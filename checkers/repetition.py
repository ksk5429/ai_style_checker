"""Repetition and self-plagiarism detector.

AI text often repeats phrases, restates the introduction in the conclusion,
and uses the same transition patterns across sections. This checker finds:
- Repeated n-grams (3-gram, 4-gram, 5-gram)
- Cross-section phrase duplication
- Conclusion restating introduction
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

_WORD_RE = re.compile(r"\b[a-z]+\b")


def _extract_ngrams(text: str, n: int) -> list[str]:
    """Extract word n-grams from text."""
    words = _WORD_RE.findall(text.lower())
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def _jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


@dataclass
class RepetitionChecker:
    """Detects repetitive phrases and cross-section duplication."""

    name: str = "repetition"
    description: str = "Finds repeated n-grams, cross-section duplication, and conclusion restatement"

    # Thresholds
    ngram_repeat_threshold: int = 3  # flag 4-grams appearing 3+ times
    intro_conclusion_threshold: float = 0.25  # Jaccard > 0.25 = suspicious

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        issues: list[Issue] = []

        # ── Repeated n-grams ─────────────────────────────────────
        for n in [4, 5, 6]:
            ngrams = _extract_ngrams(text, n)
            counts = Counter(ngrams)
            repeated = {
                ng: c for ng, c in counts.items()
                if c >= self.ngram_repeat_threshold
                and not any(skip in ng for skip in [
                    "of the", "in the", "et al", "this study",
                    "is the", "for the", "on the", "at the",
                ])
            }
            for ng, count in sorted(repeated.items(), key=lambda x: -x[1])[:10]:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING if count >= 5 else Severity.INFO,
                    line=0,
                    message=f"{n}-gram repeated {count}x: '{ng}'",
                    suggestion=f"Rephrase some instances of '{ng}' to reduce mechanical repetition.",
                ))

        # ── Repeated transition patterns ──────────────────────────
        transition_re = re.compile(
            r"^(Furthermore|Moreover|Additionally|In addition|However|"
            r"Nevertheless|On the other hand|Conversely|In contrast|"
            r"Therefore|Consequently|As a result|Thus|Hence|"
            r"Specifically|In particular|Notably|Importantly)\b",
            re.IGNORECASE | re.MULTILINE,
        )
        transitions = [m.group(1).lower() for m in transition_re.finditer(text)]
        transition_counts = Counter(transitions)
        for word, count in transition_counts.items():
            if count >= 4:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    line=0,
                    message=f"Transition '{word}' used {count} times — suggests mechanical generation.",
                    suggestion=f"Vary transitions or remove unnecessary ones.",
                ))

        # ── Introduction vs Conclusion similarity ─────────────────
        sections: dict[str, str] = {}
        current_heading = ""
        current_text: list[str] = []
        for line in lines:
            if line.strip().startswith("#"):
                if current_heading and current_text:
                    sections[current_heading.lower()] = " ".join(current_text)
                current_heading = line.strip().lstrip("#").strip()
                current_text = []
            elif line.strip():
                current_text.append(line.strip())
        if current_heading and current_text:
            sections[current_heading.lower()] = " ".join(current_text)

        intro_key = next((k for k in sections if "intro" in k), None)
        concl_key = next((k for k in sections if "conclu" in k), None)

        intro_concl_sim = 0.0
        if intro_key and concl_key:
            intro_4grams = set(_extract_ngrams(sections[intro_key], 4))
            concl_4grams = set(_extract_ngrams(sections[concl_key], 4))
            intro_concl_sim = _jaccard_similarity(intro_4grams, concl_4grams)

            if intro_concl_sim > self.intro_conclusion_threshold:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.ERROR,
                    line=0,
                    message=f"Conclusion restates Introduction (Jaccard 4-gram similarity: {intro_concl_sim:.3f}). "
                            f"AI frequently copies introduction phrasing into conclusions.",
                    suggestion="Rewrite conclusion to present new synthesis, not restatement.",
                ))

        # ── Cross-section 5-gram overlap ──────────────────────────
        section_ngrams: dict[str, set[str]] = {}
        for heading, sec_text in sections.items():
            if len(sec_text.split()) > 30:
                section_ngrams[heading] = set(_extract_ngrams(sec_text, 5))

        section_keys = list(section_ngrams.keys())
        for i in range(len(section_keys)):
            for j in range(i + 1, len(section_keys)):
                overlap = section_ngrams[section_keys[i]] & section_ngrams[section_keys[j]]
                # Filter out very common academic phrases
                meaningful = {
                    ng for ng in overlap
                    if len(ng.split()) >= 5
                    and not any(skip in ng for skip in ["of the", "et al", "in the", "for the"])
                }
                if len(meaningful) >= 5:
                    issues.append(Issue(
                        checker=self.name,
                        severity=Severity.INFO,
                        line=0,
                        message=f"Sections '{section_keys[i]}' and '{section_keys[j]}' share "
                                f"{len(meaningful)} unique 5-grams.",
                    ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "repeated_4grams": sum(1 for ng in Counter(_extract_ngrams(text, 4)).values() if ng >= 3),
                "transition_reuse": dict(transition_counts.most_common(5)),
                "intro_conclusion_similarity": round(intro_concl_sim, 4),
            },
            summary=f"Intro/Concl similarity: {intro_concl_sim:.3f}, "
                    f"{sum(1 for t in transition_counts.values() if t >= 4)} overused transitions",
        )
