"""Safe condition expression evaluation for conditional prompt execution.

Uses AST parsing to safely evaluate conditions without eval()/exec(),
supporting comparisons, boolean logic, and function calls.
"""

import ast
import logging
import operator
import re
from typing import Any

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """Safely evaluates condition expressions for conditional prompt execution.

    Security model: Never uses eval() or exec() on user input. Conditions are
    parsed using AST and evaluated using a restricted set of operators.

    Syntax:
        {{prompt_name.property}} == "value"
        {{prompt_name.property}} != "value"
        {{prompt_name.property}} contains "substring"
        {{prompt_name.property}} not contains "substring"
        {{prompt_name.property}} matches "regex"
        len({{prompt_name.response}}) > 100
        {{a.status}} == "success" and {{b.status}} == "success"
        {{a.status}} == "success" or {{b.status}} == "success"
        not {{prompt_name.has_response}}

    Available properties:
        - status: "success", "failed", "skipped"
        - response: The AI response text
        - attempts: Number of retry attempts (int)
        - error: Error message if failed (str)
        - has_response: True if response exists and non-empty (bool)
    """

    ALLOWED_OPERATORS = {
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
    }

    ALLOWED_UNARY_OPERATORS = {
        ast.Not: operator.not_,
    }

    ALLOWED_FUNCTIONS = {
        "len": len,
        "lower": lambda s: str(s).lower() if s is not None else "",
        "upper": lambda s: str(s).upper() if s is not None else "",
        "trim": lambda s: str(s).strip() if s is not None else "",
        "int": lambda x: int(x) if x is not None else 0,
        "float": lambda x: float(x) if x is not None else 0.0,
        "str": lambda x: str(x) if x is not None else "",
    }

    VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\.(\w+)\}\}")

    def __init__(self, results_by_name: dict[str, dict[str, Any]]) -> None:
        """Initialize evaluator with completed prompt results.

        Args:
            results_by_name: Dict mapping prompt_name to result dict with keys:
                - status: str
                - response: str
                - attempts: int
                - error: str
                - has_response: bool

        """
        self.results_by_name = results_by_name

    def evaluate(self, condition: str) -> tuple[bool, str | None]:
        """Evaluate a condition expression.

        Args:
            condition: The condition string to evaluate

        Returns:
            Tuple of (result, error_message)
            - result: True if condition passes, False otherwise
            - error_message: None if successful, error string if failed

        """
        if not condition or not condition.strip():
            return True, None

        try:
            resolved = self._resolve_variables(condition)
            logger.debug(f"Resolved condition: '{condition}' -> '{resolved}'")

            if not resolved.strip():
                return True, None

            tree = ast.parse(resolved, mode="eval")
            result = self._eval_node(tree.body)

            logger.debug(f"Condition result: {result}")
            return bool(result), None

        except SyntaxError as e:
            error_msg = f"Syntax error in condition: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Condition evaluation error: {error_msg}")
            return False, error_msg

    def _resolve_variables(self, text: str) -> str:
        """Replace {{name.property}} with actual values.

        Converts variable references to Python literals that can be parsed.
        """

        def replacer(match: re.Match) -> str:
            name = match.group(1)
            prop = match.group(2)

            if name not in self.results_by_name:
                raise ValueError(f"Unknown prompt name in condition: '{name}'")

            result = self.results_by_name[name]
            value = result.get(prop)

            computed_value = self._compute_property(result, prop, value)

            return self._value_to_literal(computed_value)

        return self.VARIABLE_PATTERN.sub(replacer, text)

    def _compute_property(self, result: dict[str, Any], prop: str, value: Any) -> Any:  # noqa: ANN401
        """Compute property value, including computed properties."""
        if prop == "has_response":
            if isinstance(value, bool):
                return value
            response = result.get("response")
            return response is not None and len(str(response).strip()) > 0

        if prop == "status":
            return value if value else "pending"

        if prop == "response":
            if value is None:
                return ""
            return str(value)

        if prop == "error":
            return str(value) if value else ""

        if prop == "attempts":
            return int(value) if value is not None else 0

        return value

    def _value_to_literal(self, value: Any) -> str:  # noqa: ANN401
        """Convert a value to a Python literal string."""
        if value is None:
            return '""'
        elif isinstance(value, bool):
            return "True" if value else "False"
        elif isinstance(value, int | float):
            return str(value)
        elif isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            escaped = escaped.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            return f'"{escaped}"'
        else:
            escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

    def _eval_node(self, node: ast.AST) -> Any:  # noqa: ANN401
        """Recursively evaluate an AST node."""
        if isinstance(node, ast.Constant):
            return node.value

        # Python < 3.8 compatibility (deprecated in 3.8, removed in 3.14)
        if hasattr(ast, "Str") and isinstance(node, ast.Str):
            return node.s

        if hasattr(ast, "Num") and isinstance(node, ast.Num):
            return node.n

        if hasattr(ast, "NameConstant") and isinstance(node, ast.NameConstant):
            return node.value

        if isinstance(node, ast.Name):
            name = node.id
            if name in ("True", "true"):
                return True
            if name in ("False", "false"):
                return False
            if name == "None":
                return None
            raise ValueError(f"Unknown identifier: '{name}'")

        if isinstance(node, ast.Compare):
            return self._eval_compare(node)

        if isinstance(node, ast.BoolOp):
            return self._eval_boolop(node)

        if isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node)

        if isinstance(node, ast.Call):
            return self._eval_call(node)

        if isinstance(node, ast.BinOp):
            return self._eval_binop(node)

        if isinstance(node, ast.IfExp):
            return self._eval_ifexp(node)

        raise ValueError(f"Unsupported expression type: {type(node).__name__}")

    def _eval_compare(self, node: ast.Compare) -> bool:
        """Evaluate comparison operations."""
        left = self._eval_node(node.left)

        for op, comparator in zip(node.ops, node.comparators):
            right = self._eval_node(comparator)

            if isinstance(op, ast.In):
                if not isinstance(left, str) or not isinstance(right, str):
                    raise ValueError("'contains' operator requires string values")
                result = left in right
            elif isinstance(op, ast.NotIn):
                if not isinstance(left, str) or not isinstance(right, str):
                    raise ValueError("'not contains' operator requires string values")
                result = left not in right
            elif type(op) in self.ALLOWED_OPERATORS:
                result = self.ALLOWED_OPERATORS[type(op)](left, right)
            else:
                raise ValueError(f"Unsupported comparison operator: {type(op).__name__}")

            left = result

        return bool(left)

    def _eval_boolop(self, node: ast.BoolOp) -> bool:
        """Evaluate boolean operations (and, or)."""
        values = [self._eval_node(v) for v in node.values]

        if isinstance(node.op, ast.And):
            return all(values)
        elif isinstance(node.op, ast.Or):
            return any(values)
        else:
            raise ValueError(f"Unsupported boolean operator: {type(node.op).__name__}")

    def _eval_unaryop(self, node: ast.UnaryOp) -> Any:  # noqa: ANN401
        """Evaluate unary operations (not)."""
        operand = self._eval_node(node.operand)

        if isinstance(node.op, ast.Not):
            return not operand
        elif type(node.op) in self.ALLOWED_UNARY_OPERATORS:
            return self.ALLOWED_UNARY_OPERATORS[type(node.op)](operand)
        else:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")

    def _eval_call(self, node: ast.Call) -> Any:  # noqa: ANN401
        """Evaluate function calls."""
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed")

        func_name = node.func.id
        if func_name not in self.ALLOWED_FUNCTIONS:
            raise ValueError(f"Unknown function: '{func_name}'")

        args = [self._eval_node(arg) for arg in node.args]

        if node.keywords:
            raise ValueError("Keyword arguments are not supported in conditions")

        return self.ALLOWED_FUNCTIONS[func_name](*args)

    def _eval_binop(self, node: ast.BinOp) -> Any:  # noqa: ANN401
        """Evaluate binary operations (for 'matches' via % operator)."""
        left = self._eval_node(node.left)
        right = self._eval_node(node.right)

        if isinstance(node.op, ast.Mod):
            if not isinstance(left, str) or not isinstance(right, str):
                raise ValueError("'matches' operator requires string values")
            try:
                return bool(re.search(right, left))
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")

        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        else:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")

    def _eval_ifexp(self, node: ast.IfExp) -> Any:  # noqa: ANN401
        """Evaluate ternary if expression."""
        test = self._eval_node(node.test)
        if test:
            return self._eval_node(node.body)
        else:
            return self._eval_node(node.orelse)

    @classmethod
    def extract_referenced_names(cls, condition: str) -> list:
        """Extract all prompt names referenced in a condition.

        Args:
            condition: The condition string

        Returns:
            List of prompt names referenced via {{name.property}} syntax

        """
        if not condition:
            return []
        return list(set(cls.VARIABLE_PATTERN.findall(condition)))

    @classmethod
    def validate_syntax(cls, condition: str) -> tuple[bool, str | None]:
        """Validate condition syntax without evaluating.

        Args:
            condition: The condition string to validate

        Returns:
            Tuple of (is_valid, error_message)

        """
        if not condition or not condition.strip():
            return True, None

        try:
            dummy_results = {}
            for name, _prop in cls.VARIABLE_PATTERN.findall(condition):
                dummy_results[name] = {
                    "status": "success",
                    "response": "test",
                    "attempts": 1,
                    "error": "",
                    "has_response": True,
                }

            evaluator = cls(dummy_results)
            evaluator.evaluate(condition)
            return True, None

        except Exception as e:
            return False, str(e)
