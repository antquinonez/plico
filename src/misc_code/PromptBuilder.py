from typing import Any

import jinja2


class PromptTemplate:
    """Individual prompt template with metadata"""

    def __init__(self, template: str, variables: list[str], metadata: dict[str, Any]):
        self.template = template
        self.variables = variables
        self.metadata = metadata


class PromptBuilder:
    def __init__(self):
        self._templates: dict[str, PromptTemplate] = {}
        self._jinja_env = jinja2.Environment()
        self._prompt_cache: dict[str, str] = {}

    def register_template(self, name: str, template: str, variables: list[str]) -> None:
        """Register a reusable prompt template"""
        self._templates[name] = PromptTemplate(template, variables, {})

    def build_prompt(
        self,
        prompt: str,
        history: list[str] | None = None,
        context: dict[str, Any] | None = None,
        template_name: str | None = None,
    ) -> str:
        """Build prompt with history and context injection"""
        # Check cache first
        cache_key = f"{prompt}:{history}:{context}"
        if cache_key in self._prompt_cache:
            return self._prompt_cache[cache_key]

        # Build the prompt
        if template_name and template_name in self._templates:
            prompt = self._render_template(template_name, context or {})

        if history:
            prompt = self._inject_history(prompt, history)

        if context:
            prompt = self._inject_context(prompt, context)

        self._prompt_cache[cache_key] = prompt
        return prompt

    def _render_template(self, template_name: str, variables: dict[str, Any]) -> str:
        """Render a Jinja2 template with variables"""
        template = self._jinja_env.from_string(self._templates[template_name].template)
        return template.render(**variables)

    def _inject_history(self, prompt: str, history: list[str]) -> str:
        """Inject history into prompt with proper formatting"""
        # Implementation from current _build_prompt method
        pass

    def validate_prompt(self, prompt: str) -> dict[str, Any]:
        """Validate prompt structure and return metrics"""
        return {
            "token_estimate": len(prompt.split()),
            "has_history": "<conversation_history>" in prompt,
            "has_context": "<context>" in prompt,
            "valid_structure": True,  # Add validation logic
        }
