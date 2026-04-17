"""Readability metrics for academic manuscripts.

Computes standard readability indices and flags text that is
suspiciously uniform in readability (an AI signal) or inappropriate
for academic writing (too simple or too complex).

Uses only stdlib — no external dependencies (textstat-compatible formulas).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

_SENT_END = re.compile(r"[.!?]+")
_WORD_RE = re.compile(r"[a-zA-Z]+")
_SYLLABLE_RE = re.compile(r"[aeiouy]+", re.IGNORECASE)


def _count_syllables(word: str) -> int:
    """Estimate syllable count using vowel-cluster heuristic."""
    word = word.lower().rstrip("e")
    matches = _SYLLABLE_RE.findall(word)
    return max(1, len(matches))


def _split_sentences(text: str) -> list[str]:
    parts = _SENT_END.split(text)
    return [s.strip() for s in parts if len(s.strip()) > 2]


def _extract_words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def flesch_reading_ease(text: str) -> float:
    """Flesch Reading Ease: 0–100 (higher = easier)."""
    sentences = _split_sentences(text)
    words = _extract_words(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    return 206.835 - 1.015 * asl - 84.6 * asw


def flesch_kincaid_grade(text: str) -> float:
    """Flesch-Kincaid Grade Level."""
    sentences = _split_sentences(text)
    words = _extract_words(text)
    if not sentences or not words:
        return 0.0
    syllables = sum(_count_syllables(w) for w in words)
    asl = len(words) / len(sentences)
    asw = syllables / len(words)
    return 0.39 * asl + 11.8 * asw - 15.59


def gunning_fog(text: str) -> float:
    """Gunning Fog Index."""
    sentences = _split_sentences(text)
    words = _extract_words(text)
    if not sentences or not words:
        return 0.0
    complex_words = sum(1 for w in words if _count_syllables(w) >= 3)
    asl = len(words) / len(sentences)
    pcw = (complex_words / len(words)) * 100
    return 0.4 * (asl + pcw)


def coleman_liau(text: str) -> float:
    """Coleman-Liau Index."""
    sentences = _split_sentences(text)
    words = _extract_words(text)
    if not sentences or not words:
        return 0.0
    chars = sum(len(w) for w in words)
    L = (chars / len(words)) * 100  # avg letters per 100 words
    S = (len(sentences) / len(words)) * 100  # avg sentences per 100 words
    return 0.0588 * L - 0.296 * S - 15.8


@dataclass
class ReadabilityChecker:
    """Computes readability metrics and flags anomalies."""

    name: str = "readability"
    description: str = "Readability indices + uniformity check across sections"

    # Academic writing typically scores 20-50 on Flesch (difficult)
    min_flesch: float = 10.0
    max_flesch: float = 60.0
    academic_grade_range: tuple[float, float] = (12.0, 20.0)

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        prose_text = "\n".join(
            ln for ln in lines
            if ln.strip()
            and not ln.strip().startswith("#")
            and not ln.strip().startswith("![")
            and not ln.strip().startswith("|")
            and not ln.strip().startswith("$$")
        )

        words = _extract_words(prose_text)
        if len(words) < 50:
            return CheckerResult(
                checker_name=self.name,
                metrics={"word_count": len(words)},
                summary="Too few words for readability analysis",
            )

        fre = flesch_reading_ease(prose_text)
        fkg = flesch_kincaid_grade(prose_text)
        fog = gunning_fog(prose_text)
        cli = coleman_liau(prose_text)

        issues: list[Issue] = []

        if fre > self.max_flesch:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Flesch Reading Ease too high ({fre:.1f}) — text may be too simple for academic writing.",
                suggestion="Use more precise technical vocabulary and complex sentence structures.",
            ))

        if fkg < self.academic_grade_range[0]:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.INFO,
                line=0,
                message=f"Grade level ({fkg:.1f}) below typical academic range ({self.academic_grade_range[0]}-{self.academic_grade_range[1]}).",
            ))

        # Section-level readability uniformity
        sections_text: list[str] = []
        current: list[str] = []
        for line in lines:
            if line.strip().startswith("#") and current:
                joined = " ".join(current)
                if len(_extract_words(joined)) >= 30:
                    sections_text.append(joined)
                current = []
            elif line.strip() and not line.strip().startswith("#"):
                current.append(line.strip())
        if current:
            joined = " ".join(current)
            if len(_extract_words(joined)) >= 30:
                sections_text.append(joined)

        if len(sections_text) >= 3:
            section_fres = [flesch_reading_ease(s) for s in sections_text]
            mean_fre = sum(section_fres) / len(section_fres)
            if mean_fre > 0:
                import statistics
                fre_cv = statistics.stdev(section_fres) / abs(mean_fre)
                if fre_cv < 0.05:
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.WARNING,
                        line=0,
                        message=f"Section readability is suspiciously uniform (FRE CV={fre_cv:.4f}). "
                                f"AI-generated text often has identical readability across all sections.",
                        suggestion="Different sections (methods vs. discussion) should naturally "
                                   "have different readability levels.",
                    ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "word_count": len(words),
                "flesch_reading_ease": round(fre, 1),
                "flesch_kincaid_grade": round(fkg, 1),
                "gunning_fog": round(fog, 1),
                "coleman_liau": round(cli, 1),
                "section_fre_scores": [round(flesch_reading_ease(s), 1) for s in sections_text] if sections_text else [],
            },
            summary=f"Flesch={fre:.0f}, Grade={fkg:.1f}, Fog={fog:.1f}, CLI={cli:.1f}",
        )
