# Fetch

Fetch URLs and return clean, LLM-ready markdown with structured metadata and prompt injection defense. Works as a standalone CLI, a [Claude Code](https://github.com/anthropics/claude-code) skill, or an MCP server.

## What It Does

The pipeline takes a URL and produces structured output: sanitized markdown body, metadata (Open Graph, JSON-LD, meta tags), external links, and injection safety analysis. It handles HTML, JSON, XML/RSS, CSV, and plain text content types.

Three layers of defense protect against prompt injection:
- **Sanitization** strips hidden elements, offscreen content, and non-printing characters before extraction
- **Injection scanning** checks extracted content against 15 regex patterns for known prompt injection techniques
- **Session-salted tags** wrap the output body with random hex boundaries to prevent tag spoofing

Edge case detection identifies bot blocks, paywalls, and login walls. Bot blocks trigger one automatic retry with a browser User-Agent before reporting.

## Install

Python 3.9+. Install dependencies:

```bash
pip install requests beautifulsoup4 trafilatura extruct
```

For the MCP server, also install:

```bash
pip install mcp
```

For JavaScript rendering (optional):

```bash
pip install playwright && playwright install chromium
```

## Usage

### CLI

```bash
python fetch/scripts/fetch.py <url> [options]
```

| Flag | Default | Description |
|---|---|---|
| `--timeout N` | 180 | Request timeout in seconds |
| `--max-words N` | none | Word cap on extracted body content |
| `--js` | off | Use Playwright for JS-rendered pages |
| `--strict` | off | Exit code 2 on high-risk injection |
| `--links MODE` | `domains` | `domains` for unique external domains, `full` for all URLs with anchor text |

### MCP Server

Add to your MCP client config (e.g. `.mcp.json` for Claude Code):

```json
{
  "mcpServers": {
    "fetch": {
      "command": "python",
      "args": ["fetch/scripts/server.py"]
    }
  }
}
```

Or use the console entry point after `pip install`:

```json
{
  "mcpServers": {
    "fetch": {
      "command": "fetch-mcp"
    }
  }
}
```

The server exposes a single `fetch` tool over stdio with the same parameters as the CLI. Returns structured JSON.

### Claude Code Skill

Copy the `fetch/` directory to `.claude/skills/fetch/` in your project. The skill is defined in `fetch/SKILL.md`.

## Output

CLI output contains five sections:

1. **Status header**: URL, timestamp, risk flag (OK / INJECTION WARNING), sanitization tally, edge case info
2. **Body**: clean markdown wrapped in session-salted tags
3. **Metadata**: structured JSON (title, author, date, canonical URL, Open Graph, JSON-LD)
4. **External links**: domain list or full URL breakdown
5. **Injection details**: pattern match specifics (only present when injection detected)

MCP server returns the same data as a structured JSON dict.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Fetch error (network failure, no content) |
| 2 | High-risk injection detected (`--strict` only) |

## Architecture

```
URL → FetchClient → EdgeDetector → HtmlSanitizer → ContentExtractor
    → MetadataExtractor → InjectionGuard → OutputFormatter → stdout
```

All pipeline modules live in `fetch/scripts/`. Each module is a single-responsibility unit with a public function as its interface. `pipeline.py` contains the shared pipeline logic used by both the CLI (`fetch.py`) and the MCP server (`server.py`).

The pipeline checks for `/llms.txt` at the domain root before full fetch. If the URL is a domain root and `/llms.txt` exists, that content replaces the normal fetch.

## Development

```bash
# Run tests (217 tests, all mocked)
pytest

# Run live integration tests (hits real URLs)
pytest -m live

# Lint
ruff check fetch/scripts/ tests/
```

## License

MIT

## Acknowledgements

Built with [Claude Code](https://github.com/anthropics/claude-code).
