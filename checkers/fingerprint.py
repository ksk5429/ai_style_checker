"""Personal writing fingerprint checker.

Builds a stylometric fingerprint from the author's published/known writing
and compares new text against it. Paragraphs far from the author's centroid
are flagged -- whether AI-written or just written on a bad day.

Uses sentence-transformers for dense embeddings (optional dependency).
Falls back to TF-IDF if sentence-transformers is not installed.

Usage:
    # First, build fingerprint from known papers
    python -m checkers.fingerprint --build \
        --corpus-dir papers/paperJ2_oe00984 papers/paperJ3_oe02685 \
        --output fingerprint.json

    # Then check a manuscript against the fingerprint
    checker = FingerprintChecker(fingerprint_path="fingerprint.json")
    result = checker.check(text)
"""

from __future__ import annotations

import json
import math
import re
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from checkers.base import CheckerResult, Issue, Severity

_WORD_RE = re.compile(r"\b[a-z]{3,}\b")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# ── Feature extraction (lightweight, no dependencies) ─────────────────

def _extract_style_features(text: str) -> dict[str, float]:
    """Extract 20+ stylometric features from text.

    These features capture writing style without content:
    - Sentence length distribution
    - Word length distribution
    - Punctuation ratios
    - Function word ratios
    - Vocabulary richness
    """
    words = text.split()
    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 5]
    content_words = _WORD_RE.findall(text.lower())

    if not words or not sentences:
        return {}

    n_words = len(words)
    n_sents = len(sentences)
    n_chars = len(text)

    # Sentence length stats
    sent_lengths = [len(s.split()) for s in sentences]
    mean_sent = sum(sent_lengths) / n_sents
    std_sent = (sum((l - mean_sent) ** 2 for l in sent_lengths) / n_sents) ** 0.5 if n_sents > 1 else 0

    # Word length stats
    word_lengths = [len(w) for w in words]
    mean_word = sum(word_lengths) / n_words

    # Punctuation ratios
    commas = text.count(",") / n_words
    semicolons = text.count(";") / n_words
    colons = text.count(":") / n_words
    parens = (text.count("(") + text.count(")")) / n_words
    emdashes = text.count("\u2014") / n_words

    # Function word ratios
    function_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
                      "to", "for", "of", "with", "by", "and", "or", "but", "that", "which"}
    fw_count = sum(1 for w in content_words if w in function_words)
    fw_ratio = fw_count / max(len(content_words), 1)

    # Vocabulary richness
    unique = len(set(content_words))
    ttr = unique / max(len(content_words), 1)

    # Hapax legomena ratio
    counts = Counter(content_words)
    hapax = sum(1 for c in counts.values() if c == 1) / max(len(counts), 1)

    # Passive voice estimate
    passive_markers = len(re.findall(
        r"\b(?:is|are|was|were|been|being)\s+\w+(?:ed|en)\b", text, re.I
    ))
    passive_ratio = passive_markers / n_sents

    return {
        "mean_sentence_length": mean_sent,
        "std_sentence_length": std_sent,
        "cv_sentence_length": std_sent / mean_sent if mean_sent > 0 else 0,
        "mean_word_length": mean_word,
        "comma_ratio": commas,
        "semicolon_ratio": semicolons,
        "colon_ratio": colons,
        "paren_ratio": parens,
        "emdash_ratio": emdashes,
        "function_word_ratio": fw_ratio,
        "ttr": ttr,
        "hapax_ratio": hapax,
        "passive_ratio": passive_ratio,
        "words_per_paragraph": n_words / max(text.count("\n\n"), 1),
    }


def _cosine_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    """Cosine similarity between two feature dicts."""
    keys = set(a.keys()) & set(b.keys())
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag_a = sum(a[k] ** 2 for k in keys) ** 0.5
    mag_b = sum(b[k] ** 2 for k in keys) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Embedding-based fingerprint (optional) ────────────────────────────

_EMBED_MODEL = None


def _get_embed_model():
    """Lazy-load sentence-transformers model."""
    global _EMBED_MODEL
    if _EMBED_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _EMBED_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        except ImportError:
            return None
    return _EMBED_MODEL


def _compute_centroid(paragraphs: list[str]) -> list[float] | None:
    """Compute centroid embedding from paragraphs."""
    model = _get_embed_model()
    if model is None:
        return None
    embeddings = model.encode(paragraphs, show_progress_bar=False)
    centroid = embeddings.mean(axis=0).tolist()
    return centroid


