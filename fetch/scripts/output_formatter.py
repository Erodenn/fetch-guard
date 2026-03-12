"""Assembles the status header and salted body into the final stdout output."""


def format_output(url, fetch_timestamp, risk_result, sanitize_tally, salted_body, truncated_at=None):
    """Build the final output string.

    Args:
        url: the fetched URL
        fetch_timestamp: ISO format timestamp string
        risk_result: dict from injection_guard.scan() with risk and matches
        sanitize_tally: dict from html_sanitizer.sanitize() with removal counts
        salted_body: content already wrapped in salted tags
        truncated_at: word count the body was truncated to, or None if not truncated
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

    header = (
        f"--- FETCH RESULT ---\n"
        f"URL: {url}\n"
        f"Fetched: {fetch_timestamp}\n"
        f"Status: {status}\n"
        f"Sanitized: {sanitized_line}\n"
        f"---"
    )

    body = salted_body
    if truncated_at is not None:
        body += f"\n\n[Truncated at {truncated_at} words]"

    # Injection match details (if any)
    details = ""
    if risk_result["matches"]:
        lines = ["\n--- INJECTION DETAILS ---"]
        for m in risk_result["matches"]:
            lines.append(f"[{m['severity'].upper()}] {m['pattern']}: ...{m['snippet']}...")
        lines.append("---")
        details = "\n".join(lines)

    return f"{header}\n\n{body}{details}\n"
