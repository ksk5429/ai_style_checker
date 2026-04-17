"""Detect AI-typical writing patterns via regex and word lists.

Covers: AI transition words, flowery verbs, promotional language,
filler phrases, formulaic structures, and ChatGPT/Claude fingerprints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from checkers.base import Checker, CheckerResult, Issue, Severity

# ── Pattern banks ────────────────────────────────────────────────────
# Each tuple: (compiled regex, description, severity)

_PATTERNS: list[tuple[re.Pattern[str], str, Severity]] = []


def _p(pattern: str, desc: str, sev: Severity = Severity.WARNING) -> None:
    _PATTERNS.append((re.compile(pattern, re.IGNORECASE), desc, sev))


# AI transition words (comma-started sentences)
_p(
    r"\b(Critically|Notably|Importantly|Remarkably|Interestingly|Significantly)\b,",
    "AI transition opener with comma",
)

# Formulaic transitions (INFO — legitimate in academic writing, only flag for awareness)
_p(
    r"\b(Furthermore|Moreover|Additionally|Consequently|Subsequently|"
    r"Nonetheless|Nevertheless|Henceforth)\b,",
    "Formulaic AI transition",
    Severity.INFO,
)

# Flowery / inflated verbs
_p(
    r"\b(delve|leverage|foster|bolster|underscore|highlight|"
    r"spearhead|harness|pave the way|masquerade|"
    r"uniquely positioned|elucidate|endeavor|"
    r"embark|unravel|intricate|multifaceted|pivotal|"
    r"tapestry|synergy)\b",
    "AI-typical inflated language",
)

# Promotional / hype language
_p(
    r"\b(revolutionary|groundbreaking|game-changing|cutting-edge|"
    r"unprecedented|transformative|"
    r"next-generation|disruptive|novel approach)\b",
    "Promotional / hype language",
    Severity.ERROR,
)

# Hedging stacks (double hedges)
_p(
    r"\b(could potentially|may possibly|might perhaps|"
    r"is suggested to be|appears to possibly|"
    r"seems to potentially)\b",
    "Double-hedging (AI artifact)",
    Severity.ERROR,
)

# Filler phrases that add zero information
_p(
    r"\b(It is worth noting that|It is important to note that|"
    r"It should be mentioned that|It is crucial to acknowledge that|"
    r"It bears mentioning that|It is imperative to recognize that|"
    r"One might argue that|It goes without saying that)\b",
    "Zero-information filler phrase",
    Severity.ERROR,
)

# AI contextual phrases
_p(
    r"\b(In this context|In this regard|To this end|In light of|"
    r"With this in mind|Against this backdrop|"
    r"In the realm of|In the landscape of)\b",
    "AI contextual phrase",
)

# Em-dash overuse (ChatGPT signature)
_p(r"\s—\s", "Em-dash (ChatGPT signature -- consider comma or parenthetical)", Severity.INFO)

# Colon-explanation pattern: "Noun: Explanation"
_p(
    r"(?<=[.!?]\s)[A-Z][a-z]+\s[A-Z][a-z]+:\s[A-Z]",
    "Colon-explanation structure (AI pattern)",
    Severity.INFO,
)

# Numbered list in prose (AI loves lists)
_p(
    r"(?:^|\n)\s*(?:\d+\)|(?:First|Second|Third|Fourth|Fifth),)",
    "Enumerated prose list (AI structure)",
    Severity.INFO,
)

# Conclusion restating introduction verbatim
_p(
    r"\b(In summary|In conclusion|To summarize|To conclude|"
    r"Overall, this study|This paper has demonstrated|"
    r"The present study has shown)\b",
    "Formulaic conclusion opener",
    Severity.INFO,
)

# ChatGPT-specific patterns
_p(
    r"\b(As an AI|I cannot|I don't have access|"
    r"I hope this helps|Feel free to|Let me know if)\b",
    "Direct AI self-reference (critical)",
    Severity.CRITICAL,
)

# Excessive qualification
_p(
    r"\b(It is essential to understand that|"
    r"It is necessary to emphasize that|"
    r"It must be acknowledged that|"
    r"It cannot be overstated that)\b",
    "Excessive qualification (AI filler)",
)


@dataclass
class AIPatternChecker:
    """Regex-based detector for AI-typical writing patterns."""

    name: str = "ai_patterns"
    description: str = "Detects AI-generated writing patterns (regex + word lists)"

    def check(self, text: str, *, lines: list[str] | None = None) -> CheckerResult:
        if lines is None:
            lines = text.split("\n")

        issues: list[Issue] = []
        pattern_counts: dict[str, int] = {}

        for line_num, line in enumerate(lines, 1):
            for pattern, desc, severity in _PATTERNS:
                for m in pattern.finditer(line):
                    issues.append(Issue(
                        checker=self.name,
                        severity=severity,
                        line=line_num,
                        message=desc,
                        match=m.group()[:60],
                        context=line.strip()[:100],
                    ))
                    pattern_counts[desc] = pattern_counts.get(desc, 0) + 1

        # Compute AI pattern density (issues per 1000 words)
        word_count = len(text.split())
        density = (len(issues) / max(word_count, 1)) * 1000

        return CheckerResult(
            checker_name=self.name,
            issues=tuple(issues),
            metrics={
                "total_flags": len(issues),
                "density_per_1k_words": round(density, 2),
                "top_patterns": dict(
                    sorted(pattern_counts.items(), key=lambda x: -x[1])[:5]
                ),
            },
            summary=f"{len(issues)} AI patterns flagged ({density:.1f} per 1k words)",
        )
