"""Burstiness and perplexity-proxy analysis.

AI text has low burstiness (uniform sentence lengths) and low vocabulary
surprise. Human academic writing alternates between short punchy sentences
and long technical ones.

Metric: coefficient of variation (CV) of sentence lengths.
  - Human academic: CV ≈ 0.5–1.0
  - AI-generated:   CV ≈ 0.2–0.4
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

# Simple sentence splitter — splits on sentence-ending punctuation followed by capital letter
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences, handling academic abbreviations."""
    raw = _SENT_SPLIT.split(text)
    return [s.strip() for s in raw if len(s.strip()) > 5]


def _word_count(sentence: str) -> int:
    return len(sentence.split())


@dataclass
class BurstinessChecker:
    """Measures sentence-length variance (burstiness) as an AI signal."""

    name: str = "burstiness"
    description: str = "Detects uniform sentence lengths typical of AI writing"

    # Thresholds
    low_cv_threshold: float = 0.35
    very_low_cv_threshold: float = 0.25
    min_sentences: int = 10

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        # Join lines into paragraphs, skip headings / blank lines
        if lines is None:
            lines = text.split("\n")

        prose_lines = [
            ln for ln in lines
            if ln.strip()
            and not ln.strip().startswith("#")
            and not ln.strip().startswith("![")
            and not ln.strip().startswith("|")
            and not ln.strip().startswith("$$")
        ]
        prose = " ".join(prose_lines)
        sentences = _split_sentences(prose)

        if len(sentences) < self.min_sentences:
            return CheckerResult(
                checker_name=self.name,
                metrics={"sentence_count": len(sentences), "cv": None},
                summary=f"Too few sentences ({len(sentences)}) for burstiness analysis",
            )

        lengths = [_word_count(s) for s in sentences]
        mean_len = statistics.mean(lengths)
        std_len = statistics.stdev(lengths)
        cv = std_len / mean_len if mean_len > 0 else 0.0

        # Paragraph-level burstiness (variance of paragraph lengths)
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 20]
        para_lengths = [_word_count(p) for p in paragraphs]
        para_cv = (
            statistics.stdev(para_lengths) / statistics.mean(para_lengths)
            if len(para_lengths) > 2 and statistics.mean(para_lengths) > 0
            else 0.0
        )

        issues: list[Issue] = []

        if cv < self.very_low_cv_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.ERROR,
                line=0,
                message=(
                    f"Very low sentence-length CV ({cv:.3f}) — strong AI signal. "
                    f"Human academic writing typically has CV > 0.5."
                ),
                suggestion="Vary sentence lengths: mix short declarative statements with longer analytical ones.",
            ))
        elif cv < self.low_cv_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=(
                    f"Low sentence-length CV ({cv:.3f}) — moderate AI signal. "
                    f"Consider more variation in sentence structure."
                ),
                suggestion="Break up uniformly-medium sentences into a mix of short and long.",
            ))

        # Flag runs of similar-length sentences (3+ consecutive within ±3 words)
        run_start = 0
        for i in range(1, len(lengths)):
            if abs(lengths[i] - lengths[i - 1]) > 3:
                if i - run_start >= 4:
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.INFO,
                        line=0,
                        message=f"Run of {i - run_start} similarly-lengthed sentences (words: {lengths[run_start:i]})",
                        suggestion="Vary sentence structure in this passage.",
                    ))
                run_start = i

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "sentence_count": len(sentences),
                "mean_sentence_length": round(mean_len, 1),
                "std_sentence_length": round(std_len, 1),
                "cv_sentence_length": round(cv, 3),
                "min_sentence_length": min(lengths),
                "max_sentence_length": max(lengths),
                "paragraph_count": len(paragraphs),
                "cv_paragraph_length": round(para_cv, 3),
            },
            summary=f"CV={cv:.3f} ({'AI-like' if cv < self.low_cv_threshold else 'human-like'}), "
                    f"{len(sentences)} sentences, mean {mean_len:.0f} words",
        )
