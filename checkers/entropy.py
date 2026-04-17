"""Paragraph-level information entropy variance.

AI generates paragraphs with nearly identical information density.
Human paragraphs vary -- a methods paragraph is dense with specifics,
a discussion paragraph is sparser with interpretation.

Metrics:
  - Per-paragraph Shannon entropy (character-level)
  - Entropy variance across paragraphs (low variance = AI signal)
  - Entropy curve shape (human writing has more peaks and valleys)
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

_WORD_RE = re.compile(r"\b[a-z]{2,}\b")


def _paragraph_entropy(text: str) -> float:
    """Compute word-level Shannon entropy for a paragraph.

    Uses word frequency distribution within the paragraph.
    Higher entropy = more diverse vocabulary = more information.
    """
    words = _WORD_RE.findall(text.lower())
    if len(words) < 5:
        return 0.0
    counts = Counter(words)
    total = len(words)
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def _extract_paragraphs(lines: list[str], min_words: int = 20) -> list[str]:
    """Extract prose paragraphs from lines, skipping non-prose."""
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if (not stripped
            or stripped.startswith("#")
            or stripped.startswith("![")
            or stripped.startswith("|")
            or stripped.startswith("$$")
            or stripped.startswith("```")
            or stripped.startswith("- [")):
            if current:
                para = " ".join(current)
                if len(para.split()) >= min_words:
                    paragraphs.append(para)
                current = []
        else:
            current.append(stripped)

    if current:
        para = " ".join(current)
        if len(para.split()) >= min_words:
            paragraphs.append(para)

    return paragraphs


@dataclass
class EntropyChecker:
    """Measures paragraph-level entropy variance as an AI signal."""

    name: str = "entropy"
    description: str = "Detects uniform information density across paragraphs (AI signal)"

    # Thresholds
    low_cv_threshold: float = 0.08  # CV of paragraph entropies < 0.08 = suspicious
    very_low_cv_threshold: float = 0.05  # CV < 0.05 = strong AI signal
    min_paragraphs: int = 8

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        paragraphs = _extract_paragraphs(lines)

        if len(paragraphs) < self.min_paragraphs:
            return CheckerResult(
                checker_name=self.name,
                metrics={"paragraph_count": len(paragraphs)},
                summary=f"Too few paragraphs ({len(paragraphs)}) for entropy analysis",
            )

        # Compute per-paragraph entropy
        entropies = [_paragraph_entropy(p) for p in paragraphs]

        mean_entropy = statistics.mean(entropies)
        std_entropy = statistics.stdev(entropies)
        cv = std_entropy / mean_entropy if mean_entropy > 0 else 0.0

        # Section-level entropy analysis
        # Split into quartiles and compare
        n = len(entropies)
        q1 = entropies[:n // 4]
        q4 = entropies[3 * n // 4:]
        q1_mean = statistics.mean(q1) if q1 else 0
        q4_mean = statistics.mean(q4) if q4 else 0

        # Entropy range (max - min) as a diversity measure
        entropy_range = max(entropies) - min(entropies)

        issues: list[Issue] = []

        if cv < self.very_low_cv_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.ERROR,
                line=0,
                message=f"Very low entropy variance (CV={cv:.4f}). All paragraphs have nearly "
                        f"identical information density -- strong AI signal. Human writing varies "
                        f"between dense methods paragraphs and sparser discussion.",
                suggestion="Vary paragraph complexity: make methods paragraphs denser with specifics, "
                           "make discussion paragraphs more interpretive and varied.",
            ))
        elif cv < self.low_cv_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Low entropy variance (CV={cv:.4f}). Paragraphs have suspiciously uniform "
                        f"information density. Human academic writing typically has CV > 0.10.",
                suggestion="Different sections should naturally have different density levels.",
            ))

        # Check for flat entropy curve (no peaks/valleys)
        if entropy_range < 1.0 and len(entropies) >= 10:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.INFO,
                line=0,
                message=f"Narrow entropy range ({entropy_range:.2f} bits). Human writing typically "
                        f"has range > 1.5 bits between densest and sparsest paragraphs.",
            ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "paragraph_count": len(paragraphs),
                "mean_entropy": round(mean_entropy, 3),
                "std_entropy": round(std_entropy, 3),
                "cv_entropy": round(cv, 4),
                "entropy_range": round(entropy_range, 3),
                "min_entropy": round(min(entropies), 3),
                "max_entropy": round(max(entropies), 3),
                "q1_mean": round(q1_mean, 3),
                "q4_mean": round(q4_mean, 3),
                "per_paragraph": [round(e, 2) for e in entropies],
            },
            summary=f"Entropy CV={cv:.4f} ({'uniform (AI-like)' if cv < self.low_cv_threshold else 'varied (human-like)'}), "
                    f"range={entropy_range:.1f} bits, {len(paragraphs)} paragraphs",
        )
