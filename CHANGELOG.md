# Changelog

## 2026.04.2 (2026-04-17)

### Added
- Sentence-opener diversity checker (POS classification, Shannon entropy)
- Paragraph entropy variance checker
- Personal writing fingerprint (14 stylometric features + sentence-transformers centroid)
- Structure checker contribution to composite score
- Numeric citation pattern `[12]` in structure checker
- Adjectival past-participle exclusion in passive voice checker

### Fixed
- Capped per-pattern density to prevent single pattern (em-dashes) dominating score
- Replaced hardcoded `year > 2026` with `datetime.now().year`
- Only strip YAML frontmatter for `.qmd`/`.md` files (not `.tex`)
- Downgraded formulaic transitions from WARNING to INFO
- Removed false-positive terms: `landscape`, `paradigm shift`, `state-of-the-art`
- Include `context` field in JSON output for pipeline integration

## 2026.04.1 (2026-04-17)

### Added
- Initial release with 9 checkers: ai_patterns, burstiness, vocabulary, readability, hedging, passive_voice, structure, repetition, claims
- Composite AI likelihood score (0-100)
- Console, Markdown, and JSON output formats
- CI-friendly `--threshold` flag
- Sample AI-generated and human-written texts
- 14 tests
