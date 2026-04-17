"""Sentence-opener diversity checker.

The single strongest statistical signal for AI text: sentence-opener monotony.
AI starts 40-60% of sentences with "The/This/These/It" (noun phrase + verb).
Human academic writing varies openers: adverbial clauses, prepositional phrases,
participial phrases, questions, numbers, transitions.

Metrics:
  - POS-tag distribution of first 2 tokens per sentence
  - Dominant opener ratio (% of sentences starting with the same pattern)
  - Opener category diversity (Shannon entropy over opener types)
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Opener categories based on the first word(s)
_ARTICLE_OPENERS = frozenset({"the", "a", "an"})
_DEMONSTRATIVE_OPENERS = frozenset({"this", "that", "these", "those"})
_PRONOUN_OPENERS = frozenset({"it", "we", "they", "he", "she", "our", "its"})
_PASSIVE_OPENERS = frozenset({"is", "are", "was", "were"})  # sentence starts with be-verb
_NUMBER_OPENERS = re.compile(r"^\d")
_PREP_OPENERS = frozenset({
    "in", "on", "at", "by", "for", "from", "with", "to", "of",
    "during", "after", "before", "between", "through", "across",
    "above", "below", "under", "over", "within", "without",
    "among", "against", "along", "around", "beyond", "despite",
})
_ADVERB_OPENERS = frozenset({
    "however", "moreover", "furthermore", "additionally", "consequently",
    "therefore", "thus", "hence", "accordingly", "specifically",
    "notably", "importantly", "similarly", "conversely", "alternatively",
    "meanwhile", "subsequently", "initially", "finally", "overall",
    "here", "there", "recently", "generally", "typically",
    "first", "second", "third", "fourth", "fifth",
})
_CONJUNCTION_OPENERS = frozenset({
    "although", "because", "since", "while", "when", "if", "unless",
    "whereas", "as", "once", "until", "after", "before",
})
_PARTICIPIAL = re.compile(r"^[A-Z][a-z]+(?:ing|ed|en)\b")


def _classify_opener(sentence: str) -> str:
    """Classify a sentence's opening pattern."""
    words = sentence.split()
    if not words:
        return "other"

    first = words[0].lower().rstrip(",")

    if first in _ARTICLE_OPENERS:
        return "article"  # The/A/An
    if first in _DEMONSTRATIVE_OPENERS:
        return "demonstrative"  # This/That/These/Those
    if first in _PRONOUN_OPENERS:
        return "pronoun"  # It/We/They/Our
    if first in _PREP_OPENERS:
        return "prepositional"  # In/On/At/By...
    if first in _ADVERB_OPENERS:
        return "adverb"  # However/Moreover/Thus...
    if first in _CONJUNCTION_OPENERS:
        return "subordinate"  # Although/Because/Since...
    if _NUMBER_OPENERS.match(words[0]):
        return "numeric"  # 3.5 m, 100g, ...
    if _PARTICIPIAL.match(words[0]):
        return "participial"  # Running/Based/Given...
    if first in _PASSIVE_OPENERS:
        return "passive_start"

    return "other"


def _shannon_entropy(counts: Counter) -> float:
    """Compute Shannon entropy over a distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


@dataclass
class SentenceOpenerChecker:
    """Measures sentence-opener diversity as an AI detection signal."""

    name: str = "sentence_openers"
    description: str = "Detects monotonous sentence openers (strongest AI statistical signal)"

    # Thresholds
    # AI text: article+demonstrative+pronoun often > 55%
    # Human academic: typically 35-50%
    noun_phrase_threshold: float = 0.55
    dominant_single_threshold: float = 0.35  # any single opener type > 35%
    low_entropy_threshold: float = 1.8  # Shannon entropy < 1.8 = low diversity
    min_sentences: int = 15

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        # Extract prose sentences (skip headings, figures, tables, equations)
        prose = " ".join(
            ln for ln in lines
            if ln.strip()
            and not ln.strip().startswith("#")
            and not ln.strip().startswith("![")
            and not ln.strip().startswith("|")
            and not ln.strip().startswith("$$")
            and not ln.strip().startswith("- ")
            and not ln.strip().startswith("```")
        )
        sentences = [s.strip() for s in _SENT_SPLIT.split(prose) if len(s.strip()) > 10]

        if len(sentences) < self.min_sentences:
            return CheckerResult(
                checker_name=self.name,
                metrics={"sentence_count": len(sentences)},
                summary=f"Too few sentences ({len(sentences)}) for opener analysis",
            )

        # Classify each opener
        opener_types = [_classify_opener(s) for s in sentences]
        counts = Counter(opener_types)
        total = len(opener_types)

        # Compute metrics
        article_ratio = counts.get("article", 0) / total
        demonstrative_ratio = counts.get("demonstrative", 0) / total
        pronoun_ratio = counts.get("pronoun", 0) / total
        noun_phrase_ratio = article_ratio + demonstrative_ratio + pronoun_ratio

        # Dominant opener
        most_common_type, most_common_count = counts.most_common(1)[0]
        dominant_ratio = most_common_count / total

        # Entropy
        entropy = _shannon_entropy(counts)
        # Max entropy for reference (if all categories used equally)
        max_entropy = math.log2(len(counts)) if len(counts) > 1 else 0

        issues: list[Issue] = []

        if noun_phrase_ratio > self.noun_phrase_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Noun-phrase openers dominate ({noun_phrase_ratio:.0%} of sentences start "
                        f"with The/This/These/It/We). AI text typically exceeds 55%; "
                        f"human writing is usually 35-50%.",
                suggestion="Vary sentence openers: start with prepositional phrases, "
                           "adverbial clauses, participial phrases, or numeric data.",
            ))

        if dominant_ratio > self.dominant_single_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Single opener type '{most_common_type}' used in {dominant_ratio:.0%} "
                        f"of sentences ({most_common_count}/{total}). This monotony is a strong AI signal.",
                suggestion=f"Reduce '{most_common_type}' openers. Rewrite some sentences to start "
                           f"with a different grammatical structure.",
            ))

        if entropy < self.low_entropy_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Opener entropy is low ({entropy:.2f} bits, max possible {max_entropy:.2f}). "
                        f"AI text typically has entropy < 1.8; human writing > 2.2.",
                suggestion="Diversify sentence openings across more grammatical categories.",
            ))

        # Section-level analysis: find runs of same opener type
        run_length = 1
        for i in range(1, len(opener_types)):
            if opener_types[i] == opener_types[i - 1]:
                run_length += 1
                if run_length >= 4:
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.INFO,
                        line=0,
                        message=f"Run of {run_length}+ sentences starting with '{opener_types[i]}' "
                                f"pattern near sentence {i + 1}.",
                    ))
            else:
                run_length = 1

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "sentence_count": total,
                "opener_distribution": dict(counts.most_common()),
                "noun_phrase_ratio": round(noun_phrase_ratio, 3),
                "dominant_opener": most_common_type,
                "dominant_ratio": round(dominant_ratio, 3),
                "entropy": round(entropy, 3),
                "max_entropy": round(max_entropy, 3),
            },
            summary=f"Openers: {noun_phrase_ratio:.0%} noun-phrase, "
                    f"entropy={entropy:.2f}/{max_entropy:.2f}, "
                    f"dominant='{most_common_type}' ({dominant_ratio:.0%})",
        )
