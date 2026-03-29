# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Agentic execution loop for tool-call-driven prompt execution.

The AgentLoop wraps an FFAIClientBase and executes multi-round tool-call
loops: the LLM generates responses that may include tool calls, the loop
executes those tools, feeds results back, and continues until the LLM
produces a final answer without tool calls or the maximum round count
is reached.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any

from ..FFAIClientBase import FFAIClientBase
from ..orchestrator.tool_registry import ToolRegistry
from .agent_result import AgentResult, ToolCallRecord

logger = logging.getLogger(__name__)

_TOOL_CALLS_DATA_KEY = "tool_calls"
_CONTINUE_PROMPT = "Continue using the tool results to answer the original request."


class AgentLoop:
    """Executes agentic tool-call loops for a single prompt.

    Usage:
        loop = AgentLoop(client, tool_registry, max_rounds=5)
        result = loop.execute(
            prompt="Search for information about X",
            tools=["rag_search", "calculate"],
        )

    """

    def __init__(
        self,
        client: FFAIClientBase,
        tool_registry: ToolRegistry,
        max_rounds: int = 5,
        tool_timeout: float = 30.0,
        continue_on_tool_error: bool = True,
    ) -> None:
        """Initialize the agent loop.

        Args:
            client: AI client to use for LLM calls. Will be cloned for isolation.
            tool_registry: Registry of tools available for execution.
            max_rounds: Maximum number of tool-call rounds.
            tool_timeout: Timeout in seconds for individual tool execution.
            continue_on_tool_error: Whether to continue the loop if a tool fails.

        """
        self.client = client
        self.tool_registry = tool_registry
        self.max_rounds = max_rounds
        self.tool_timeout = tool_timeout
        self.continue_on_tool_error = continue_on_tool_error

    def execute(
        self,
        prompt: str,
        tools: list[str],
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> AgentResult:
        """Execute the agentic loop.

        Calls the LLM with the prompt and available tools. If the response
        contains tool calls, executes them and feeds results back. Repeats
        until no tool calls or max_rounds is reached.

        Args:
            prompt: The user prompt.
            tools: List of tool names to make available.
            tool_choice: Tool selection strategy ("auto", "none", etc.).
            **kwargs: Additional parameters passed to generate_response().

        Returns:
            AgentResult with response, tool call records, and round/LLM counts.

        """
        kwargs = dict(kwargs)
        kwargs.pop("prompt_name", None)
        kwargs.pop("history", None)

        tool_schemas = self.tool_registry.get_tools_schema(tools)

        if not tool_schemas:
            logger.warning("No valid tool schemas found, executing as single prompt")
            response = self.client.generate_response(prompt, **kwargs)
            return AgentResult(
                response=response,
                total_rounds=1,
                total_llm_calls=1,
                status="success",
            )

        all_tool_calls: list[ToolCallRecord] = []
        total_llm_calls = 0
        current_prompt = prompt
        final_response = ""
        last_round = 0

        for round_num in range(1, self.max_rounds + 1):
            last_round = round_num
            total_llm_calls += 1
            logger.info(
                f"Agent round {round_num}/{self.max_rounds} "
                f"({len(all_tool_calls)} tool calls so far)"
            )

            try:
                response = self.client.generate_response(
                    prompt=current_prompt,
                    tools=tool_schemas,
                    tool_choice=tool_choice if round_num == 1 else "auto",
                    **kwargs,
                )
            except Exception as e:
                logger.error(f"LLM call failed in round {round_num}: {e}")
                if total_llm_calls == 1:
                    return AgentResult(
                        response="",
                        total_rounds=round_num,
                        total_llm_calls=total_llm_calls,
                        status="failed",
                    )
                break

            final_response = response

            tool_calls = self._extract_tool_calls()

            if not tool_calls:
                logger.info(f"No tool calls in round {round_num}, loop complete")
                break

            logger.info(f"Round {round_num}: {len(tool_calls)} tool call(s) detected")

            for tc_data in tool_calls:
                tc_record = self._execute_single_tool(tc_data, round_num)
                all_tool_calls.append(tc_record)

                if tc_record.error and not self.continue_on_tool_error:
                    logger.error(f"Tool error, aborting loop: {tc_record.error}")
                    return AgentResult(
                        response=final_response,
                        tool_calls=all_tool_calls,
                        total_rounds=last_round,
                        total_llm_calls=total_llm_calls,
                        status="failed",
                    )

            current_prompt = _CONTINUE_PROMPT
        else:
            logger.warning(f"Agent loop reached max rounds ({self.max_rounds})")
            return AgentResult(
                response=final_response,
                tool_calls=all_tool_calls,
                total_rounds=self.max_rounds,
                total_llm_calls=total_llm_calls,
                status="max_rounds_exceeded",
            )

        return AgentResult(
            response=final_response,
            tool_calls=all_tool_calls,
            total_rounds=last_round,
            total_llm_calls=total_llm_calls,
            status="success",
        )

    def _extract_tool_calls(self) -> list[dict[str, Any]]:
        """Extract tool calls from the client's chat history.

        Reads the last assistant message from chat history and extracts
        tool_calls data if present.

        Returns:
            List of tool call dicts with 'id', 'function.name', 'function.arguments'.

        """
        try:
            history = self.client.get_conversation_history()
        except Exception as e:
            logger.warning(f"Could not read conversation history: {e}")
            return []

        for msg in reversed(history):
            if msg.get("role") == "assistant":
                if _TOOL_CALLS_DATA_KEY in msg:
                    return msg[_TOOL_CALLS_DATA_KEY]
                return []

        return []

    def _execute_single_tool(self, tc_data: dict[str, Any], round_num: int) -> ToolCallRecord:
        """Execute a single tool call and feed the result back.

        Args:
            tc_data: Tool call dict with 'id', 'function.name', 'function.arguments'.
            round_num: Current round number.

        Returns:
            ToolCallRecord with execution details.

        """
        func_info = tc_data.get("function", {})
        tool_name = func_info.get("name", "")
        tool_call_id = tc_data.get("id", "")
        arguments_str = func_info.get("arguments", "{}")

        try:
            arguments = (
                json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
            )
        except json.JSONDecodeError:
            arguments = {}

        logger.info(f"Executing tool: {tool_name}({arguments})")

        start_time = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(self.tool_registry.execute_tool, tool_name, arguments)
                try:
                    result = future.result(timeout=self.tool_timeout)
                except FuturesTimeoutError:
                    raise RuntimeError(f"Tool '{tool_name}' timed out after {self.tool_timeout}s")
            duration_ms = (time.monotonic() - start_time) * 1000

            self.client.add_tool_result(tool_call_id, result)

            return ToolCallRecord(
                round=round_num,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                result=result[:10000],
                duration_ms=round(duration_ms, 1),
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            error_msg = str(e)

            logger.error(f"Tool {tool_name} failed: {error_msg}")

            error_result = json.dumps({"error": error_msg})
            self.client.add_tool_result(tool_call_id, error_result)

            return ToolCallRecord(
                round=round_num,
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                arguments=arguments,
                result=error_result,
                duration_ms=round(duration_ms, 1),
                error=error_msg,
            )
