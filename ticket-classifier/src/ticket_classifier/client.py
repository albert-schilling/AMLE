"""Anthropic API client."""

from functools import cache

from anthropic import Anthropic

from .config import get_settings


@cache
def get_client() -> Anthropic:
    """Raises ``RuntimeError`` if ``ANTHROPIC_API_KEY`` is not set."""
    key = get_settings().anthropic_api_key
    if key is None:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return Anthropic(api_key=key.get_secret_value())
