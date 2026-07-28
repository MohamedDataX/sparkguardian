"""Logger factory shared by the whole package."""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    # Guard against duplicate handlers: get_logger is called at import time
    # in many modules, and each extra handler prints the message again.
    if not logger.handlers:
        # stderr, so logs never pollute JSON/SARIF written to stdout.
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
        logger.addHandler(handler)
    return logger
