"""Text normalization for injection scanning — handles homoglyph/confusable bypasses."""

import unicodedata

# Confusable character mapping: visually similar characters → ASCII equivalents.
# Covers high-frequency Cyrillic and Greek confusables that appear in injection
# keywords (ignore, previous, system, prompt, instructions, forget, disregard, pretend).
CONFUSABLES = {
    # Cyrillic → Latin
    "\u0430": "a",  # а
    "\u0435": "e",  # е
    "\u043e": "o",  # о
    "\u0441": "c",  # с
    "\u0440": "p",  # р
    "\u0445": "x",  # х
    "\u0443": "y",  # у
    "\u0456": "i",  # і
    "\u0455": "s",  # ѕ
    "\u044a": "b",  # ъ (rare but possible)
    "\u043d": "h",  # н (visual match in some fonts)
    "\u0442": "t",  # т (visual match in some fonts)
    "\u043c": "m",  # м (visual match in some fonts)
    # Cyrillic uppercase → Latin lowercase
    "\u0410": "a",  # А
    "\u0415": "e",  # Е
    "\u041e": "o",  # О
    "\u0421": "c",  # С
    "\u0420": "p",  # Р
    "\u0425": "x",  # Х
    "\u0423": "y",  # У
    "\u0406": "i",  # І
    "\u0405": "s",  # Ѕ
    # Greek → Latin
    "\u03b1": "a",  # α
    "\u03b5": "e",  # ε
    "\u03bf": "o",  # ο
    "\u03b9": "i",  # ι
    "\u03ba": "k",  # κ
    "\u03c1": "p",  # ρ (visually similar to p)
    "\u03c4": "t",  # τ
    "\u03c5": "u",  # υ
    "\u03bd": "v",  # ν
    # Greek uppercase → Latin lowercase
    "\u0391": "a",  # Α
    "\u0395": "e",  # Ε
    "\u039f": "o",  # Ο
    "\u0399": "i",  # Ι
    "\u039a": "k",  # Κ
    "\u03a1": "p",  # Ρ
    "\u03a4": "t",  # Τ
}

# Build translation table once
_CONFUSABLE_TABLE = str.maketrans(CONFUSABLES)


def normalize_for_scan(text: str) -> str:
    """Normalize text for injection pattern scanning.

    Applies NFKC normalization (collapses compatibility characters) then maps
    known confusable characters (Cyrillic/Greek look-alikes) to their Latin
    equivalents. Our patterns already use IGNORECASE so no lowercasing needed.
    """
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.translate(_CONFUSABLE_TABLE)
