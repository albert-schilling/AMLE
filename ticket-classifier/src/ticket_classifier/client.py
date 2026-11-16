"""Anthropic API setup: the client and file uploads."""

import logging
from functools import cache
from pathlib import Path

from anthropic import Anthropic

from .config import get_settings

logger = logging.getLogger(__name__)


@cache
def get_client() -> Anthropic:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
    return client


def upload_log(client: Anthropic, path: Path) -> str:
    """Upload the log file once; the sandbox can only read files given this way."""
    uploaded = client.beta.files.upload(
        file=(path.name, path.read_bytes(), "text/plain")
    )
    logger.info("Uploaded %s as %s", path, uploaded.id)
    return uploaded.id
