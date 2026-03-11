"""Centralized logger for the fetch skill pipeline."""

import logging
import sys

LOG_FORMAT = "%(levelname)s [%(name)s] %(message)s"


def get_logger(name):
    """Return a named logger configured for stderr output.

    All log output goes to stderr so stdout remains clean for pipeline output.
    Default level is WARNING; set FETCH_LOG_LEVEL env var to override
    (e.g. DEBUG, INFO).
    """
    import os

    logger = logging.getLogger(f"fetch.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)

    level = os.environ.get("FETCH_LOG_LEVEL", "WARNING").upper()
    logger.setLevel(getattr(logging, level, logging.WARNING))

    return logger
