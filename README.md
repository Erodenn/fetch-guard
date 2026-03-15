# Fetch Guard

[![PyPI](https://img.shields.io/pypi/v/fetch-guard)](https://pypi.org/project/fetch-guard/)
[![CI](https://github.com/Erodenn/fetch-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Erodenn/fetch-guard/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/fetch-guard)](https://pypi.org/project/fetch-guard/)
[![License: MIT](https://badgen.net/github/license/Erodenn/fetch-guard)](LICENSE)

<a href="https://glama.ai/mcp/servers/@Erodenn/fetch-guard">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@Erodenn/fetch-guard/badge" alt="fetch-guard MCP server" />
</a>

An [MCP](https://modelcontextprotocol.io/) server and CLI tool that fetches URLs and returns clean, LLM-ready markdown. A purpose-built extraction pipeline sanitizes HTML, pulls structured metadata, detects prompt injection attempts, and handles the edge cases that break naive fetchers: bot blocks, paywalls, login walls, non-HTML content types, and pages that require JavaScript to render.

The core problem is straightforward: LLMs need web content, but raw HTML is noisy and potentially hostile. Fetched pages can contain hidden text, invisible Unicode, off-screen elements, and outright prompt injection attempts embedded in the content itself. This pipeline strips all of that before the content reaches the model.

Three layers handle the injection defense specifically:

1. **Pre-extraction sanitization** removes hidden elements (`display:none`, `visibility:hidden`, `opacity:0`, `font-size:0`, `transform:scale(0)`, `clip:rect(0,0,0,0)`, zero-height overflow containers, and elements with matching foreground and background colors), elements hidden via CSS class/ID rules in `<style>` tags, off-screen positioned content, `aria-hidden` elements, `<noscript>` and `<template>` tags, and 26 categories of non-printing Unicode characters including bidi isolates and Unicode Tags. This happens before content extraction, so trafilatura never sees the attack vectors.
2. **Pattern scanning** runs a four-phase scan against the extracted text and metadata fields. Phase one applies 50 compiled regex patterns covering system prompt overrides, ignore-previous instructions, role injection, fake conversation tags, and hidden instruction markers, in English, Spanish, French, German, Japanese, Simplified Chinese, and Portuguese. Phase two normalizes the text via NFKC and confusable-character mapping, then rescans to catch homoglyph bypasses (Cyrillic or mathematical Unicode characters substituted for Latin, etc.). Phase three finds base64, hex-encoded, and URL percent-encoded blocks, decodes them, and scans against high-severity patterns. Phase four decodes the full document with ROT13 and scans against high-severity patterns. Metadata fields (title, description, og:title, etc.) are scanned independently with matches namespaced to their source field.
3. **Session-salted output wrapping** generates a random 8-character hex salt per invocation and wraps the body in `<fetch-content-{salt}>` tags. Since the salt is unpredictable, injected content cannot spoof the wrapper boundaries.

## One Tool

This is a single-tool MCP server. It exposes one tool — `fetch` — that runs a full extraction pipeline behind a consistent interface. No tool selection, no routing, no multi-step workflows. One URL in, one structured result out, configurable via parameters.

## Testing

The test suite has two tiers.

**Unit tests** (424, all mocked — no network calls):

```bash
pytest
```

Every module has a corresponding test file. Tests are fully parametrized tables with explicit input/output pairs — no shared mutable state, no network, no filesystem side effects. CI runs the full suite on Python 3.10, 3.12, and 3.13 on every push and PR.

**Live integration tests** (54 entries, real network):

```bash
pytest -m live -v
```

Rather than hardcoded test functions, the live suite is data-driven: five YAML catalogs in `tests/catalogs/` define URL entries with typed assertions. A single parametrized runner (`test_catalog.py`) evaluates all of them.

| Catalog | Entries | What it covers |
|---|---|---|
| `html.yaml` | 13 | Metadata-rich pages, non-English content, redirects, government/academic sites |
| `injection.yaml` | 9 | OWASP cheat sheets, arXiv papers, controlled high-severity payload gist |
| `edge_cases.yaml` | 10 | Login walls (GitHub, Reddit, Steam), bot blocks (LinkedIn, Glassdoor, WSJ) |
| `content_types.yaml` | 12 | RSS/Atom feeds, GitHub API JSON, raw text files, XML sitemaps |
| `llms_txt.yaml` | 11 | Domains with `/llms.txt` (replaced vs. available), confirmed negatives |

Each entry can assert `min_body_length`, `injection_match_count_min`, `links_count_min`, `url_changed`, and exact field equality via dot-notation (e.g. `edge_cases.type: login_wall`). Entries can set `allow_fetch_error: true` for inherently flaky sources (bot-blocking sites) and `max_words` to bypass the size guard for large pages.

Live tests run automatically on release via a separate `live-tests.yml` workflow.

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Install

```bash
pip install fetch-guard
```

For JavaScript rendering (optional):

```bash
pip install 'fetch-guard[js]' && playwright install chromium
```

### Configure Your MCP Client

Add the following to your MCP client config. Works with Claude Code, Claude Desktop, Cursor, or any MCP-compatible client.

**Via uvx (recommended):**

```json
{
  "mcpServers": {
    "fetch-guard": {
      "command": "uvx",
      "args": ["fetch-guard"]
    }
  }
}
```

**Via pip install:**

```json
{
  "mcpServers": {
    "fetch-guard": {
      "command": "fetch-guard"
    }
  }
}
```

**From source:**

```json
{
  "mcpServers": {
    "fetch-guard": {
      "command": "python",
      "args": ["-m", "fetch_guard.server"]
    }
  }
}
```

**Via Docker:**

```json
{
  "mcpServers": {
    "fetch-guard": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "sterlsnyc/fetch-guard"]
    }
  }
}
```

> **Note:** The Docker image does not include Playwright. JavaScript rendering (`js: true`) is not available when running via Docker. Use the `uvx` or `pip` install if you need JS rendering.

### Verify

Ask your AI assistant to fetch any URL. If it returns structured content with a status header, metadata, and risk assessment, you're connected.

### CLI

```bash
fetch-guard-cli <url> [options]
# or: python -m fetch_guard.cli <url> [options]
```

| Flag | Default | Description |
|---|---|---|
| `--timeout N` | 180 | Request timeout in seconds |
| `--max-words N` | none | Word cap on extracted body content. Also disables the automatic size guard |
| `--js` | off | Use Playwright for JS-rendered pages |
| `--strict` | off | Exit code 2 on high-risk injection |
| `--links MODE` | `domains` | `domains` for unique external domains, `full` for all URLs with anchor text |
| `--header KEY:VALUE` | none | Custom HTTP header (repeatable) |

## Tool Parameters

The MCP `fetch` tool accepts these parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | The URL to fetch |
| `timeout` | integer | 180 | Request timeout in seconds. Ensures the tool always returns — no hanging fetches |
| `max_words` | integer | none | Word cap on extracted body content. Also disables the automatic size guard — use when you want explicit control over truncation without hitting the default limits |
| `strict` | boolean | false | When true and high-risk injection is detected, the response is marked as an error |
| `js` | boolean | false | Use Playwright for JavaScript-rendered pages (requires `fetch-guard[js]`) |
| `links` | string | `"domains"` | `"domains"` for unique external domains, `"full"` for all URLs with anchor text |
| `headers` | object | none | Custom HTTP headers as a key-value dict (e.g. `{"Authorization": "Bearer token"}`). Useful for GitHub's authenticated API and other endpoints requiring auth |

### Claude Code Skill

Copy `resources/fetch-guard/` to `.claude/skills/fetch-guard/` in your project, or use the standalone command file `resources/fetch-guard.md` as a Claude Code command.

## What It Does

The pipeline runs a 13-step sequence from URL to structured output:

1. **`/llms.txt` preflight.** Checks the domain root for `/llms.txt` before the full fetch. If the requested URL is a domain root and `/llms.txt` exists, that content replaces the normal HTML pipeline entirely. This respects the emerging convention for LLM-friendly site summaries.

2. **Fetch.** Static HTTP request via `requests`, or Playwright-driven browser rendering if `--js` is set. No automatic fallback between the two: `--js` is explicit opt-in.

3. **Edge detection.** Classifies the response for bot blocks (Cloudflare challenges, 403/429/503 with block signatures, LinkedIn's custom 999), paywalls (subscription prompts, premium overlays), and login walls (sign-in redirects, members-only patterns).

4. **Automatic retry.** Bot blocks trigger one retry with a full Chrome User-Agent string before reporting. Paywalls and login walls are reported immediately with no retry.

5. **Content-type routing.** Non-HTML responses get a fast path: JSON is rendered as a fenced code block, RSS/Atom feeds are parsed into structured summaries, CSV becomes a markdown table (capped at 2,000 rows), and plain text passes through directly. Binary content types are rejected.

6. **HTML sanitization.** Strips hidden elements (including extended CSS visibility techniques, color-matched text, and `<template>` tags), off-screen positioned content, `aria-hidden` nodes, `<noscript>` tags, and non-printing Unicode. Returns a tally of everything removed.

7. **Content extraction.** trafilatura converts sanitized HTML to markdown with link preservation.

8. **Metadata extraction.** Pulls title, author, date, description, canonical URL, and image from three sources in priority order: JSON-LD, Open Graph, then meta tags.

9. **Link extraction.** Two modes: `domains` returns a sorted list of unique external domains, `full` returns all external URLs grouped by domain with anchor text.

10. **Injection scanning.** Four-phase scan: original text against all 50 patterns (English + 6 additional languages), NFKC-normalized text for homoglyph bypasses, decode-and-scan for base64/hex/URL-percent-encoded payloads, and ROT13 whole-document scan. Metadata fields are scanned independently with matches namespaced to their source field. Each match records the pattern name, severity (high/medium), and a 60-character context snippet.

11. **Size guard + truncation.** By default, content over 2MB (pre-extraction) or 20KB (post-extraction) raises an error with a suggested `max_words` value. Setting `--max-words` disables both limits and truncates instead — use it when you want explicit control over what reaches the model.

12. **Salt wrapping.** The body gets wrapped in session-salted tags for defense-in-depth.

13. **Output formatting.** CLI produces five plaintext sections (status header, body, metadata, links, injection details). MCP server returns a structured JSON dict with the same data.

## Output

### CLI

Five sections, printed to stdout:

- **Status header:** URL, fetch timestamp, risk flag (`OK` or `INJECTION WARNING`), sanitization tally, edge case info if detected
- **Body:** clean markdown wrapped in `<fetch-content-{salt}>` tags
- **Metadata:** JSON block with title, author, date, description, canonical URL, image
- **External links:** domain list or full URL breakdown by domain
- **Injection details:** pattern name, severity, and context snippet for each match (only present when patterns detected)

### MCP Server

Returns a structured dict:

```
status, url, fetched_at, body, content_type, metadata, links, links_mode,
risk_level, injection_matches, edge_cases, sanitization,
llms_txt_available, llms_txt_replaced, js_rendered, js_hint,
retried, truncated_at
```

`status` is a quick-glance summary string designed to be readable without expanding the full result:

```
"OK | html"
"HIGH | html | edge:paywall | sanitized:193 | retried | truncated:500"
```

Always includes `risk` and `content_type`. Non-default values (`edge`, `sanitized > 0`, `retried`, `js`, `truncated`) are appended only when present.

When `--strict` is set and the risk level is `HIGH`, the CLI exits with code 2 and the MCP server raises an error response. The full result is still available in both cases.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Fetch error (network failure, empty response, binary content) |
| 2 | High-risk injection detected (`--strict` only) |

## Architecture

```
fetch_guard/
├── pipeline.py             # Core orchestration — 13-step sequence, shared by CLI and server
├── cli.py                  # CLI entry point — arg parsing, pipeline call, output
├── server.py               # MCP server — FastMCP wrapper over the same pipeline
│
├── http/                   # HTTP fetching layer
│   ├── client.py           # Static HTTP fetch via requests
│   ├── playwright.py       # JS rendering via Playwright (optional)
│   └── llms_txt.py         # /llms.txt preflight check
│
├── extraction/             # Content extraction and edge detection
│   ├── content.py          # trafilatura wrapper — HTML to markdown
│   ├── content_type.py     # Non-HTML routing — JSON, XML/RSS, CSV, plain text
│   ├── edges.py            # Bot block, paywall, login wall classification
│   ├── links.py            # External link extraction (domain list or full URLs)
│   └── metadata.py         # JSON-LD, Open Graph, meta tag extraction
│
├── security/               # Injection defense
│   ├── guard.py            # Salt generation, content wrapping, four-phase scan, metadata scan, merge API
│   ├── normalize.py        # NFKC + confusable-character normalization for homoglyph detection
│   ├── patterns.py         # 14 English + 36 multilingual compiled regex patterns — single source of truth
│   ├── multilingual_patterns.json  # Multilingual injection patterns (ES, FR, DE, JA, ZH, PT)
│   └── sanitizer.py        # Hidden element, CSS rule, color-match, and non-printing character removal
│
└── output/                 # Formatting
    └── formatter.py        # CLI output assembly
```

Each module is a single-responsibility unit with a public function as its interface. `pipeline.py` is the shared core: both `cli.py` and `server.py` call `pipeline.run()` and handle the result in their own way.

## Development

```bash
# Run tests (414 unit tests, all mocked — no network calls)
pytest

# Run live integration tests (hits real URLs)
pytest -m live

# Lint
ruff check fetch_guard/ tests/
```

CI runs on push and PR to `main` via GitHub Actions, testing against Python 3.10, 3.12, and 3.13.

## Acknowledgements

Developed with [Claude Code](https://claude.ai/code).

## License

[MIT](LICENSE)
