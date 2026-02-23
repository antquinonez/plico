import os
import re
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Callable

from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .workbook_builder import WorkbookBuilder
from .client_registry import ClientRegistry

logger = logging.getLogger(__name__)


@dataclass
class PromptNode:
    sequence: int
    prompt: Dict[str, Any]
    dependencies: Set[int] = field(default_factory=set)
    level: int = 0


@dataclass
class ExecutionState:
    completed: Set[int] = field(default_factory=set)
    in_progress: Set[int] = field(default_factory=set)
    pending: Dict[int, PromptNode] = field(default_factory=dict)
    results: List[Dict[str, Any]] = field(default_factory=list)
    results_lock: threading.Lock = field(default_factory=threading.Lock)
    success_count: int = 0
    failed_count: int = 0
    results_by_name: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    current_name: str = ""
    running_count: int = 0


class ExcelOrchestrator:
    """
    Orchestrates AI prompt execution via Excel workbook.

    Usage:
        from src.Clients.FFMistralSmall import FFMistralSmall
        from src.orchestrator import ExcelOrchestrator

        client = FFMistralSmall(api_key="...")
        orchestrator = ExcelOrchestrator("prompts.xlsx", client=client)
        orchestrator.run()
    """

    def __init__(
        self,
        workbook_path: str,
        client: FFAIClientBase,
        config_overrides: Optional[Dict[str, Any]] = None,
        concurrency: int = 2,
        progress_callback: Optional[Callable[..., None]] = None,
    ):
        self.workbook_path = workbook_path
        self.client = client
        self.config_overrides = config_overrides or {}
        self.concurrency = min(max(1, concurrency), 10)
        self.progress_callback = progress_callback
        self.builder = WorkbookBuilder(workbook_path)

        self.config: Dict[str, Any] = {}
        self.prompts: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self.ffai: Optional[FFAI] = None

        self.batch_data: List[Dict[str, Any]] = []
        self.is_batch_mode: bool = False

        self.client_registry: Optional[ClientRegistry] = None
        self.has_multi_client: bool = False

    def _init_workbook(self) -> None:
        """Initialize workbook - create if not exists, validate if exists."""
        if not os.path.exists(self.workbook_path):
            logger.info(f"Workbook not found, creating template: {self.workbook_path}")
            self.builder.create_template_workbook()
        else:
            logger.info(f"Workbook found, validating: {self.workbook_path}")
            self.builder.validate_workbook()

    def _load_config(self) -> None:
        """Load configuration, apply overrides."""
        self.config = self.builder.load_config()
        self.config.update(self.config_overrides)

        logger.info(
            f"Configuration loaded: model={self.config.get('model')}, max_retries={self.config.get('max_retries')}"
        )

    def _init_client(self) -> None:
        """Initialize FFAI wrapper with configured client."""
        self.ffai = FFAI(self.client)
        logger.info("FFAI wrapper initialized")

    def _init_client_registry(self) -> None:
        """Initialize client registry with clients from workbook."""
        self.client_registry = ClientRegistry(self.client)

        if self.builder.has_clients_sheet():
            clients = self.builder.load_clients()
            for client_config in clients:
                name = client_config.get("name")
                client_type = client_config.get("client_type")
                if name and client_type:
                    config = {
                        k: v
                        for k, v in client_config.items()
                        if k not in ("name", "client_type")
                    }
                    try:
                        self.client_registry.register(name, client_type, config)
                    except ValueError as e:
                        logger.warning(f"Failed to register client '{name}': {e}")

            logger.info(
                f"Client registry initialized with {len(self.client_registry.get_registered_names())} clients"
            )

        self.has_multi_client = any(p.get("client") for p in self.prompts)
        if self.has_multi_client:
            logger.info("Multi-client mode enabled - prompts specify client names")

    def _validate_dependencies(self) -> None:
        """Validate all history dependencies reference existing prompt_names."""
        prompt_names = {p["prompt_name"] for p in self.prompts if p.get("prompt_name")}
        prompt_names_by_sequence = {}

        for p in self.prompts:
            seq = p["sequence"]
            name = p.get("prompt_name")
            if name:
                prompt_names_by_sequence[seq] = name

        errors = []
        for prompt in self.prompts:
            seq = prompt["sequence"]
            history = prompt.get("history")

            if not history:
                continue

            for dep_name in history:
                if dep_name not in prompt_names:
                    errors.append(
                        f"Sequence {seq}: dependency '{dep_name}' not found in any prompt_name"
                    )
                else:
                    dep_sequence = next(
                        (
                            p["sequence"]
                            for p in self.prompts
                            if p.get("prompt_name") == dep_name
                        ),
                        None,
                    )
                    if dep_sequence and dep_sequence >= seq:
                        errors.append(
                            f"Sequence {seq}: dependency '{dep_name}' (seq {dep_sequence}) "
                            f"must be defined before sequence {seq}"
                        )

        if errors:
            raise ValueError("Dependency validation failed:\n" + "\n".join(errors))

        logger.info("Dependency validation passed")

    def _build_execution_graph(self) -> Dict[int, PromptNode]:
        """Build dependency graph and assign execution levels."""
        name_to_sequence = {
            p["prompt_name"]: p["sequence"]
            for p in self.prompts
            if p.get("prompt_name")
        }

        nodes = {}
        for prompt in self.prompts:
            seq = prompt["sequence"]
            deps = set()
            if prompt.get("history"):
                for dep_name in prompt["history"]:
                    if dep_name in name_to_sequence:
                        deps.add(name_to_sequence[dep_name])

            nodes[seq] = PromptNode(
                sequence=seq,
                prompt=prompt,
                dependencies=deps,
                level=0,
            )

        for seq, node in nodes.items():
            if node.dependencies:
                max_dep_level = max(nodes[d].level for d in node.dependencies)
                node.level = max_dep_level + 1

        logger.debug(f"Built execution graph with {len(nodes)} nodes")
        for seq, node in sorted(nodes.items()):
            logger.debug(f"  Seq {seq}: level={node.level}, deps={node.dependencies}")

        return nodes

    def _get_ready_prompts(
        self, state: ExecutionState, nodes: Dict[int, PromptNode]
    ) -> List[PromptNode]:
        """Get prompts ready to execute (all dependencies met, not in progress)."""
        ready = []
        for seq, node in nodes.items():
            if seq in state.completed or seq in state.in_progress:
                continue
            if node.dependencies.issubset(state.completed):
                ready.append(node)
        return sorted(ready, key=lambda n: n.sequence)

    def _execute_prompt_isolated(
        self, prompt: Dict[str, Any], state: ExecutionState
    ) -> Dict[str, Any]:
        """Execute a single prompt with completely isolated client clone."""
        max_retries = self.config.get("max_retries", 3)

        result = {
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        client_name = prompt.get("client")

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.debug(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
                    + (f" with client '{client_name}'" if client_name else "")
                )

                if client_name:
                    isolated_client = self.client_registry.clone(client_name)
                else:
                    isolated_client = self.client.clone()
                ffai = FFAI(isolated_client)

                with state.results_lock:
                    for dep_name in prompt.get("history") or []:
                        if dep_name in state.results_by_name:
                            dep_result = state.results_by_name[dep_name]
                            ffai.prompt_attr_history.append(
                                {
                                    "prompt_name": dep_name,
                                    "prompt": dep_result.get("prompt"),
                                    "response": dep_result.get("response"),
                                }
                            )

                response = ffai.generate_response(
                    prompt=prompt["prompt"],
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                result["response"] = response
                result["status"] = "success"
                logger.debug(f"Sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(
                    f"Sequence {prompt['sequence']} failed (attempt {attempt}): {e}"
                )

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def _execute_prompt(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single prompt with retry logic."""
        max_retries = self.config.get("max_retries", 3)

        result = {
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        client_name = prompt.get("client")
        client = self.client_registry.get(client_name) if client_name else self.client
        ffai = FFAI(client) if client_name else self.ffai

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.info(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
                    + (f" with client '{client_name}'" if client_name else "")
                )

                response = ffai.generate_response(
                    prompt=prompt["prompt"],
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                result["response"] = response
                result["status"] = "success"
                logger.info(f"Sequence {prompt['sequence']} succeeded")
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(
                    f"Sequence {prompt['sequence']} failed (attempt {attempt}): {e}"
                )

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def _resolve_variables(self, text: str, data_row: Dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values from data row."""
        if not text:
            return text

        pattern = r"\{\{(\w+)\}\}"

        def replacer(match):
            var_name = match.group(1)
            if var_name in data_row and data_row[var_name] is not None:
                return str(data_row[var_name])
            logger.warning(f"Variable '{var_name}' not found in data row")
            return match.group(0)

        return re.sub(pattern, replacer, text)

    def _resolve_prompt_variables(
        self, prompt: Dict[str, Any], data_row: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve all {{variable}} placeholders in a prompt."""
        resolved = dict(prompt)
        resolved["prompt"] = self._resolve_variables(prompt.get("prompt", ""), data_row)
        if prompt.get("prompt_name"):
            resolved["prompt_name"] = self._resolve_variables(
                prompt["prompt_name"], data_row
            )
        return resolved

    def _resolve_batch_name(self, data_row: Dict[str, Any], batch_id: int) -> str:
        """Generate batch name from data row or default."""
        if "batch_name" in data_row and data_row["batch_name"]:
            name = self._resolve_variables(str(data_row["batch_name"]), data_row)
            return re.sub(r"[^\w\-]", "_", name)[:50]
        return f"batch_{batch_id}"

    def _execute_single_batch(
        self, batch_id: int, data_row: Dict[str, Any], batch_name: str
    ) -> List[Dict[str, Any]]:
        """Execute all prompts for a single batch with resolved variables."""
        results = []

        for prompt in self.prompts:
            resolved_prompt = self._resolve_prompt_variables(prompt, data_row)

            result = self._execute_prompt_with_batch(
                resolved_prompt, batch_id, batch_name
            )
            results.append(result)

            if result["status"] == "failed":
                on_error = self.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(
                        f"Stopping batch execution due to failure at batch {batch_id}"
                    )
                    break

        return results

    def _execute_prompt_with_batch(
        self, prompt: Dict[str, Any], batch_id: int, batch_name: str
    ) -> Dict[str, Any]:
        """Execute a single prompt and tag with batch info."""
        max_retries = self.config.get("max_retries", 3)

        result = {
            "batch_id": batch_id,
            "batch_name": batch_name,
            "sequence": prompt["sequence"],
            "prompt_name": prompt.get("prompt_name"),
            "prompt": prompt["prompt"],
            "history": prompt.get("history"),
            "client": prompt.get("client"),
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        client_name = prompt.get("client")
        client = self.client_registry.get(client_name) if client_name else self.client
        ffai = FFAI(client)

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.info(
                    f"Executing batch {batch_id}, sequence {prompt['sequence']} (attempt {attempt})"
                    + (f" with client '{client_name}'" if client_name else "")
                )

                response = ffai.generate_response(
                    prompt=prompt["prompt"],
                    prompt_name=prompt.get("prompt_name"),
                    history=prompt.get("history"),
                    model=self.config.get("model"),
                    temperature=self.config.get("temperature"),
                    max_tokens=self.config.get("max_tokens"),
                )

                result["response"] = response
                result["status"] = "success"
                logger.info(
                    f"Batch {batch_id}, sequence {prompt['sequence']} succeeded"
                )
                break

            except Exception as e:
                result["error"] = str(e)
                logger.warning(
                    f"Batch {batch_id}, sequence {prompt['sequence']} failed (attempt {attempt}): {e}"
                )

                if attempt == max_retries:
                    result["status"] = "failed"
                    logger.error(
                        f"Batch {batch_id}, sequence {prompt['sequence']} failed after {max_retries} attempts"
                    )

        return result

    def execute(self) -> List[Dict[str, Any]]:
        """Execute all prompts in sequence."""
        self.results = []
        total = len(self.prompts)

        for prompt in self.prompts:
            if self.progress_callback:
                self.progress_callback(
                    len(self.results),
                    total,
                    sum(1 for r in self.results if r["status"] == "success"),
                    sum(1 for r in self.results if r["status"] == "failed"),
                    current_name=prompt.get("prompt_name"),
                    running=1,
                )
            result = self._execute_prompt(prompt)
            self.results.append(result)

        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")

        if self.progress_callback:
            self.progress_callback(
                total,
                total,
                successful,
                failed,
                current_name=None,
                running=0,
            )

        logger.info(f"Execution complete: {successful} succeeded, {failed} failed")
        return self.results

    def execute_parallel(self) -> List[Dict[str, Any]]:
        """Execute prompts in parallel with dependency-aware scheduling."""
        nodes = self._build_execution_graph()
        state = ExecutionState(pending=dict(nodes))

        total = len(nodes)

        def update_progress():
            if self.progress_callback:
                self.progress_callback(
                    len(state.completed),
                    total,
                    state.success_count,
                    state.failed_count,
                    current_name=state.current_name,
                    running=len(state.in_progress),
                )

        logger.info(f"Starting parallel execution with concurrency={self.concurrency}")

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            while len(state.completed) < total:
                ready = self._get_ready_prompts(state, nodes)

                if not ready and not state.in_progress:
                    logger.error(
                        "Deadlock detected: no ready prompts and none in progress"
                    )
                    break

                futures = {}
                for node in ready:
                    if len(state.in_progress) >= self.concurrency:
                        break
                    state.in_progress.add(node.sequence)
                    future = executor.submit(
                        self._execute_prompt_isolated, node.prompt, state
                    )
                    futures[future] = node.sequence

                for future in as_completed(futures):
                    seq = futures[future]
                    try:
                        result = future.result()
                        with state.results_lock:
                            state.results.append(result)
                            state.completed.add(seq)
                            state.current_name = (
                                result.get("prompt_name") or f"seq_{seq}"
                            )
                            if result["status"] == "success":
                                state.success_count += 1
                                if result.get("prompt_name"):
                                    state.results_by_name[result["prompt_name"]] = (
                                        result
                                    )
                            else:
                                state.failed_count += 1
                    except Exception as e:
                        logger.error(f"Unexpected error for sequence {seq}: {e}")
                        with state.results_lock:
                            state.completed.add(seq)
                            state.failed_count += 1
                            state.current_name = (
                                nodes[seq].prompt.get("prompt_name") or f"seq_{seq}"
                            )
                            state.results.append(
                                {
                                    "sequence": seq,
                                    "prompt_name": nodes[seq].prompt.get("prompt_name"),
                                    "prompt": nodes[seq].prompt["prompt"],
                                    "history": nodes[seq].prompt.get("history"),
                                    "response": None,
                                    "status": "failed",
                                    "attempts": 1,
                                    "error": str(e),
                                }
                            )
                    finally:
                        state.in_progress.discard(seq)
                        update_progress()

        state.results.sort(key=lambda r: r["sequence"])
        self.results = state.results

        logger.info(
            f"Parallel execution complete: {state.success_count} succeeded, {state.failed_count} failed"
        )
        return self.results

    def execute_batch(self) -> List[Dict[str, Any]]:
        """Execute all prompts for each batch row sequentially."""
        self.results = []
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        for batch_idx, data_row in enumerate(self.batch_data, start=1):
            batch_name = self._resolve_batch_name(data_row, batch_idx)
            logger.info(f"Starting batch {batch_idx}/{total_batches}: {batch_name}")

            batch_results = self._execute_single_batch(batch_idx, data_row, batch_name)
            self.results.extend(batch_results)

            batch_failed = sum(1 for r in batch_results if r["status"] == "failed")
            if batch_failed > 0:
                on_error = self.config.get("on_batch_error", "continue")
                if on_error == "stop":
                    logger.error(
                        f"Stopping at batch {batch_idx} due to {batch_failed} failures"
                    )
                    break

            if self.progress_callback:
                completed = len(self.results)
                success = sum(1 for r in self.results if r["status"] == "success")
                failed = sum(1 for r in self.results if r["status"] == "failed")
                self.progress_callback(
                    completed,
                    total,
                    success,
                    failed,
                    current_name=f"batch_{batch_idx}",
                    running=1,
                )

        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        logger.info(
            f"Batch execution complete: {successful} succeeded, {failed} failed"
        )
        return self.results

    def execute_batch_parallel(self) -> List[Dict[str, Any]]:
        """Execute batches in parallel, with dependency-aware prompt execution within each batch."""
        total_batches = len(self.batch_data)
        total_prompts = len(self.prompts)
        total = total_batches * total_prompts

        state = ExecutionState()
        results_lock = threading.Lock()

        def execute_single_batch_isolated(batch_idx: int, data_row: Dict[str, Any]):
            batch_name = self._resolve_batch_name(data_row, batch_idx)
            batch_results = []
            batch_results_by_name: Dict[str, Dict[str, Any]] = {}

            nodes = self._build_execution_graph()

            for prompt in self.prompts:
                resolved_prompt = self._resolve_prompt_variables(prompt, data_row)

                max_retries = self.config.get("max_retries", 3)
                result = {
                    "batch_id": batch_idx,
                    "batch_name": batch_name,
                    "sequence": resolved_prompt["sequence"],
                    "prompt_name": resolved_prompt.get("prompt_name"),
                    "prompt": resolved_prompt["prompt"],
                    "history": resolved_prompt.get("history"),
                    "client": resolved_prompt.get("client"),
                    "response": None,
                    "status": "pending",
                    "attempts": 0,
                    "error": None,
                }

                client_name = resolved_prompt.get("client")

                for attempt in range(1, max_retries + 1):
                    result["attempts"] = attempt
                    try:
                        if client_name:
                            isolated_client = self.client_registry.clone(client_name)
                        else:
                            isolated_client = self.client.clone()
                        ffai = FFAI(isolated_client)

                        for dep_name in resolved_prompt.get("history") or []:
                            if dep_name in batch_results_by_name:
                                dep_result = batch_results_by_name[dep_name]
                                ffai.prompt_attr_history.append(
                                    {
                                        "prompt_name": dep_name,
                                        "prompt": dep_result.get("prompt"),
                                        "response": dep_result.get("response"),
                                    }
                                )

                        response = ffai.generate_response(
                            prompt=resolved_prompt["prompt"],
                            prompt_name=resolved_prompt.get("prompt_name"),
                            history=resolved_prompt.get("history"),
                            model=self.config.get("model"),
                            temperature=self.config.get("temperature"),
                            max_tokens=self.config.get("max_tokens"),
                        )

                        result["response"] = response
                        result["status"] = "success"
                        break

                    except Exception as e:
                        result["error"] = str(e)
                        if attempt == max_retries:
                            result["status"] = "failed"

                batch_results.append(result)
                if result["status"] == "success" and result.get("prompt_name"):
                    batch_results_by_name[result["prompt_name"]] = result

                if result["status"] == "failed":
                    on_error = self.config.get("on_batch_error", "continue")
                    if on_error == "stop":
                        break

            return batch_results

        all_results = []
        failed_batches = []

        logger.info(
            f"Starting parallel batch execution with concurrency={self.concurrency}"
        )

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {}
            for batch_idx, data_row in enumerate(self.batch_data, start=1):
                future = executor.submit(
                    execute_single_batch_isolated, batch_idx, data_row
                )
                futures[future] = batch_idx

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_results = future.result()
                    with results_lock:
                        all_results.extend(batch_results)
                        state.success_count += sum(
                            1 for r in batch_results if r["status"] == "success"
                        )
                        state.failed_count += sum(
                            1 for r in batch_results if r["status"] == "failed"
                        )

                    if self.progress_callback:
                        completed = len(all_results)
                        self.progress_callback(
                            completed,
                            total,
                            state.success_count,
                            state.failed_count,
                            current_name=f"batch_{batch_idx}",
                            running=len([f for f in futures if not f.done()]),
                        )

                    batch_failed = sum(
                        1 for r in batch_results if r["status"] == "failed"
                    )
                    if batch_failed > 0:
                        failed_batches.append(batch_idx)

                except Exception as e:
                    logger.error(f"Batch {batch_idx} failed with exception: {e}")
                    failed_batches.append(batch_idx)

        all_results.sort(key=lambda r: (r["batch_id"], r["sequence"]))
        self.results = all_results

        logger.info(
            f"Parallel batch execution complete: {state.success_count} succeeded, "
            f"{state.failed_count} failed across {total_batches} batches"
        )
        if failed_batches:
            logger.warning(f"Failed batches: {failed_batches}")

        return self.results

    def run(self) -> str:
        """
        Main entry point. Initialize, validate, execute, write results.

        Returns:
            Name of the results sheet created.
        """
        self._init_workbook()
        self._load_config()
        self.prompts = self.builder.load_prompts()
        self._validate_dependencies()
        self._init_client()
        self._init_client_registry()

        self.batch_data = self.builder.load_data()
        self.is_batch_mode = len(self.batch_data) > 0

        if self.is_batch_mode:
            logger.info(f"Running in batch mode with {len(self.batch_data)} batches")
            if self.concurrency > 1:
                self.execute_batch_parallel()
            else:
                self.execute_batch()
        else:
            if self.concurrency > 1:
                self.execute_parallel()
            else:
                self.execute()

        batch_output = self.config.get("batch_output", "combined")

        if self.is_batch_mode and batch_output == "separate_sheets":
            return self._write_separate_batch_results()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_sheet = f"results_{timestamp}"
            self.builder.write_results(self.results, results_sheet)
            logger.info(f"Orchestration complete. Results in sheet: {results_sheet}")
            return results_sheet

    def _write_separate_batch_results(self) -> str:
        """Write results to separate sheets per batch."""
        batches: Dict[int, List[Dict[str, Any]]] = {}
        for result in self.results:
            batch_id = result.get("batch_id", 0)
            if batch_id not in batches:
                batches[batch_id] = []
            batches[batch_id].append(result)

        sheet_names = []
        for batch_id in sorted(batches.keys()):
            batch_results = batches[batch_id]
            batch_name = batch_results[0].get("batch_name", f"batch_{batch_id}")
            sheet_name = self.builder.write_batch_results(batch_results, batch_name)
            sheet_names.append(sheet_name)

        logger.info(f"Wrote {len(sheet_names)} batch result sheets")
        return ", ".join(sheet_names)

    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        if not self.results:
            return {"status": "not_run"}

        summary = {
            "total_prompts": len(self.results),
            "successful": sum(1 for r in self.results if r["status"] == "success"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "total_attempts": sum(r["attempts"] for r in self.results),
            "workbook": self.workbook_path,
        }

        if self.is_batch_mode:
            batch_ids = set(r.get("batch_id", 0) for r in self.results)
            summary["total_batches"] = len(batch_ids)
            summary["batch_mode"] = True

            batch_failures = {}
            for r in self.results:
                if r["status"] == "failed":
                    batch_id = r.get("batch_id", 0)
                    batch_failures[batch_id] = batch_failures.get(batch_id, 0) + 1
            if batch_failures:
                summary["batches_with_failures"] = batch_failures

        return summary
