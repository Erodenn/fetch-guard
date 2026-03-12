"""Assembles the status header, salted body, metadata, and links into the final stdout output."""

import json


def format_output(
    url,
    fetch_timestamp,
    risk_result,
    sanitize_tally,
    salted_body,
    truncated_at=None,
    metadata=None,
    links=None,
    links_mode=None,
    llms_txt_available=False,
    llms_txt_replaced=False,
    js_rendered=False,
    edge_type=None,
    edge_detail=None,
    retried=False,
    js_hint=False,
):
    """Build the final output string.

    Args:
        url: the fetched URL
        fetch_timestamp: ISO format timestamp string
        risk_result: dict from injection_guard.scan() with risk and matches
        sanitize_tally: dict from html_sanitizer.sanitize() with removal counts
        salted_body: content already wrapped in salted tags
        truncated_at: word count the body was truncated to, or None if not truncated
        metadata: dict with unified metadata schema, or None to omit section
        links: list of domains or dict of grouped links, or None to omit section
        links_mode: "domains" or "full", controls link section formatting
        llms_txt_available: True if /llms.txt exists on the domain
        llms_txt_replaced: True if content was sourced from /llms.txt
    """
    # Status line
    risk = risk_result["risk"]
    match_count = len(risk_result["matches"])
    if risk == "OK":
        status = "OK"
    else:
        status = f"INJECTION WARNING ({match_count} pattern match{'es' if match_count != 1 else ''})"

    # Sanitization summary
    h = sanitize_tally.get("hidden_elements", 0)
    o = sanitize_tally.get("offscreen_elements", 0)
    n = sanitize_tally.get("nonprinting_chars", 0)
    sanitized_line = f"{h} hidden elements, {o} offscreen elements, {n} non-printing chars removed"

    header_lines = [
        "--- FETCH RESULT ---",
        f"URL: {url}",
        f"Fetched: {fetch_timestamp}",
        f"Status: {status}",
        f"Sanitized: {sanitized_line}",
    ]

    if llms_txt_replaced:
        header_lines.append("Source: /llms.txt")
    elif llms_txt_available:
        header_lines.append("/llms.txt: available")

    if js_rendered:
        header_lines.append("Renderer: Playwright (JavaScript)")
    if edge_type and edge_detail:
        header_lines.append(f"Edge case: {edge_type} ({edge_detail})")
    if retried:
        header_lines.append("Retried: yes (alternative User-Agent)")
    if js_hint:
        header_lines.append(
            "Hint: static extraction returned no content -- retry with --js for JavaScript rendering"
        )

    header_lines.append("---")
    header = "\n".join(header_lines)

    body = salted_body
    if truncated_at is not None:
        body += f"\n\n[Truncated at {truncated_at} words]"

    # Metadata section
    metadata_section = ""
    if metadata is not None:
        metadata_section = "\n\n--- METADATA ---\n" + json.dumps(metadata, indent=2) + "\n---"

    # Links section
    links_section = ""
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
    if risk_result["matches"]:
        lines = ["\n--- INJECTION DETAILS ---"]
        for m in risk_result["matches"]:
            lines.append(f"[{m['severity'].upper()}] {m['pattern']}: ...{m['snippet']}...")
        lines.append("---")
        details = "\n".join(lines)

    return f"{header}\n\n{body}{metadata_section}{links_section}{details}\n"
