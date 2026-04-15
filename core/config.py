"""Application configuration for the FastAPI backend."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """
    Simple settings container loaded from environment variables.

    This project targets IBKR Client Portal Web API running locally.
    """

    base_url: str = os.getenv("IBKR_BASE_URL", "https://localhost:5000/v1/api")
    verify_ssl: bool = os.getenv("IBKR_VERIFY_SSL", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    default_account_id: str | None = os.getenv("IBKR_ACCOUNT_ID")
    request_timeout_seconds: int = int(os.getenv("IBKR_TIMEOUT", "8"))


settings = Settings()
