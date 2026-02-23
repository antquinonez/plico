import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Set, Callable

from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .workbook_builder import WorkbookBuilder

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
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.debug(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
                )

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
            "response": None,
            "status": "pending",
            "attempts": 0,
            "error": None,
        }

        for attempt in range(1, max_retries + 1):
            result["attempts"] = attempt

            try:
                logger.info(
                    f"Executing sequence {prompt['sequence']} (attempt {attempt})"
                )

                response = self.ffai.generate_response(
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

        if self.concurrency > 1:
            self.execute_parallel()
        else:
            self.execute()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_sheet = f"results_{timestamp}"

        self.builder.write_results(self.results, results_sheet)

        logger.info(f"Orchestration complete. Results in sheet: {results_sheet}")
        return results_sheet

    def get_summary(self) -> Dict[str, Any]:
        """Get execution summary."""
        if not self.results:
            return {"status": "not_run"}

        return {
            "total_prompts": len(self.results),
            "successful": sum(1 for r in self.results if r["status"] == "success"),
            "failed": sum(1 for r in self.results if r["status"] == "failed"),
            "total_attempts": sum(r["attempts"] for r in self.results),
            "workbook": self.workbook_path,
        }
