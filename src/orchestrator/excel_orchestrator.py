import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from ..FFAI import FFAI
from ..FFAIClientBase import FFAIClientBase
from .workbook_builder import WorkbookBuilder

logger = logging.getLogger(__name__)


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
    ):
        self.workbook_path = workbook_path
        self.client = client
        self.config_overrides = config_overrides or {}
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

        for prompt in self.prompts:
            result = self._execute_prompt(prompt)
            self.results.append(result)

        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = sum(1 for r in self.results if r["status"] == "failed")

        logger.info(f"Execution complete: {successful} succeeded, {failed} failed")
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
