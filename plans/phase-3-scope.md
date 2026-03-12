# Scope: Phase 3 — JavaScript Fallback & Edge Case Handling

## Summary

Adds Playwright-based JS rendering behind a `--js` flag, auto-escalation hints when static extraction fails, and detection + simple retry logic for paywalls, login walls, and bot blocks.

## What It Does

- **PlaywrightFetcher** — headless Chromium via Playwright, invoked only with `--js`. Fetches the URL, waits for network idle, returns rendered HTML. Output feeds into the existing sanitize → extract → guard → format pipeline
- **Auto-escalation hint** — when trafilatura returns empty/no content on a static fetch (without `--js`), the output includes a note suggesting `--js` retry. No automatic retry
- **Edge case detection** — inspects response for signals of paywalls, login walls, and bot detection (status codes, page content patterns, common block page signatures). On detection: tries one simple retry with an alternative User-Agent. If still blocked, reports the detected condition in the status header
- **Graceful Playwright absence** — if `--js` is used but Playwright isn't installed, emits a clear install message and exits, no traceback

## What It Does Not Do

- No automatic `--js` fallback — hint only, user/Claude decides
- No headed/GUI browser mode — always headless
- No cookie injection, session reuse, or login automation
- No CAPTCHA solving
- No Playwright install management (user runs `playwright install` themselves)

## Inputs

Existing CLI args unchanged, plus:
- `--js` — opt-in flag to use Playwright for JS rendering

## Outputs

Same output structure as Phase 2, with additions:
- **Status header** gains `js_rendered: true` when `--js` was used, and edge case flags (`paywall_detected`, `bot_block_detected`, `login_wall_detected`, `retry_attempted`) when applicable
- **Escalation hint** appended after body when static extraction returns empty: suggests re-running with `--js`

## Environment & Constraints

- Same as Phase 1/2: Python 3.x, Git Bash, Windows, utf-8
- New optional dependency: `playwright` (only required when `--js` is used)
- Playwright Chromium browser must be installed separately (`playwright install chromium`)
- Dependency check at startup must cover `playwright` only when `--js` is passed — don't require it for normal use
- Playwright timeout should respect `--timeout` but cap at a reasonable ceiling for page load + network idle

## Open Questions

- **Network idle wait strategy** — `networkidle` vs `domcontentloaded` + fixed delay? `networkidle` is more reliable but slower on pages with persistent connections (analytics, websockets)
- **Bot detection patterns** — initial set of heuristics (Cloudflare challenge page, common 403 bodies, "please verify you are human" text). How comprehensive should the first pass be?
