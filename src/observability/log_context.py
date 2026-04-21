# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Thread-local logging context for batch_name and prompt_name."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar

_batch_name: ContextVar[str] = ContextVar("batch_name", default="-")
_prompt_name: ContextVar[str] = ContextVar("prompt_name", default="-")


def set_log_context(batch_name: str | None = None, prompt_name: str | None = None) -> None:
    if batch_name is not None:
        _batch_name.set(batch_name)
    if prompt_name is not None:
        _prompt_name.set(prompt_name)


def clear_log_context() -> None:
    _batch_name.set("-")
    _prompt_name.set("-")


@contextmanager
def log_context(batch_name: str | None = None, prompt_name: str | None = None):
    tokens = []
    if batch_name is not None:
        tokens.append((_batch_name, _batch_name.set(batch_name)))
    if prompt_name is not None:
        tokens.append((_prompt_name, _prompt_name.set(prompt_name)))
    try:
        yield
    finally:
        for var, token in tokens:
            var.reset(token)


class LogContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.batch_name = _batch_name.get()
        record.prompt_name = _prompt_name.get()
        return True


class ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.batch_name = getattr(record, "batch_name", _batch_name.get())
        record.prompt_name = getattr(record, "prompt_name", _prompt_name.get())
        return super().format(record)
