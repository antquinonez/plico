# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Agent mode executor for the orchestrator.

Handles agentic tool-call execution with validation retry logic.
Receives callbacks from the orchestrator for history recording,
reference injection, and isolated FFAI client creation, keeping
the agent execution decoupled from orchestrator internals.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any

from ..config import get_config
from ..FFAI import FFAI
from .models import ConfigSpec, PromptSpec
from .results import ResultBuilder
from .tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


def _build_validation_prompt(validation_prompt: str, response: str) -> str:
    return (
        "You are a response validator. Evaluate the response against the criteria below.\n"
        'Reply with exactly "PASS" if acceptable, or "FAIL: <reason>" if not.\n\n'
        f"Criteria: {validation_prompt}\n\n"
        f"Response to evaluate:\n{response}"
    )


class AgentExecutor:
    """Handles agentic tool-call execution with optional validation retry.

    Args:
        tool_registry: Tool registry with registered tools and executors.
        config: Orchestrator config dict (model, temperature, max_tokens, etc.).
        record_history_fn: Callback to record agent results in shared history.
            Signature: ``(prompt: dict, response: str | None) -> None``

    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        config: ConfigSpec,
        record_history_fn: Callable[[PromptSpec, str | None], None],
    ) -> None:
        self.tool_registry = tool_registry
        self.config = config
        self._record_history = record_history_fn

    def execute(
        self,
        prompt: PromptSpec,
        ffai: FFAI,
        builder: ResultBuilder,
        seq_label: str,
        inject_references_fn: Callable[[PromptSpec], str],
        get_isolated_ffai_fn: Callable[[str | None], FFAI],
    ) -> dict[str, Any] | None:
        """Execute a prompt using the agentic tool-call loop.

        Args:
            prompt: Prompt dictionary with agent_mode=True.
            ffai: FFAI instance for the execution.
            builder: ResultBuilder already configured with prompt metadata.
            seq_label: Label for logging (e.g. "Sequence 10").
            inject_references_fn: Callback to inject document references.
            get_isolated_ffai_fn: Callback to create isolated FFAI for validation.

        Returns:
            Result dictionary with tool call records, or None to signal
            fallback to single-shot execution (e.g. unsupported client type).

        """
        from ..agent.agent_loop import AgentLoop

        client = ffai.client

        if client.__class__.__name__ == "FFOpenAIAssistant":
            logger.warning(
                f"{seq_label}: agent_mode is not supported with FFOpenAIAssistant "
                "(Assistants API). Falling back to single-shot execution."
            )
            return None

        tool_names = prompt.get("tools") or []
        max_rounds = prompt.get("max_tool_rounds") or get_config().agent.max_tool_rounds

        agent_config = get_config().agent

        injected_prompt = inject_references_fn(prompt)
        resolved_prompt, _ = ffai.build_prompt(
            injected_prompt,
            prompt.get("history"),
            None,
        )

        logger.info(f"{seq_label} agent mode: {len(tool_names)} tool(s), max_rounds={max_rounds}")

        agent_loop = AgentLoop(
            client=ffai.client,
            tool_registry=self.tool_registry,
            max_rounds=max_rounds,
            tool_timeout=agent_config.tool_timeout,
            continue_on_tool_error=agent_config.continue_on_tool_error,
        )

        validation_prompt = prompt.get("validation_prompt")
        max_val_retries = (
            prompt.get("max_validation_retries") or agent_config.validation.max_retries
        )

        try:
            agent_start = time.monotonic()
            agent_result = agent_loop.execute(
                prompt=resolved_prompt,
                tools=tool_names,
                tool_choice="auto",
                prompt_name=prompt.get("prompt_name"),
                history=prompt.get("history"),
                model=self.config.get("model"),
                temperature=self.config.get("temperature"),
                max_tokens=self.config.get("max_tokens"),
            )
            agent_duration_ms = (time.monotonic() - agent_start) * 1000

            builder.with_agent_result(agent_result)
            builder.with_resolved_prompt(resolved_prompt)
            builder.with_attempts(1)
            builder.with_duration(agent_duration_ms)

            usage = getattr(ffai.client, "last_usage", None)
            if usage:
                builder.with_usage(usage.input_tokens, usage.output_tokens, usage.total_tokens)
            cost_usd = getattr(ffai.client, "last_cost_usd", 0.0)
            builder.with_cost(cost_usd)

            if agent_result.status == "failed":
                logger.error(f"{seq_label} agent mode failed")
            elif agent_result.status == "max_rounds_exceeded":
                logger.warning(f"{seq_label} agent mode max rounds ({agent_result.total_rounds})")
            else:
                logger.info(
                    f"{seq_label} agent mode succeeded: "
                    f"{agent_result.tool_calls_count} tool call(s), "
                    f"{agent_result.total_rounds} round(s)"
                )

            if agent_result.status == "success" and agent_result.response:
                self._record_history(prompt, agent_result.response)

            if validation_prompt and agent_config.validation.enabled and agent_result.response:
                self.validate_response(
                    prompt=prompt,
                    builder=builder,
                    agent_result=agent_result,
                    tool_names=tool_names,
                    validation_prompt=validation_prompt,
                    max_val_retries=max_val_retries,
                    seq_label=seq_label,
                    original_prompt=resolved_prompt,
                    max_rounds=max_rounds,
                    tool_timeout=agent_config.tool_timeout,
                    continue_on_tool_error=agent_config.continue_on_tool_error,
                    get_isolated_ffai_fn=get_isolated_ffai_fn,
                )

        except Exception as e:
            builder.with_error(str(e), 1)
            logger.error(f"{seq_label} agent mode error: {e}")

        return builder.build_dict()

    def validate_response(
        self,
        prompt: PromptSpec,
        builder: Any,
        agent_result: Any,
        tool_names: list[str],
        validation_prompt: str,
        max_val_retries: int,
        seq_label: str,
        original_prompt: str,
        max_rounds: int,
        tool_timeout: float,
        continue_on_tool_error: bool,
        get_isolated_ffai_fn: Callable[[str | None], FFAI],
    ) -> None:
        """Validate agent response and optionally re-execute on failure.

        Args:
            prompt: Original prompt dictionary.
            builder: ResultBuilder to populate with validation results.
            agent_result: The initial AgentResult to validate.
            tool_names: Tool names available for re-execution.
            validation_prompt: Criteria to validate against.
            max_val_retries: Maximum validation retry attempts.
            seq_label: Label for logging.
            original_prompt: The fully resolved original prompt text.
            max_rounds: Max agent tool rounds for retry execution.
            tool_timeout: Timeout for each tool execution.
            continue_on_tool_error: Whether tool errors should continue the loop.
            get_isolated_ffai_fn: Callback to create isolated FFAI instances.

        """
        from ..agent.agent_loop import AgentLoop

        response = agent_result.response or ""
        validation_prompt_text = _build_validation_prompt(
            validation_prompt,
            response,
        )

        best_agent_result = agent_result
        last_critique = None

        for attempt in range(1, max_val_retries + 2):
            try:
                val_client = get_isolated_ffai_fn(prompt.get("client"))
                val_result = val_client.generate_response(
                    validation_prompt_text,
                    prompt_name=f"{prompt.get('prompt_name', '')}_validation",
                    model=self.config.get("model"),
                    temperature=0.1,
                )
            except Exception as e:
                logger.warning(f"{seq_label} validation LLM call failed: {e}")
                last_critique = f"Validation call failed: {e}"
                if attempt > max_val_retries:
                    builder.with_validation_result(
                        passed=None,
                        attempts=attempt,
                        critique=last_critique,
                    )
                    return
                continue

            val_response = (
                val_result.response.strip()
                if isinstance(val_result.response, str)
                else str(val_result.response).strip()
            )

            if re.match(r"^PASS\s*$", val_response, re.IGNORECASE):
                logger.info(
                    f"{seq_label} validation passed on attempt {attempt}/{max_val_retries + 1}"
                )
                builder.with_validation_result(
                    passed=True,
                    attempts=attempt,
                )
                return

            fail_match = re.match(r"FAIL\s*:\s*(.+)", val_response, re.IGNORECASE | re.DOTALL)
            last_critique = fail_match.group(1).strip() if fail_match else val_response

            logger.info(
                f"{seq_label} validation failed on attempt {attempt}/{max_val_retries + 1}: "
                f"{last_critique[:100]}"
            )

            if attempt > max_val_retries:
                break

            augmented_prompt = (
                f"{original_prompt}\n\n"
                f"[Previous attempt produced this response, which was rejected:]\n"
                f"{best_agent_result.response}\n\n"
                f"[Rejection reason:]\n"
                f"{last_critique}\n\n"
                f"Please try again, addressing the rejection reason."
            )

            retry_ffai = get_isolated_ffai_fn(prompt.get("client"))
            retry_loop = AgentLoop(
                client=retry_ffai.client,
                tool_registry=self.tool_registry,
                max_rounds=max_rounds,
                tool_timeout=tool_timeout,
                continue_on_tool_error=continue_on_tool_error,
            )

            try:
                builder.increment_attempts()
                retry_result = retry_loop.execute(
                    prompt=augmented_prompt,
                    tools=tool_names,
                    tool_choice="auto",
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                if retry_result.status == "success" or retry_result.status == "max_rounds_exceeded":
                    best_agent_result = retry_result
                    builder.with_agent_result(retry_result)
                    if retry_result.status == "success" and retry_result.response:
                        self._record_history(prompt, retry_result.response)

                response = retry_result.response or ""
                validation_prompt_text = _build_validation_prompt(
                    validation_prompt,
                    response,
                )

            except Exception as e:
                logger.warning(f"{seq_label} validation retry execution failed: {e}")
                continue

        logger.warning(f"{seq_label} validation failed after {max_val_retries + 1} attempt(s)")
        builder.with_validation_result(
            passed=False,
            attempts=max_val_retries + 1,
            critique=last_critique,
        )