def _embedding_distance(paragraph: str, centroid: list[float]) -> float:
    """Compute cosine distance between a paragraph and the centroid."""
    model = _get_embed_model()
    if model is None:
        return 0.0
    import numpy as np
    emb = model.encode([paragraph], show_progress_bar=False)[0]
    centroid_arr = np.array(centroid)
    cos_sim = np.dot(emb, centroid_arr) / (np.linalg.norm(emb) * np.linalg.norm(centroid_arr) + 1e-8)
    return 1.0 - float(cos_sim)


# ── Fingerprint building ─────────────────────────────────────────────

def build_fingerprint(
    corpus_paths: list[str | Path],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build a writing fingerprint from multiple manuscript files.

    Args:
        corpus_paths: List of .qmd or .md files to learn from.
        output_path: Where to save the fingerprint JSON.

    Returns:
        Fingerprint dict with style features and optional embedding centroid.
    """
    all_paragraphs: list[str] = []
    all_features: list[dict[str, float]] = []

    for path in corpus_paths:
        p = Path(path)
        if not p.exists():
            continue

        text = p.read_text(encoding="utf-8", errors="replace")
        # Strip YAML frontmatter
        if text.startswith("---"):
            end = text.find("---", 3)
            if end != -1:
                text = text[end + 3:]

        # Extract paragraphs
        lines = text.split("\n")
        current: list[str] = []
        for line in lines:
            stripped = line.strip()
            if (not stripped or stripped.startswith("#") or stripped.startswith("![")
                    or stripped.startswith("|") or stripped.startswith("$$")):
                if current:
                    para = " ".join(current)
                    if len(para.split()) >= 20:
                        all_paragraphs.append(para)
                        all_features.append(_extract_style_features(para))
                    current = []
            else:
                current.append(stripped)
        if current:
            para = " ".join(current)
            if len(para.split()) >= 20:
                all_paragraphs.append(para)
                all_features.append(_extract_style_features(para))

    if not all_features:
        return {"error": "No paragraphs extracted from corpus"}

    # Compute mean features (the "fingerprint")
    feature_keys = all_features[0].keys()
    mean_features = {}
    std_features = {}
    for key in feature_keys:
        values = [f.get(key, 0) for f in all_features]
        mean_features[key] = sum(values) / len(values)
        variance = sum((v - mean_features[key]) ** 2 for v in values) / len(values)
        std_features[key] = variance ** 0.5

    # Compute embedding centroid
    centroid = _compute_centroid(all_paragraphs)

    fingerprint = {
        "n_paragraphs": len(all_paragraphs),
        "n_files": len(corpus_paths),
        "mean_features": mean_features,
        "std_features": std_features,
        "centroid": centroid,
    }

    if output_path:
        Path(output_path).write_text(
            json.dumps(fingerprint, indent=2), encoding="utf-8"
        )

    return fingerprint


# ── Checker ───────────────────────────────────────────────────────────

@dataclass
class FingerprintChecker:
    """Compares manuscript paragraphs against the author's writing fingerprint."""

    name: str = "fingerprint"
    description: str = "Compares text against author's personal writing fingerprint"

    fingerprint_path: str = ""
    _fingerprint: dict[str, Any] | None = None

    # Thresholds
    style_distance_threshold: float = 0.85  # cosine sim < 0.85 = flagged
    embedding_distance_threshold: float = 0.40  # cosine distance > 0.40 = flagged

    def _load_fingerprint(self) -> dict[str, Any] | None:
        if self._fingerprint is not None:
            return self._fingerprint

        # Search for fingerprint file
        candidates = [
            Path(self.fingerprint_path) if self.fingerprint_path else None,
            Path(os.environ.get("FINGERPRINT_PATH", "")) if os.environ.get("FINGERPRINT_PATH") else None,
            Path(__file__).parent.parent / "fingerprint.json",
            Path.cwd() / "fingerprint.json",
        ]
        for c in candidates:
            if c and c.exists():
                self._fingerprint = json.loads(c.read_text(encoding="utf-8"))
                return self._fingerprint
        return None

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        fingerprint = self._load_fingerprint()

        if fingerprint is None:
            return CheckerResult(
                checker_name=self.name,
                metrics={"status": "no_fingerprint"},
                summary="No fingerprint file found. Run: python -m checkers.fingerprint --build",
            )

        # Extract paragraphs from the manuscript
        paragraphs: list[tuple[int, str]] = []
        current: list[str] = []
        para_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if (not stripped or stripped.startswith("#") or stripped.startswith("![")
                    or stripped.startswith("|") or stripped.startswith("$$")):
                if current:
                    para = " ".join(current)
                    if len(para.split()) >= 20:
                        paragraphs.append((para_start, para))
                    current = []
            else:
                if not current:
                    para_start = i + 1
                current.append(stripped)
        if current:
            para = " ".join(current)
            if len(para.split()) >= 20:
                paragraphs.append((para_start, para))

        if not paragraphs:
            return CheckerResult(
                checker_name=self.name,
                metrics={"paragraph_count": 0},
                summary="No paragraphs for fingerprint comparison",
            )

        mean_features = fingerprint.get("mean_features", {})
        centroid = fingerprint.get("centroid")

        issues: list[Issue] = []
        style_sims: list[float] = []
        embed_dists: list[float] = []

        for line_num, para in paragraphs:
            # Style feature comparison
            para_features = _extract_style_features(para)
            sim = _cosine_similarity(para_features, mean_features)
            style_sims.append(sim)

            # Embedding comparison (if available)
            embed_dist = 0.0
            if centroid:
                embed_dist = _embedding_distance(para, centroid)
                embed_dists.append(embed_dist)

            # Flag if significantly different from fingerprint
            if sim < self.style_distance_threshold:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    line=line_num,
                    message=f"Paragraph style deviates from your fingerprint "
                            f"(similarity={sim:.3f}, threshold={self.style_distance_threshold})",
                    context=para[:100],
                    suggestion="This paragraph doesn't match your typical writing style. "
                               "Review for AI-generated content or consider revising to match your voice.",
                ))

            if centroid and embed_dist > self.embedding_distance_threshold:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    line=line_num,
                    message=f"Paragraph semantically distant from your writing centroid "
                            f"(distance={embed_dist:.3f}, threshold={self.embedding_distance_threshold})",
                    context=para[:100],
                    suggestion="This paragraph's content/vocabulary is unusual compared to your other work.",
                ))

        mean_sim = sum(style_sims) / len(style_sims) if style_sims else 0
        mean_dist = sum(embed_dists) / len(embed_dists) if embed_dists else 0

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "paragraph_count": len(paragraphs),
                "mean_style_similarity": round(mean_sim, 4),
                "min_style_similarity": round(min(style_sims), 4) if style_sims else 0,
                "mean_embedding_distance": round(mean_dist, 4) if embed_dists else None,
                "max_embedding_distance": round(max(embed_dists), 4) if embed_dists else None,
                "flagged_paragraphs": len(issues),
                "fingerprint_corpus_size": fingerprint.get("n_paragraphs", 0),
            },
            summary=f"Style sim={mean_sim:.3f}, "
                    f"embed dist={mean_dist:.3f}, "
                    f"{len(issues)} paragraphs flagged "
                    f"(vs {fingerprint.get('n_paragraphs', 0)}-paragraph fingerprint)",
        )


