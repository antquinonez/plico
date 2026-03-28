# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tool registry for agentic execution.

Provides registration, validation, and execution of tools available
to the agentic loop. Mirrors the ClientRegistry pattern for consistency.

Tools can be:
- Built-in: Referenced as ``builtin:<tool_name>`` (e.g. ``builtin:rag_search``)
- Python callables: Referenced as ``python:<module>.<function>``
"""

from __future__ import annotations

import importlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Declarative tool definition.

    Attributes:
        name: Unique identifier for this tool.
        description: Human-readable description sent to the LLM.
        parameters: JSON Schema describing the tool's parameters.
        implementation: Implementation reference string
            (``builtin:<name>`` or ``python:<module>.<function>``).
        enabled: Whether this tool is available for use.

    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    implementation: str = ""
    enabled: bool = True

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool schema.

        Returns:
            Dictionary in OpenAI tool format.

        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "implementation": self.implementation,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolDefinition:
        """Create from dictionary.

        Args:
            data: Dictionary with tool definition fields.

        Returns:
            A new ToolDefinition instance.

        """
        parameters = data.get("parameters", {})
        if parameters is None:
            parameters = {}
        elif isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                logger.warning(
                    f"Invalid JSON in parameters for tool '{data.get('name')}': {parameters}"
                )
                parameters = {"type": "object", "properties": {}}

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=parameters,
            implementation=data.get("implementation", ""),
            enabled=data.get("enabled", True),
        )


class ToolRegistry:
    """Registry of tools available for agentic execution.

    Usage:
        registry = ToolRegistry()
        registry.register(ToolDefinition(
            name='rag_search',
            description='Search indexed documents',
            parameters={...},
            implementation='builtin:rag_search',
        ))

        schema = registry.get_tools_schema(['rag_search'])
        result = registry.execute_tool('rag_search', {'query': 'test'})

    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._executors: dict[str, Callable[..., str]] = {}

    def register(self, definition: ToolDefinition) -> None:
        """Register a tool definition.

        Args:
            definition: The tool definition to register.

        Raises:
            ValueError: If a tool with the same name is already registered.

        """
        if definition.name in self._tools:
            raise ValueError(f"Tool '{definition.name}' is already registered")
        self._tools[definition.name] = definition
        logger.debug(f"Registered tool '{definition.name}'")

    def register_executor(self, name: str, executor: Callable[..., str]) -> None:
        """Register a callable executor for a tool.

        This is used for built-in tools where the executor is a Python
        function rather than referenced by implementation string.

        Args:
            name: Tool name (must already be registered via ``register()``).
            executor: Callable that accepts a dict of arguments and returns a string.

        Raises:
            ValueError: If the tool is not registered.

        """
        if name not in self._tools:
            raise ValueError(f"Cannot register executor for unknown tool '{name}'")
        self._executors[name] = executor
        logger.debug(f"Registered executor for tool '{name}'")

    def get_tool(self, name: str) -> ToolDefinition:
        """Get a tool definition by name.

        Args:
            name: Tool name.

        Returns:
            The tool definition.

        Raises:
            KeyError: If the tool is not registered.

        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")
        return self._tools[name]

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_registered_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())

    def get_enabled_names(self) -> list[str]:
        """Get list of enabled tool names."""
        return [name for name, tool in self._tools.items() if tool.enabled]

    def get_tools_schema(self, tool_names: list[str]) -> list[dict[str, Any]]:
        """Get OpenAI-format tool schemas for the specified tools.

        Args:
            tool_names: List of tool names to include.

        Returns:
            List of tool schema dictionaries in OpenAI function-calling format.

        """
        schemas = []
        for name in tool_names:
            if name in self._tools and self._tools[name].enabled:
                schemas.append(self._tools[name].to_openai_tool())
            else:
                logger.warning(f"Requested tool '{name}' not found or disabled, skipping")
        return schemas

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name with the given arguments.

        Resolution order:
        1. Registered executor (from ``register_executor()``)
        2. ``builtin:`` implementation (looked up in built-in tools)
        3. ``python:`` implementation (dynamic import)

        Args:
            name: Tool name.
            arguments: Arguments to pass to the tool.

        Returns:
            Tool execution result as a string.

        Raises:
            KeyError: If the tool is not registered.
            RuntimeError: If tool execution fails.

        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry")

        tool = self._tools[name]
        if not tool.enabled:
            raise RuntimeError(f"Tool '{name}' is disabled")

        executor = self._resolve_executor(name, tool)
        if executor is None:
            raise RuntimeError(
                f"No executor found for tool '{name}' (implementation='{tool.implementation}')"
            )

        try:
            result = executor(arguments)
            if not isinstance(result, str):
                result = str(result)
            return result
        except Exception as e:
            logger.error(f"Tool '{name}' execution failed: {e}")
            raise RuntimeError(f"Tool '{name}' execution failed: {e}") from e

    def _resolve_executor(self, name: str, tool: ToolDefinition) -> Callable[..., str] | None:
        """Resolve the executor callable for a tool.

        Args:
            name: Tool name.
            tool: Tool definition.

        Returns:
            Callable executor or None if not found.

        """
        if name in self._executors:
            return self._executors[name]

        if not tool.implementation:
            return None

        if tool.implementation.startswith("builtin:"):
            builtin_name = tool.implementation[len("builtin:") :]
            return self._get_builtin_executor(builtin_name)

        if tool.implementation.startswith("python:"):
            callable_path = tool.implementation[len("python:") :]
            return self.load_python_callable(callable_path)

        return None

    def _get_builtin_executor(self, name: str) -> Callable[..., str] | None:
        """Get a built-in tool executor by name.

        Args:
            name: Built-in tool name (e.g., 'rag_search').

        Returns:
            The executor callable or None.

        """
        try:
            from .builtin_tools import get_builtin_tool

            return get_builtin_tool(name)
        except (ImportError, KeyError) as e:
            logger.warning(f"Built-in tool '{name}' not found: {e}")
            return None

    @staticmethod
    def load_python_callable(path: str) -> Callable[..., str] | None:
        """Load a Python callable from a dotted module.function path.

        Args:
            path: Dotted path like 'my_package.my_module.my_function'.

        Returns:
            The callable or None.

        """
        parts = path.rsplit(".", 1)
        if len(parts) != 2:
            logger.error(f"Invalid python callable path: '{path}' (expected module.function)")
            return None

        module_path, func_name = parts
        try:
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            if not callable(func):
                logger.error(f"'{path}' is not callable")
                return None
            return func
        except (ImportError, AttributeError) as e:
            logger.error(f"Could not load python callable '{path}': {e}")
            return None
