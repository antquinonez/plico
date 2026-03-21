#!/usr/bin/env python
# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Utility functions for sample workbook creation scripts.

This module provides:
    - Client argument parsing helpers
    - Client configuration retrieval from clients.yaml
    - Config sheet override builders
    - Sample clients override builders for multiclient workbooks
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_config


def get_available_clients() -> list[str]:
    """Return list of valid client names from clients.yaml.

    Returns:
        Sorted list of client type names.

    """
    config = get_config()
    return sorted(config.clients.client_types.keys())


def get_client_config(client_name: str) -> dict[str, Any]:
    """Get client configuration from clients.yaml.

    Args:
        client_name: Name of the client type (e.g., 'anthropic', 'litellm-gemini').

    Returns:
        Dictionary with client configuration (client_class, type, api_key_env, default_model, etc.).

    Raises:
        ValueError: If client_name is not found in clients.yaml.

    """
    config = get_config()
    client_types = config.clients.client_types

    if client_name not in client_types:
        available = ", ".join(get_available_clients())
        raise ValueError(f"Unknown client type '{client_name}'. Available: {available}")

    return client_types[client_name]


def build_config_overrides(client_name: str) -> dict[str, str]:
    """Build overrides for the config sheet based on selected client.

    Args:
        client_name: Name of the client type from clients.yaml.

    Returns:
        Dictionary with 'client_type' and 'model' keys for config sheet overrides.

    Raises:
        ValueError: If client_name is not found in clients.yaml.

    """
    client_config = get_client_config(client_name)
    return {
        "client_type": client_name,
        "model": getattr(client_config, "default_model", ""),
    }


def build_sample_clients_overrides(client_name: str) -> dict[str, dict[str, Any]]:
    """Build updated sample_clients dict for multiclient workbooks.

    Creates four client variants (default, fast, creative, analytical) all using
    the same provider but with different temperature and max_tokens settings.

    Args:
        client_name: Name of the client type from clients.yaml.

    Returns:
        Dictionary mapping client names to their configurations.

    Raises:
        ValueError: If client_name is not found in clients.yaml.

    """
    client_config = get_client_config(client_name)
    client_type = client_name
    api_key_env = getattr(client_config, "api_key_env", "")
    model = getattr(client_config, "default_model", "")

    return {
        "default": {
            "client_type": client_type,
            "api_key_env": api_key_env,
            "model": model,
            "temperature": 0.7,
            "max_tokens": 300,
        },
        "fast": {
            "client_type": client_type,
            "api_key_env": api_key_env,
            "model": model,
            "temperature": 0.3,
            "max_tokens": 100,
        },
        "creative": {
            "client_type": client_type,
            "api_key_env": api_key_env,
            "model": model,
            "temperature": 0.9,
            "max_tokens": 500,
        },
        "analytical": {
            "client_type": client_type,
            "api_key_env": api_key_env,
            "model": model,
            "temperature": 0.2,
            "max_tokens": 400,
        },
    }


def create_client_argument_parser(
    script_description: str,
    default_output: str,
    default_client: str = "litellm-mistral-small",
) -> argparse.ArgumentParser:
    """Create an ArgumentParser with standard client argument.

    Args:
        script_description: Description text for the script.
        default_output: Default output path for the workbook.
        default_client: Default client type from clients.yaml.

    Returns:
        Configured ArgumentParser instance.

    """
    parser = argparse.ArgumentParser(
        description=script_description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Available clients: {', '.join(get_available_clients())}",
    )

    parser.add_argument(
        "output",
        nargs="?",
        default=default_output,
        help=f"Output path for workbook (default: {default_output})",
    )

    parser.add_argument(
        "--client",
        default=default_client,
        help=f"Client type from clients.yaml (default: {default_client})",
    )

    return parser


def parse_client_args(
    script_description: str,
    default_output: str,
    default_client: str = "litellm-mistral-small",
) -> tuple[argparse.Namespace, dict[str, str], dict[str, dict[str, Any]]]:
    """Parse command line arguments and build client overrides.

    This is a convenience function that combines argument parsing with
    building the necessary overrides for workbook creation.

    Args:
        script_description: Description text for the script.
        default_output: Default output path for the workbook.
        default_client: Default client type from clients.yaml.

    Returns:
        Tuple of (args, config_overrides, sample_clients_overrides).

    Raises:
        ValueError: If client_name is not found in clients.yaml.
        SystemExit: If --help is requested or invalid arguments provided.

    """
    parser = create_client_argument_parser(script_description, default_output, default_client)
    args = parser.parse_args()

    config_overrides = build_config_overrides(args.client)
    sample_clients_overrides = build_sample_clients_overrides(args.client)

    return args, config_overrides, sample_clients_overrides