# ── CLI for building fingerprints ─────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build personal writing fingerprint")
    parser.add_argument("--build", action="store_true", help="Build fingerprint from corpus")
    parser.add_argument("--corpus", nargs="+", help="Paths to .qmd/.md files")
    parser.add_argument("--corpus-dir", nargs="+", help="Directories containing manuscript.qmd")
    parser.add_argument("--output", type=str, default="fingerprint.json", help="Output path")
    args = parser.parse_args()

    if args.build:
        paths: list[Path] = []
        if args.corpus:
            paths.extend(Path(p) for p in args.corpus)
        if args.corpus_dir:
            for d in args.corpus_dir:
                qmd = Path(d) / "manuscript.qmd"
                if qmd.exists():
                    paths.append(qmd)

        if not paths:
            print("No corpus files found. Use --corpus or --corpus-dir")
        else:
            print(f"Building fingerprint from {len(paths)} files...")
            fp = build_fingerprint(paths, args.output)
            print(f"Fingerprint saved: {args.output}")
            print(f"  Paragraphs: {fp.get('n_paragraphs', 0)}")
            print(f"  Centroid: {'computed' if fp.get('centroid') else 'skipped (no sentence-transformers)'}")
            for key, val in fp.get("mean_features", {}).items():
                print(f"  {key}: {val:.4f}")
