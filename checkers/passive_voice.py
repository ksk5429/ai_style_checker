"""Passive voice detector using regex heuristics.

Academic writing uses passive voice legitimately, but AI text
tends to use it excessively and uniformly. This checker measures
the passive-to-active ratio and flags sections with > 40% passive.

No spaCy dependency — uses regex patterns for portability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from checkers.base import CheckerResult, Issue, Severity

# Passive voice patterns: be-verb + past participle
_BE_VERBS = r"(?:is|are|was|were|be|been|being|has been|have been|had been|will be|would be|could be|should be|may be|might be)"
_PAST_PARTICIPLE = r"(?:[a-z]+ed|[a-z]+en|[a-z]+ied|built|done|found|given|gone|known|made|shown|taken|told|written|seen|set|run|put|paid|met|led|left|kept|held|got|felt|drawn|cut|brought|bought|born|begun|become|chosen|driven|eaten|fallen|flown|forgotten|frozen|hidden|ridden|risen|spoken|stolen|sworn|thrown|torn|worn|woken)"

_PASSIVE_RE = re.compile(
    rf"\b{_BE_VERBS}\s+{_PAST_PARTICIPLE}\b",
    re.IGNORECASE,
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class PassiveVoiceChecker:
    """Detects excessive passive voice usage."""

    name: str = "passive_voice"
    description: str = "Measures passive/active ratio and flags excessive passive usage"

    # Thresholds
    high_passive_threshold: float = 0.40  # > 40% passive = flag
    section_passive_threshold: float = 0.50  # > 50% in a section = strong flag

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
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
        sentences = [s.strip() for s in _SENT_SPLIT.split(prose) if len(s.strip()) > 5]

        if len(sentences) < 10:
            return CheckerResult(
                checker_name=self.name,
                metrics={"sentence_count": len(sentences)},
                summary="Too few sentences for passive voice analysis",
            )

        passive_sentences: list[int] = []
        passive_matches: list[tuple[int, str, str]] = []

        for i, sent in enumerate(sentences):
            matches = list(_PASSIVE_RE.finditer(sent))
            if matches:
                passive_sentences.append(i)
                for m in matches:
                    passive_matches.append((i + 1, m.group(), sent[:80]))

        passive_ratio = len(passive_sentences) / len(sentences)

        issues: list[Issue] = []

        if passive_ratio > self.high_passive_threshold:
            issues.append(Issue(
                checker=self.name,
                severity=Severity.WARNING,
                line=0,
                message=f"Passive voice ratio ({passive_ratio:.0%}) exceeds {self.high_passive_threshold:.0%} threshold. "
                        f"{len(passive_sentences)}/{len(sentences)} sentences use passive constructions.",
                suggestion="Convert passive constructions to active voice where the agent is known.",
            ))

        # Flag clusters of consecutive passive sentences (3+)
        if passive_sentences:
            consecutive = 1
            for i in range(1, len(passive_sentences)):
                if passive_sentences[i] == passive_sentences[i - 1] + 1:
                    consecutive += 1
                    if consecutive >= 3:
                        issues.append(Issue(
                            checker=self.name,
                            severity=Severity.INFO,
                            line=0,
                            message=f"Cluster of {consecutive}+ consecutive passive sentences near sentence {passive_sentences[i]}.",
                            suggestion="Break the passive streak with an active-voice sentence.",
                        ))
                else:
                    consecutive = 1

        # Section-level analysis
        sections: list[tuple[str, list[str]]] = []
        current_heading = "Preamble"
        current_sents: list[str] = []
        for line in lines:
            if line.strip().startswith("#"):
                if current_sents:
                    sections.append((current_heading, current_sents))
                current_heading = line.strip().lstrip("#").strip()
                current_sents = []
            elif line.strip() and not line.strip().startswith(("!", "|", "$$")):
                current_sents.extend(
                    s.strip() for s in _SENT_SPLIT.split(line) if len(s.strip()) > 5
                )
        if current_sents:
            sections.append((current_heading, current_sents))

        section_ratios: dict[str, float] = {}
        for heading, sents in sections:
            if len(sents) < 5:
                continue
            n_passive = sum(1 for s in sents if _PASSIVE_RE.search(s))
            ratio = n_passive / len(sents)
            section_ratios[heading] = round(ratio, 3)
            if ratio > self.section_passive_threshold:
                issues.append(Issue(
                    checker=self.name,
                    severity=Severity.WARNING,
                    line=0,
                    message=f"Section '{heading}' has {ratio:.0%} passive voice ({n_passive}/{len(sents)} sentences).",
                    suggestion=f"Rewrite key sentences in '{heading}' using active voice.",
                ))

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "total_sentences": len(sentences),
                "passive_sentences": len(passive_sentences),
                "passive_ratio": round(passive_ratio, 3),
                "section_passive_ratios": section_ratios,
            },
            summary=f"Passive ratio: {passive_ratio:.0%} ({len(passive_sentences)}/{len(sentences)})",
        )
