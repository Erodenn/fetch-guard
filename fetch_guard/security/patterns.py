"""Constant registry of injection detection regex patterns.

Each entry is a (name, compiled_regex, severity) tuple.
Severity levels: "high" (system prompt overrides, ignore-previous)
                 "medium" (role-play, structural fakes)
"""

import json
import re
from pathlib import Path

# Severity constants — single source of truth for pattern severity values
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"

PATTERNS = [
    # System prompt overrides
    (
        "system_prompt_override",
        re.compile(r"(?:new|updated?|revised?|actual)\s+system\s+prompt", re.IGNORECASE),
        "high",
    ),
    (
        "you_are_now",
        re.compile(r"you\s+are\s+now\s+(?:a|an|the|in)\b", re.IGNORECASE),
        "high",
    ),
    (
        "new_instructions",
        re.compile(r"(?:new|updated?|revised?)\s+instructions?\s*:", re.IGNORECASE),
        "high",
    ),

    # Ignore-previous patterns
    (
        "ignore_previous",
        re.compile(
            r"ignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+(?:instructions?|prompts?|context)",
            re.IGNORECASE,
        ),
        "high",
    ),
    (
        "disregard_above",
        re.compile(r"disregard\s+(?:all\s+)?(?:above|previous|prior|earlier)", re.IGNORECASE),
        "high",
    ),
    (
        "forget_everything",
        re.compile(r"forget\s+(?:everything|all)\s+(?:above|before|prior)", re.IGNORECASE),
        "high",
    ),

    # Role-play instructions
    (
        "pretend_you_are",
        re.compile(r"pretend\s+(?:you\s+are|to\s+be|you'?re)", re.IGNORECASE),
        "medium",
    ),
    (
        "act_as_if",
        re.compile(
            r"act\s+as\s+(?:"
            r"(?:if|though)\b"
            r"|(?:(?:a|an)\s+)?(?:assistant|ai|model|system|bot|llm|chatbot|gpt|claude|character|persona|agent|dan)\b"
            r")",
            re.IGNORECASE,
        ),
        "medium",
    ),
    (
        "roleplay_you_are",
        re.compile(r"(?:from\s+now\s+on\s+)?you\s+are\s+a\s+(?!user|reader|visitor|customer|guest)", re.IGNORECASE),
        "medium",
    ),

    # Hidden instruction markers
    (
        "inst_marker",
        re.compile(r"\[/?INST\]", re.IGNORECASE),
        "high",
    ),
    (
        "sys_marker",
        re.compile(r"<<\s*/?SYS\s*>>", re.IGNORECASE),
        "high",
    ),

    # Structural fakes — tags that mimic LLM conversation structure
    (
        "fake_system_tag",
        re.compile(r"</?(?:system|instructions?|prompt)>", re.IGNORECASE),
        "high",
    ),
    (
        "fake_role_tag",
        re.compile(r"</?(?:human|user|assistant|claude)>", re.IGNORECASE),
        "high",
    ),
    (
        "fake_claude_md",
        re.compile(r"```\s*(?:CLAUDE\.md|claude\.md)", re.IGNORECASE),
        "high",
    ),
]

def _load_multilingual():
    """Load and compile multilingual injection patterns from JSON.

    Raises RuntimeError at import time if the JSON is missing, malformed,
    or any regex fails to compile.
    """
    path = Path(__file__).parent / "multilingual_patterns.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(f"multilingual_patterns.json not found at {path}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"multilingual_patterns.json is malformed: {e}") from e
    result = []
    for phrase_key, entry in data.items():
        severity = entry["severity"]
        for lang_code, regex_str in entry["translations"].items():
            name = f"{phrase_key}_{lang_code}"
            try:
                result.append((name, re.compile(regex_str, re.IGNORECASE), severity))
            except re.error as e:
                raise RuntimeError(f"Failed to compile multilingual pattern '{name}': {e}") from e
    return result


MULTILINGUAL_PATTERNS = _load_multilingual()
PATTERNS = PATTERNS + MULTILINGUAL_PATTERNS

# Filtered list of high-severity patterns only — used by decode-and-scan
# (no point decoding base64/hex to check for medium-severity roleplay patterns)
HIGH_PATTERNS = [(name, pattern, severity) for name, pattern, severity in PATTERNS if severity == SEVERITY_HIGH]
