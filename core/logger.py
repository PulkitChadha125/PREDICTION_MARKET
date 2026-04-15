"""Central logging configuration for the app."""

from __future__ import annotations

import logging


def setup_logging() -> None:
    """Configure root logging once for the whole application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger used by modules/services."""
    return logging.getLogger(name)
