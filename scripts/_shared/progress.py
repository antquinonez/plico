# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Progress indicator for CLI scripts."""

import sys
import time


class ProgressIndicator:
    """Console progress indicator for orchestration execution."""

    def __init__(self, total: int, show_names: bool = True):
        self.total = total
        self.start_time = time.time()
        self.last_update = 0
        self.show_names = show_names
        self.running = 0

        self.completed = 0
        self.success = 0
        self.failed = 0

    def update(
        self,
        completed: int,
        total: int,
        success: int,
        failed: int,
        current_name: str | None = None,
        running: int = 0,
    ) -> None:
        now = time.time()
        if now - self.last_update < 0.1 and completed < total:
            return
        self.last_update = now
        self.running = running
        self.completed = completed
        self.success = success
        self.failed = failed

        pct = (completed / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        elapsed = now - self.start_time
        if completed > 0 and completed < total:
            eta = (elapsed / completed) * (total - completed)
            if eta > 60:
                eta_str = f"ETA: {int(eta // 60)}m {int(eta % 60)}s"
            else:
                eta_str = f"ETA: {int(eta)}s"
        elif completed == total:
            if elapsed > 60:
                eta_str = f"Done: {int(elapsed // 60)}m {int(elapsed % 60)}s"
            else:
                eta_str = f"Done: {int(elapsed)}s"
        else:
            eta_str = "ETA: --"
        status = f"\r[{bar}] {completed}/{total} ({pct:.0f}%) | ✓{success} ✗{failed}"
        if self.show_names and current_name:
            name_display = current_name[:20] if len(current_name) > 20 else current_name
            status += f" | →{name_display}"
        if running > 0:
            status += f" | ⏳{running}"
        status += f" | {eta_str}"
        sys.stdout.write(status)
        sys.stdout.flush()
        self.last_update = now

    def finish(self) -> None:
        sys.stdout.write("\n")
        sys.stdout.flush()
