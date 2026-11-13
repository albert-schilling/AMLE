"""Anthropic API setup: the client and file uploads."""

import logging
from pathlib import Path

from anthropic import Anthropic

from .config import get_settings

logger = logging.getLogger(__name__)


def create_client() -> Anthropic:
    return Anthropic(api_key=get_settings().anthropic_api_key.get_secret_value())


def upload_log(client: Anthropic, path: Path) -> str:
    """Upload the log file once; the sandbox can only read files given this way."""
    uploaded = client.beta.files.upload(
        file=(path.name, path.read_bytes(), "text/plain")
    )
    logger.info("Uploaded %s as %s", path, uploaded.id)
    return uploaded.id
