# Scope: Phase 2 — Metadata Layer

## Summary

Adds structured metadata extraction, `/llms.txt` preflight checking, and external link extraction to the fetch pipeline. Metadata gives Claude structured context (title, author, date) alongside the markdown body; `/llms.txt` provides an LLM-optimized alternative for domain root fetches; link extraction maps the page's external references.

## What It Does

- **MetadataExtractor** — uses extruct to pull JSON-LD, Open Graph, and `<meta>` tags from the raw HTML, then normalizes into a unified schema with consistent top-level keys: `title`, `author`, `date`, `description`, `canonical_url`, `image`. Missing fields are `null`, not omitted. Best-guess resolution when multiple sources disagree (JSON-LD > OG > meta tags as priority order).
- **LlmsTxtChecker** — before fetching, sends a HEAD request to `{domain_root}/llms.txt`. If it exists (200, non-empty), and the requested URL is the domain root, replaces the normal fetch entirely with the `/llms.txt` content. For non-root URLs, notes the existence of `/llms.txt` in the status header but fetches the requested page normally.
- **External link extraction** — scans extracted content for external links. Default: deduplicated list of external domains. `--links full` flag: all external URLs with anchor text, grouped by domain.
- **Output change** — metadata JSON block appended after the salted body. Status header updated to include `/llms.txt` note when applicable.

## What It Does Not Do

- No raw extruct pass-through — unified schema only (keeps output predictable)
- No `/llms.txt` replacement for non-root URLs
- No JavaScript rendering (Phase 3)
- No caching of `/llms.txt` results between invocations
- No recursive link following or crawling

## Inputs

Existing CLI args unchanged, plus:
- `--links full` — optional flag for verbose link extraction (default: unique domains only)

## Outputs

Stdout output block becomes:

1. **Status header** — existing fields, plus `/llms.txt: available` note when present on the domain
2. **Article body** — salted markdown (unchanged from Phase 1), OR `/llms.txt` content when replacing a root URL fetch
3. **Metadata block** — JSON with unified schema keys
4. **External links** — domain list or full link list depending on flag

## Environment & Constraints

- Same as Phase 1: Python 3.x, Git Bash, Windows, utf-8
- New dependency: `extruct` (plus its transitive deps: `mf2py`, `w3lib`, etc.)
- Dependency check at startup must cover `extruct` alongside existing deps
- `/llms.txt` HEAD request should respect the same `--timeout` as the main fetch, but use a short ceiling (e.g. 5s) so it doesn't double the total wait time

## Open Questions

- **llms.txt content format** — should `/llms.txt` content go through the sanitizer and injection guard, or pass through raw? (It's meant to be LLM-friendly, but trust-but-verify seems wise.)
- **Metadata extraction on llms.txt replacement** — when `/llms.txt` replaces the page fetch, there's no HTML to extract metadata from. Emit an empty metadata block, or skip the section entirely?
- **extruct error handling** — extruct can be noisy on malformed HTML. Swallow errors silently and return partial metadata, or surface warnings?
