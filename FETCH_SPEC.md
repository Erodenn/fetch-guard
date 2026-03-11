# Spec: `/fetch` — LLM-Ready Web Fetching Skill

## Summary

A Claude Code skill that replaces the raw `curl` web fetch pattern with a pipeline that extracts clean, readable markdown from any URL and packages structured metadata alongside it — with prompt injection defense built in from day one.

## What It Does

- Fetches a URL via HTTP with a configurable timeout (default: 180s)
- Strips HTML boilerplate and extracts article body as clean markdown
- Extracts structured page metadata (title, author, published date, Open Graph, JSON-LD)
- Sanitizes hidden content vectors (invisible text, off-screen CSS, non-printing unicode) before extraction
- Wraps output in session-salted tags and scans for injection patterns, alerting Claude if suspicious content is detected
- Checks for `/llms.txt` at the domain root before a full fetch; uses it if available
- Falls back to Playwright for JavaScript-rendered pages when static extraction fails

## What It Does Not Do

- Does not render JavaScript by default — Playwright is an explicit opt-in
- Does not cache or store fetched content
- Does not filter or truncate content based on Claude's context window — that is the caller's responsibility
- Does not use any external APIs or paid services

## Inputs

- URL (required)
- `--timeout N` — request timeout in seconds (default: 180; agents should override with ~30 for most uses)
- `--js` — opt-in flag to route through Playwright for JS-rendered pages
- `--max-words N` — optional word cap on extracted body content

## Outputs

A single formatted block containing:
1. **Fetch status header** — URL, fetch timestamp, risk flag (OK / INJECTION WARNING)
2. **Article body** — clean markdown from trafilatura, wrapped in session-salted tags
3. **Metadata block** — structured JSON (title, author, date, canonical URL, Open Graph, JSON-LD, external domain list)

## Architecture Suggestions

### Core Services

| Name | Role |
|---|---|
| `FetchClient` | HTTP layer — handles timeout, User-Agent, redirects, llms.txt preflight |
| `HtmlSanitizer` | Pre-extraction pass — removes hidden text vectors (display:none, off-screen CSS, non-printing unicode) |
| `ContentExtractor` | Wraps trafilatura — article extraction and markdown conversion |
| `MetadataExtractor` | Wraps extruct — normalizes JSON-LD, Open Graph, and meta tags into a unified dict |
| `InjectionGuard` | Generates salted session tags, scans extracted text for injection patterns, emits risk assessment |
| `OutputFormatter` | Assembles final output block from all pipeline stages |

### Supporting Helpers

| Name | Role |
|---|---|
| `LlmsTxtChecker` | HEAD + GET for `/llms.txt` at the domain root; returns content or None |
| `PlaywrightFetcher` | JS-rendered HTML via Playwright — isolated, only invoked with `--js` |
| `InjectionPatterns` | Constant registry of injection detection regex patterns |

### Entry Point

`fetch.py` — CLI script, parses args, runs the pipeline, prints to stdout. Claude reads stdout.

## Phased Plan

### Phase 1 — Core Pipeline with Injection Defense

Functional fetch → sanitize → extract → guard → format pipeline.
Injection defense is first-class here, not added later:

- `FetchClient`, `HtmlSanitizer`, `ContentExtractor`, `InjectionGuard`, `OutputFormatter`
- Session-salted tag generation and injection pattern scanning included from the start
- Markdown body output only (no metadata JSON yet)
- Timeout and `--max-words` flags

### Phase 2 — Metadata Layer

Structured JSON output alongside the markdown body:

- `MetadataExtractor` (extruct integration)
- `LlmsTxtChecker` — preflight check before full fetch
- External domain extraction from links

### Phase 3 — JavaScript Fallback

Handle JS-rendered pages and tighten edge cases:

- `PlaywrightFetcher` behind `--js` flag
- Auto-escalation suggestion in output when trafilatura returns empty content
- Edge case handling: paywalls, login walls, bot detection responses

## Environment & Constraints

- Python 3.x; runs via `python fetch.py` in Git Bash
- Lives in `~/.claude/skills/fetch/` — global, available across all Claude Code sessions
- Key dependencies: `trafilatura`, `extruct`, `requests`, `beautifulsoup4`
- Playwright dependency only required if `--js` is used; graceful error if not installed
- Script must check for missing dependencies and emit a clear install message, not a traceback
- Output goes to stdout only; no files written unless explicitly instructed by the caller
- Windows-compatible paths and encoding throughout (`utf-8` explicit)

## Open Questions

- Should `InjectionGuard` emit a flag only, or optionally block (exit nonzero) on high-risk detection?
- Word cap (`--max-words`) — truncate at sentence boundary or hard cut?
- Link extraction verbosity — top N external domains only, or full list?
