"""Assembles the status header, salted body, metadata, and links into the final stdout output."""

import json

from injection_guard import RISK_OK


def format_output(result, salted_body):
    """Build the final output string from a pipeline result dict.

    Args:
        result: The dict returned by pipeline.run().
        salted_body: The body content already wrapped in salted tags.
    """
    # Status line
    risk = result["risk_level"]
    matches = result["injection_matches"]
    match_count = len(matches)
    if risk == RISK_OK:
        status = "OK"
    else:
        status = f"INJECTION WARNING ({match_count} pattern match{'es' if match_count != 1 else ''})"

    # Sanitization summary
    tally = result["sanitization"]
    h = tally.get("hidden_elements", 0)
    o = tally.get("offscreen_elements", 0)
    n = tally.get("nonprinting_chars", 0)
    sanitized_line = f"{h} hidden elements, {o} offscreen elements, {n} non-printing chars removed"

    header_lines = [
        "--- FETCH RESULT ---",
        f"URL: {result['url']}",
        f"Fetched: {result['fetched_at']}",
        f"Status: {status}",
        f"Sanitized: {sanitized_line}",
    ]

    if result.get("llms_txt_replaced"):
        header_lines.append("Source: /llms.txt")
    elif result.get("llms_txt_available"):
        header_lines.append("/llms.txt: available")

    if result.get("js_rendered"):
        header_lines.append("Renderer: Playwright (JavaScript)")

    edge_cases = result.get("edge_cases")
    if edge_cases:
        header_lines.append(f"Edge case: {edge_cases['type']} ({edge_cases['detail']})")

    if result.get("retried"):
        header_lines.append("Retried: yes (alternative User-Agent)")
    if result.get("js_hint"):
        header_lines.append(
            "Hint: static extraction returned no content -- retry with --js for JavaScript rendering"
        )

    header_lines.append("---")
    header = "\n".join(header_lines)

    body = salted_body
    if result.get("truncated_at") is not None:
        body += f"\n\n[Truncated at {result['truncated_at']} words]"

    # Metadata section
    metadata_section = ""
    metadata = result.get("metadata")
    if metadata is not None:
        metadata_section = "\n\n--- METADATA ---\n" + json.dumps(metadata, indent=2) + "\n---"

    # Links section
    links_section = ""
    links = result.get("links")
    links_mode = result.get("links_mode")
    if links is not None and links:
        links_section = "\n\n--- EXTERNAL LINKS ---\n"
        if links_mode == "full" and isinstance(links, dict):
            lines = []
            for domain, entries in links.items():
                lines.append(f"{domain}:")
                for entry in entries:
                    anchor = entry.get("anchor", "")
                    anchor_text = f" ({anchor})" if anchor else ""
                    lines.append(f"  {entry['url']}{anchor_text}")
            links_section += "\n".join(lines)
        else:
            # domains mode — links is a list of domain strings
            links_section += "\n".join(links) if isinstance(links, list) else str(links)
        links_section += "\n---"

    # Injection match details (if any)
    details = ""
    if matches:
        lines = ["\n--- INJECTION DETAILS ---"]
        for m in matches:
            lines.append(f"[{m['severity'].upper()}] {m['pattern']}: ...{m['snippet']}...")
        lines.append("---")
        details = "\n".join(lines)

    return f"{header}\n\n{body}{metadata_section}{links_section}{details}\n"
