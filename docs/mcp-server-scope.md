# Scope: MCP Server Wrapper for Fetch Skill

## Summary
An MCP server that exposes the existing Fetch pipeline as a single `fetch` tool over stdio transport, returning structured results. Distributed as a pip/uvx-installable package alongside the existing CLI skill — both interfaces share the same pipeline code.

## What It Does
- Exposes a single `fetch` MCP tool with parameters mirroring the CLI flags: `url` (required), `timeout`, `max_words`, `strict`, `js`, `links`
- Returns structured content: discrete fields for `body`, `metadata`, `links`, `risk_level`, `injection_matches`, `edge_cases`, `sanitization_stats`, `llms_txt_available`, `js_hint`, `fetched_at`, `final_url`
- Wraps the existing pipeline modules directly (thin wrapper, no subprocess, no duplication)
- Communicates over stdio transport
- Installable via `pip install` / `uvx` with a console script entry point (e.g., `fetch-mcp-server`)
- Preserves the existing CLI (`python fetch.py <url>`) and skill (SKILL.md) as-is — no breaking changes

## What It Does Not Do
- No SSE or HTTP transport (stdio only)
- No additional tools beyond the single `fetch` tool (no separate `check_llms_txt`, `fetch_js`, etc.)
- No MCP resources or prompts
- No batch/crawl capabilities
- No new pipeline features — the MCP server is a wrapper, not a feature expansion

## Inputs
- MCP tool call with parameters: `url` (string, required), `timeout` (int, optional), `max_words` (int, optional), `strict` (bool, optional), `js` (bool, optional), `links` (enum: `domains`|`full`, optional)

## Outputs
- MCP tool result with structured JSON containing all pipeline outputs as discrete fields
- On `strict` mode with high-risk injection: returns the result with `risk_level: "HIGH"` and `is_error: true` (MCP error semantics) rather than an exit code

## Environment & Constraints
- Python 3.9+ (matches existing pipeline)
- Dependencies: existing pipeline deps + `mcp` (official Python MCP SDK)
- Must work on Windows (Git Bash, CMD, PowerShell) and Unix
- UTF-8 enforcement carries over from existing pipeline
- Entry point in `pyproject.toml` as console script

## Open Questions
- **Package name**: `fetch-skill` is the current project name — should the pip package be `fetch-mcp` or `claude-fetch` or keep `fetch-skill`? (likely taken on PyPI, needs checking)
- **Server file location**: `fetch/server.py` alongside the scripts dir, or `fetch/scripts/server.py` inside it?
- **Refactoring the pipeline**: the current `fetch.py` mixes CLI arg parsing with pipeline orchestration — the MCP wrapper needs the pipeline logic without argparse. This likely means extracting a `pipeline.py` function that both `fetch.py` and `server.py` call
- **Session salt behavior**: CLI generates a new salt per invocation. MCP should do the same per tool call — confirm this carries over naturally
