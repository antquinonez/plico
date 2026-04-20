# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Logging configuration for CLI scripts."""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler


def setup_logging(
    quiet: bool = False, verbose: bool = False, suppress_litellm: bool = True
) -> logging.Logger:
    """Configure logging with file rotation and optional console suppression.

    Args:
        quiet: If True, suppress console output (logs to file only).
        verbose: If True, enable debug-level logging.
        suppress_litellm: If True, suppress LiteLLM's verbose logging.

    Returns:
        Configured logger instance.

    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    src_config = get_config()
    log_config = src_config.logging

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_dir = os.path.join(project_root, log_config.directory)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, log_config.filename)

    file_handler = TimedRotatingFileHandler(
        log_file,
        when=log_config.rotation.when,
        interval=log_config.rotation.interval,
        backupCount=log_config.rotation.backup_count,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_config.format))
    root_logger.addHandler(file_handler)

    if not quiet:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_config.format))
        root_logger.addHandler(console_handler)

    if suppress_litellm:
        import litellm

        litellm.suppress_debug_info = True
        litellm_logger = logging.getLogger("LiteLLM")
        litellm_logger.setLevel(logging.WARNING)
        litellm_logger.propagate = False

    return logging.getLogger(__name__)


def get_config():
    """Get configuration (lazy import to avoid circular dependency).

    Returns:
        Config instance.

    """
    from src.config import get_config as _get_config

    return _get_config()
