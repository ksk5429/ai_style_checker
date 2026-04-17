"""Vocabulary diversity analysis.

AI text has characteristically uniform vocabulary — high type-token ratio
consistency across sections, lower hapax legomena ratio, and preference
for common words over domain-specific jargon.

Metrics:
  - TTR (Type-Token Ratio): unique words / total words
  - Hapax ratio: words appearing exactly once / total unique words
  - Section-level TTR variance (low variance = AI signal)
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

# Words to exclude from analysis
_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "it", "its", "not", "no", "as", "if", "than",
    "so", "which", "who", "whom", "what", "where", "when", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "very", "just", "also", "into",
    "over", "after", "before", "between", "under", "about", "through",
})

_WORD_RE = re.compile(r"\b[a-z]{2,}\b")


def _tokenize(text: str) -> list[str]:
    """Extract lowercase content words, excluding stopwords."""
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS]


def _compute_ttr(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    return len(set(tokens)) / len(tokens)


def _compute_hapax_ratio(tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    hapax = sum(1 for c in counts.values() if c == 1)
    return hapax / len(counts) if counts else 0.0


@dataclass
class VocabularyChecker:
    """Analyzes vocabulary diversity as an AI detection signal."""

    name: str = "vocabulary"
    description: str = "Measures vocabulary diversity (TTR, hapax ratio, section variance)"

    # Thresholds
    low_hapax_threshold: float = 0.45  # AI typically < 0.45
    low_section_variance_threshold: float = 0.02  # AI sections have nearly identical TTR

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        # Global tokens
        tokens = _tokenize(text)
        if len(tokens) < 50:
            return CheckerResult(
                checker_name=self.name,
                metrics={"word_count": len(tokens)},
                summary="Too few content words for vocabulary analysis",
            )

        global_ttr = _compute_ttr(tokens)
        hapax_ratio = _compute_hapax_ratio(tokens)
        counts = Counter(tokens)

        # Section-level TTR analysis
        sections: list[list[str]] = []
        current_section: list[str] = []
        for line in lines:
            if line.strip().startswith("#") and current_section:
                sections.append(current_section)
                current_section = []
            elif line.strip() and not line.strip().startswith("#"):
                current_section.extend(_tokenize(line))
        if current_section:
            sections.append(current_section)

        section_ttrs = [_compute_ttr(s) for s in sections if len(s) >= 30]

        issues: list[Issue] = []

        # Low hapax ratio flag
        if hapax_ratio < self.low_hapax_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Low hapax ratio ({hapax_ratio:.3f}) — AI tends to reuse vocabulary uniformly. "
                        f"Human academic text typically has hapax ratio > 0.50.",
                suggestion="Use more varied vocabulary. Replace repeated terms with synonyms or pronouns.",
            ))

        # Section TTR uniformity
        if len(section_ttrs) >= 3:
            ttr_cv = statistics.stdev(section_ttrs) / statistics.mean(section_ttrs) if statistics.mean(section_ttrs) > 0 else 0
            if ttr_cv < self.low_section_variance_threshold:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    line=0,
                    message=f"Section TTR variance is very low (CV={ttr_cv:.4f}) — "
                            f"sections use suspiciously similar vocabulary distributions.",
                    suggestion="Each section should have distinct vocabulary reflecting its specific content.",
                ))

        # Top overused non-technical words (potential AI padding)
        ai_padding_words = {
            "various", "significant", "particular", "specific", "important",
            "different", "several", "potential", "relevant", "comprehensive",
            "effective", "efficient", "essential", "critical", "fundamental",
            "substantial", "considerable", "notable", "remarkable", "inherent",
        }
        overused = [
            (w, c) for w, c in counts.most_common(100)
            if w in ai_padding_words and c >= 5
        ]
        for word, count in overused:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.INFO,
                line=0,
                message=f"Padding word '{word}' used {count} times — common AI filler",
                suggestion=f"Consider reducing '{word}' usage or replacing with more specific terms.",
            ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "content_word_count": len(tokens),
                "unique_words": len(set(tokens)),
                "ttr": round(global_ttr, 4),
                "hapax_ratio": round(hapax_ratio, 4),
                "section_ttrs": [round(t, 4) for t in section_ttrs],
                "section_ttr_cv": round(
                    statistics.stdev(section_ttrs) / statistics.mean(section_ttrs), 4
                ) if len(section_ttrs) >= 3 and statistics.mean(section_ttrs) > 0 else None,
            },
            summary=f"TTR={global_ttr:.3f}, hapax={hapax_ratio:.3f}, {len(set(tokens))} unique / {len(tokens)} total",
        )
