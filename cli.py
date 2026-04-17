"""CLI entry point for ai_style_checker.

Usage:
    # Check a single file
    python -m ai_style_checker manuscript.qmd

    # Check with specific checkers only
    python -m ai_style_checker manuscript.qmd --checkers ai_patterns,burstiness

    # Output report to file
    python -m ai_style_checker manuscript.qmd -o report.md

    # Check all .qmd files in a directory
    python -m ai_style_checker papers/ --glob "*.qmd"

    # JSON output for CI integration
    python -m ai_style_checker manuscript.qmd --format json

    # Fail CI if AI score exceeds threshold
    python -m ai_style_checker manuscript.qmd --threshold 40
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from checkers import ALL_CHECKERS
from checkers.base import CheckerResult
from report import compute_ai_score, generate_markdown_report, print_console_summary


def _strip_yaml_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from .qmd/.md files."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].lstrip("\n")
    return text


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai_style_checker",
        description="Detect AI-generated writing patterns in academic manuscripts",
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to a file (.qmd, .md, .txt, .tex) or directory",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output path for Markdown report (default: stdout only)",
    )
    parser.add_argument(
        "--checkers",
        type=str,
        default=None,
        help="Comma-separated list of checkers to run (default: all)",
    )
    parser.add_argument(
        "--format",
        choices=["console", "markdown", "json"],
        default="console",
        help="Output format (default: console)",
    )
    parser.add_argument(
        "--glob",
        type=str,
        default="*.qmd",
        help="Glob pattern when input is a directory (default: *.qmd)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Exit with code 1 if AI score exceeds this threshold (for CI)",
    )
    parser.add_argument(
        "--strip-frontmatter",
        action="store_true",
        default=True,
        help="Strip YAML frontmatter from .qmd/.md files (default: true)",
    )
    parser.add_argument(
        "--no-strip-frontmatter",
        action="store_false",
        dest="strip_frontmatter",
    )
    return parser.parse_args()


def _resolve_files(input_path: str, glob_pattern: str) -> list[Path]:
    """Resolve input to a list of files."""
    p = Path(input_path)
    if p.is_file():
        return [p]
    if p.is_dir():
        files = sorted(p.rglob(glob_pattern))
        if not files:
            print(f"No files matching '{glob_pattern}' in {p}", file=sys.stderr)
            sys.exit(1)
        return files
    print(f"Input not found: {input_path}", file=sys.stderr)
    sys.exit(1)


def _select_checkers(names: str | None) -> list:
    """Filter checkers by name."""
    if names is None:
        return [cls() for cls in ALL_CHECKERS]
    requested = {n.strip().lower() for n in names.split(",")}
    selected = []
    for cls in ALL_CHECKERS:
        instance = cls()
        if instance.name in requested:
            selected.append(instance)
    if not selected:
        available = ", ".join(cls().name for cls in ALL_CHECKERS)
        print(f"No matching checkers. Available: {available}", file=sys.stderr)
        sys.exit(1)
    return selected


def check_file(
    filepath: Path,
    checkers: list,
    strip_frontmatter: bool = True,
) -> tuple[list[CheckerResult], dict]:
    """Run all checkers on a single file. Return results and AI score."""
    text = filepath.read_text(encoding="utf-8", errors="replace")
    if strip_frontmatter and filepath.suffix in (".qmd", ".md"):
        text = _strip_yaml_frontmatter(text)

    lines = text.split("\n")
    results: list[CheckerResult] = []

    for checker in checkers:
        result = checker.check(text, lines=lines)
        results.append(result)

    ai_score = compute_ai_score(results)
    return results, ai_score


def main() -> None:
    args = _parse_args()
    files = _resolve_files(args.input, args.glob)
    checkers = _select_checkers(args.checkers)

    exit_code = 0

    for filepath in files:
        results, ai_score = check_file(filepath, checkers, args.strip_frontmatter)

        source = str(filepath)

        if args.format == "json":
            output = {
                "file": source,
                "ai_score": ai_score,
                "results": [
                    {
                        "checker": r.checker_name,
                        "summary": r.summary,
                        "metrics": r.metrics,
                        "issue_count": len(r.issues),
                        "issues": [
                            {
                                "severity": i.severity.value,
                                "line": i.line,
                                "message": i.message,
                                "match": i.match,
                                "context": i.context,
                                "suggestion": i.suggestion,
                            }
                            for i in r.issues
                        ],
                    }
                    for r in results
                ],
            }
            print(json.dumps(output, indent=2))

        elif args.format == "markdown":
            report = generate_markdown_report(results, ai_score, source)
            print(report)

        else:
            print_console_summary(results, ai_score, source)

        # Write report file if requested
        if args.output:
            out_path = Path(args.output)
            if len(files) > 1:
                out_path = out_path.parent / f"{filepath.stem}_report.md"
            generate_markdown_report(results, ai_score, source, out_path)
            print(f"Report written to: {out_path}")

        # Threshold check for CI
        if args.threshold is not None and ai_score["score"] > args.threshold:
            print(
                f"\nFAIL: AI score {ai_score['score']} exceeds threshold {args.threshold}",
                file=sys.stderr,
            )
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
