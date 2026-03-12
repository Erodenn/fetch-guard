# Scope: Phase 1 — Core Pipeline with Injection Defense

## Summary

The core fetch → sanitize → extract → guard → format pipeline. Takes a URL, returns clean markdown with injection safety scanning. No metadata extraction or JS rendering yet — those are Phase 2 and 3.

## What It Does

- Fetches a URL via HTTP with configurable timeout (default 180s), following redirects, with a sensible User-Agent
- Sanitizes HTML by removing hidden content vectors (display:none, off-screen CSS, non-printing unicode, aria-hidden) before extraction; includes a tally of removed elements in the status header
- Extracts article body as clean markdown via trafilatura
- Generates a random hex salt per invocation and wraps extracted content in salted tags (e.g., `<fetch-content-a3f7b2>`)
- Scans extracted text for injection patterns: system prompt overrides, role-play instructions, ignore-previous patterns, hidden instruction markers, base64-encoded instructions, and structural fakes (e.g., `<system>`, `</instructions>`, fake CLAUDE.md blocks)
- Outputs a status header (URL, timestamp, risk flag OK/INJECTION WARNING, sanitization tally), then the salted markdown body
- `--strict` flag: exits nonzero on high-risk injection detection instead of just flagging
- `--max-words N`: hard cut at the Nth word (no sentence boundary logic)
- Checks for missing dependencies at startup and prints install instructions instead of a traceback

## What It Does Not Do

- No metadata extraction (Phase 2)
- No `/llms.txt` preflight check (Phase 2)
- No JavaScript rendering / Playwright (Phase 3)
- No caching or file storage
- No context window truncation beyond `--max-words`

## Inputs

- URL (positional, required)
- `--timeout N` — seconds (default 180)
- `--max-words N` — optional hard word cap
- `--strict` — exit nonzero on high-risk injection detection

## Outputs

Stdout only. A single block containing:

1. **Status header** — URL, fetch timestamp, risk flag (OK / INJECTION WARNING), sanitization tally
2. **Article body** — clean markdown wrapped in `<fetch-content-SALT>` tags

Exit code 0 on success (or flag-only injection warning). Nonzero on `--strict` with high-risk detection, or on fetch failure.

## Environment & Constraints

- Python 3.x, runs via `python .claude/skills/fetch/scripts/fetch.py <url> [options]`
- Git Bash on Windows — utf-8 explicit everywhere
- Dependencies: `trafilatura`, `requests`, `beautifulsoup4`
- No external APIs or paid services
- Script must be self-contained in `fetch/scripts/`

## Open Questions

- Exact User-Agent string — should it identify as a bot, or use a browser-like UA?
- Should `--strict` exit code be 1 (generic failure) or a dedicated code (e.g., 2) to distinguish injection from fetch errors?
