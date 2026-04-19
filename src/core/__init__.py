# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Core FFAI infrastructure: client abstraction, prompt assembly, history, and export."""

from .client_base import FFAIClientBase
from .history import ConversationHistory, OrderedPromptHistory, PermanentHistory
from .history_exporter import HistoryExporter
from .prompt_builder import PromptBuilder
from .prompt_utils import extract_json_field, interpolate_prompt
from .response_context import ResponseContext
from .response_result import ResponseResult
from .response_utils import clean_response, extract_json

__all__ = [
    "ConversationHistory",
    "FFAIClientBase",
    "HistoryExporter",
    "OrderedPromptHistory",
    "PermanentHistory",
    "PromptBuilder",
    "ResponseContext",
    "ResponseResult",
    "clean_response",
    "extract_json",
    "extract_json_field",
    "interpolate_prompt",
]
