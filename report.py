"""Report generator — formats checker results into Markdown and console output.

Produces:
  - Console summary (colored severity levels)
  - Markdown report file with full details
  - Overall AI-likelihood score (composite metric)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from checkers.base import CheckerResult, Issue, Severity

# ── Severity styling ─────────────────────────────────────────────────

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "[CRITICAL]",
    Severity.ERROR: "[ERROR]",
    Severity.WARNING: "[WARN]",
    Severity.INFO: "[INFO]",
}

_SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.ERROR: 1,
    Severity.WARNING: 2,
    Severity.INFO: 3,
}


def _severity_sort(issue: Issue) -> tuple[int, int]:
    return (_SEVERITY_ORDER.get(issue.severity, 9), issue.line)


# ── AI Likelihood Score ───────────────────────────────────────────────

def compute_ai_score(results: list[CheckerResult]) -> dict[str, float | str]:
    """Compute composite AI-likelihood score from all checker results.

    Score 0-100:
      0-20:  Very likely human-written
      20-40: Mostly human, minor AI patterns
      40-60: Mixed signals — needs human review
      60-80: Strong AI signals detected
      80-100: Very likely AI-generated
    """
    score = 0.0
    breakdown: dict[str, float] = {}

    for result in results:
        metrics = result.metrics
        checker = result.checker_name
        contribution = 0.0

        if checker == "ai_patterns":
            density = metrics.get("density_per_1k_words", 0)
            contribution = min(density * 3, 25)  # max 25 from patterns

        elif checker == "burstiness":
            cv = metrics.get("cv_sentence_length")
            if cv is not None:
                if cv < 0.25:
                    contribution = 20
                elif cv < 0.35:
                    contribution = 12
                elif cv < 0.50:
                    contribution = 5
                # cv >= 0.50 is human-like

        elif checker == "vocabulary":
            hapax = metrics.get("hapax_ratio", 0.6)
            if hapax < 0.40:
                contribution = 15
            elif hapax < 0.50:
                contribution = 8

        elif checker == "readability":
            # Not a strong signal alone, just a modifier
            pass

        elif checker == "hedging":
            density = metrics.get("hedge_density_per_1k", 0)
            stacked = metrics.get("by_category", {}).get("stacked_hedge", 0)
            contribution = min(density * 0.3 + stacked * 5, 15)

        elif checker == "passive_voice":
            ratio = metrics.get("passive_ratio", 0)
            if ratio > 0.50:
                contribution = 5

        elif checker == "repetition":
            intro_sim = metrics.get("intro_conclusion_similarity", 0)
            contribution = min(intro_sim * 30, 10)

        elif checker == "structure":
            undefined = len(metrics.get("undefined_acronyms", []))
            citation_density = metrics.get("citation_density_per_500w", 2.0)
            if citation_density < 0.5:
                contribution += 5
            contribution += min(undefined * 0.5, 5)
            contribution = min(contribution, 10)

        elif checker == "claims":
            vague = metrics.get("vague_attributions", 0)
            contribution = min(vague * 3, 10)

        breakdown[checker] = round(contribution, 1)
        score += contribution

    score = min(100, max(0, score))

    if score < 20:
        label = "Very likely human-written"
    elif score < 40:
        label = "Mostly human, minor AI patterns"
    elif score < 60:
        label = "Mixed signals -- needs human review"
    elif score < 80:
        label = "Strong AI signals detected"
    else:
        label = "Very likely AI-generated"

    return {
        "score": round(score, 1),
        "label": label,
        "breakdown": breakdown,
    }


# ── Console Output ────────────────────────────────────────────────────

def print_console_summary(
    results: list[CheckerResult],
    ai_score: dict[str, float | str],
    source: str = "",
) -> None:
    """Print a concise summary to the console."""
    print("\n" + "=" * 70)
    print(f"  AI STYLE CHECKER REPORT -- {source}")
    print("=" * 70)

    total_issues = sum(len(r.issues) for r in results)
    by_severity: dict[Severity, int] = {}
    for r in results:
        for issue in r.issues:
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

    print(f"\n  AI Likelihood Score: {ai_score['score']}/100 — {ai_score['label']}")
    print(f"  Total issues: {total_issues}")
    for sev in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO]:
        count = by_severity.get(sev, 0)
        if count:
            print(f"    {_SEVERITY_EMOJI[sev]}: {count}")

    print("\n  Checker summaries:")
    for r in results:
        print(f"    {r.checker_name:20s}  {r.summary}")

    # Score breakdown
    breakdown = ai_score.get("breakdown", {})
    if breakdown:
        print("\n  Score breakdown:")
        for checker, contrib in sorted(breakdown.items(), key=lambda x: -x[1]):
            filled = int(contrib)
            bar = "#" * filled + "." * (25 - filled)
            print(f"    {checker:20s}  {bar} {contrib:.1f}")

    print("\n" + "=" * 70)

    # Top 10 most severe issues
    all_issues = []
    for r in results:
        all_issues.extend(r.issues)
    all_issues.sort(key=_severity_sort)

    if all_issues:
        print("\n  Top issues (up to 15):")
        for issue in all_issues[:15]:
            loc = f"L{issue.line}" if issue.line > 0 else "global"
            print(f"    {_SEVERITY_EMOJI[issue.severity]} {loc:>6s}: {issue.message[:80]}")
            if issue.match:
                print(f"           match: '{issue.match}'")
        if len(all_issues) > 15:
            print(f"    ... and {len(all_issues) - 15} more issues")
    print()


# ── Markdown Report ───────────────────────────────────────────────────

def generate_markdown_report(
    results: list[CheckerResult],
    ai_score: dict[str, float | str],
    source: str = "",
    output_path: Path | None = None,
) -> str:
    """Generate a full Markdown report."""
    lines: list[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# AI Style Checker Report")
    lines.append(f"")
    lines.append(f"**Source:** `{source}`")
    lines.append(f"**Date:** {now}")
    lines.append(f"**AI Likelihood Score:** {ai_score['score']}/100 — {ai_score['label']}")
    lines.append("")

    # Score breakdown table
    lines.append("## Score Breakdown")
    lines.append("")
    lines.append("| Checker | Contribution | Details |")
    lines.append("|---------|-------------|---------|")
    breakdown = ai_score.get("breakdown", {})
    for checker, contrib in sorted(breakdown.items(), key=lambda x: -x[1]):
        # Find the matching result for summary
        summary = next((r.summary for r in results if r.checker_name == checker), "")
        lines.append(f"| {checker} | {contrib:.1f} | {summary} |")
    lines.append("")

    # Issue summary
    total_issues = sum(len(r.issues) for r in results)
    lines.append(f"## Issues Summary ({total_issues} total)")
    lines.append("")

    for sev in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO]:
        count = sum(1 for r in results for i in r.issues if i.severity == sev)
        if count:
            lines.append(f"- **{sev.value.upper()}**: {count}")
    lines.append("")

    # Per-checker details
    for result in results:
        lines.append(f"## {result.checker_name}")
        lines.append("")
        lines.append(f"*{result.summary}*")
        lines.append("")

        # Metrics
        if result.metrics:
            lines.append("### Metrics")
            lines.append("")
            for key, value in result.metrics.items():
                if isinstance(value, dict):
                    lines.append(f"- **{key}:**")
                    for k, v in value.items():
                        lines.append(f"  - {k}: {v}")
                elif isinstance(value, list) and len(value) > 10:
                    lines.append(f"- **{key}:** [{len(value)} items]")
                else:
                    lines.append(f"- **{key}:** {value}")
            lines.append("")

        # Issues
        if result.issues:
            lines.append("### Issues")
            lines.append("")
            for issue in sorted(result.issues, key=_severity_sort):
                loc = f"L{issue.line}" if issue.line > 0 else "global"
                lines.append(f"- **{issue.severity.value.upper()}** ({loc}): {issue.message}")
                if issue.match:
                    lines.append(f"  - Match: `{issue.match}`")
                if issue.context:
                    lines.append(f"  - Context: `{issue.context}`")
                if issue.suggestion:
                    lines.append(f"  - Suggestion: {issue.suggestion}")
            lines.append("")

    report = "\n".join(lines)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")

    return report
