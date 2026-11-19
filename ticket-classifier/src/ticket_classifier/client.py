"""Anthropic API client."""

from functools import cache

from anthropic import Anthropic

from .config import get_settings


@cache
def get_client() -> Anthropic:
    settings = get_settings()
    return Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
