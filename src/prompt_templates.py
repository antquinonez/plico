# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Prompt template loader for externalized YAML prompt definitions.

Loads prompt templates from ``config/prompts/`` YAML files, falling back
to hardcoded defaults when no external file is found. This allows prompt
instructions to be version-controlled, customized, and swapped without
modifying Python source code.

Usage::

    from src.prompt_templates import load_prompt_template, load_synthesis_template

    # Load by name (looks in config/prompts/screening_planning.yaml)
    prompts = load_prompt_template("screening_planning")

    # Load by explicit path
    prompts = load_prompt_template("./my_custom_prompts.yaml")

    # Load synthesis with variable substitution
    synthesis = load_synthesis_template("screening_synthesis", top_n=5)

Template YAML format::

    name: my_template
    description: "What this template does"
    prompts:
      - sequence: 10
        prompt_name: analyze_jd
        prompt: |
          Analyze the job description...
        references: '["job_description"]'
        phase: planning
        generator: "true"

Config location: ``config/prompts/``
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_PROMPTS_DIR: Path | None = None


def _find_config_prompts_dir() -> Path:
    """Find the config/prompts directory.

    Search order:
        1. Cached result from previous call
        2. ``config/prompts`` relative to CWD
        3. ``config/prompts`` relative to this module's parent (project root)

    Returns:
        Path to the config/prompts directory (may not exist).

    """
    global _CONFIG_PROMPTS_DIR
    if _CONFIG_PROMPTS_DIR is not None:
        return _CONFIG_PROMPTS_DIR

    candidates = [
        Path.cwd() / "config" / "prompts",
        Path(__file__).parent.parent / "config" / "prompts",
        Path.cwd().parent / "config" / "prompts",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            _CONFIG_PROMPTS_DIR = candidate
            return candidate

    fallback = Path.cwd() / "config" / "prompts"
    _CONFIG_PROMPTS_DIR = fallback
    return fallback


def resolve_template_path(name_or_path: str) -> Path | None:
    """Resolve a template name or path to an actual file path.

    Args:
        name_or_path: Either a bare name (e.g., ``"screening_planning"``)
            resolved against ``config/prompts/<name>.yaml``, or an
            explicit file path (absolute or relative).

    Returns:
        Resolved Path if the file exists, otherwise None.

    """
    candidate = Path(name_or_path)

    if candidate.is_file():
        return candidate.resolve()

    if candidate.suffix != ".yaml":
        candidate = candidate.with_suffix(".yaml")

    if candidate.is_file():
        return candidate.resolve()

    prompts_dir = _find_config_prompts_dir()
    config_candidate = prompts_dir / candidate.name
    if config_candidate.is_file():
        return config_candidate.resolve()

    return None


def _dict_to_prompt_spec(data: dict[str, Any]) -> Any:
    """Convert a dict from YAML to a PromptSpec instance.

    Uses late import to avoid coupling to the scripts package at module level.

    Args:
        data: Dict with prompt fields from YAML.

    Returns:
        PromptSpec instance.

    """
    scripts_dir = str(Path(__file__).parent.parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from sample_workbooks.base import PromptSpec

    data = dict(data)

    json_fields = ["history", "references", "semantic_filter", "tools"]
    for field in json_fields:
        value = data.get(field)
        if isinstance(value, list | dict):
            data[field] = json.dumps(value)
        elif value is None:
            data[field] = None

    for field in ("sequence",):
        if field in data and not isinstance(data[field], int):
            data[field] = int(data[field])

    valid_fields = {
        "sequence",
        "name",
        "prompt",
        "history",
        "notes",
        "client",
        "condition",
        "references",
        "semantic_query",
        "semantic_filter",
        "query_expansion",
        "rerank",
        "agent_mode",
        "tools",
        "max_tool_rounds",
        "validation_prompt",
        "max_validation_retries",
        "phase",
        "generator",
    }

    field_map = {"prompt_name": "name"}
    filtered = {}
    for key, value in data.items():
        mapped_key = field_map.get(key, key)
        if mapped_key in valid_fields:
            filtered[mapped_key] = value

    return PromptSpec(**filtered)


def load_prompt_template(name_or_path: str) -> list[Any] | None:
    """Load a prompt template from a YAML file.

    Args:
        name_or_path: Template name (looked up in ``config/prompts/``)
            or explicit file path.

    Returns:
        List of PromptSpec instances, or None if the file was not found.

    """
    path = resolve_template_path(name_or_path)
    if path is None:
        logger.info("Prompt template not found: %s", name_or_path)
        return None

    logger.info("Loading prompt template: %s", path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    prompts_data = data.get("prompts", [])
    if not prompts_data:
        logger.warning("No prompts found in template: %s", path)
        return None

    return [_dict_to_prompt_spec(p) for p in prompts_data]


def load_synthesis_template(
    name_or_path: str,
    top_n: int = 10,
    comparison_n: int | None = None,
) -> list[dict[str, Any]] | None:
    """Load a synthesis template from a YAML file with variable substitution.

    The synthesis template supports ``{{top_n}}`` and ``{{comparison_n}}``
    placeholders that are replaced with actual values.

    Args:
        name_or_path: Template name or file path.
        top_n: Number of top candidates for ``source_scope``.
        comparison_n: Number of candidates for comparison. Defaults to
            ``min(3, top_n)``.

    Returns:
        List of synthesis prompt dicts, or None if file not found.

    """
    path = resolve_template_path(name_or_path)
    if path is None:
        logger.info("Synthesis template not found: %s", name_or_path)
        return None

    if comparison_n is None:
        comparison_n = min(3, top_n)

    logger.info("Loading synthesis template: %s (top_n=%d)", path, top_n)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    prompts_data = data.get("prompts", [])
    if not prompts_data:
        logger.warning("No prompts found in synthesis template: %s", path)
        return None

    results = []
    for item in prompts_data:
        entry = dict(item)
        if isinstance(entry.get("source_scope"), str):
            entry["source_scope"] = (
                entry["source_scope"]
                .replace("{{top_n}}", str(top_n))
                .replace("{{comparison_n}}", str(comparison_n))
            )
        if isinstance(entry.get("source_prompts"), list):
            entry["source_prompts"] = json.dumps(entry["source_prompts"])
        if isinstance(entry.get("history"), list):
            entry["history"] = json.dumps(entry["history"])
        if entry.get("history") is None:
            entry["history"] = ""
        if entry.get("condition") is None:
            entry["condition"] = ""
        results.append(entry)

    return results
