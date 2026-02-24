"""
Tests for ConditionEvaluator class.

Run with: python -m pytest tests/test_condition_evaluator.py -v

Note: This test file imports the condition_evaluator module directly to avoid
triggering imports from src/__init__.py which requires polars.
"""

import pytest
import sys
import os
import importlib.util

# Import condition_evaluator directly to avoid polars dependency
_spec = importlib.util.spec_from_file_location(
    "condition_evaluator",
    os.path.join(
        os.path.dirname(__file__), "..", "src", "orchestrator", "condition_evaluator.py"
    ),
)
_ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ce)
ConditionEvaluator = _ce.ConditionEvaluator


class TestConditionEvaluator:
    """Tests for ConditionEvaluator class."""

    def create_results(self, **kwargs) -> dict:
        """Create a mock results dict with default values."""
        defaults = {
            "status": "success",
            "response": "test response",
            "attempts": 1,
            "error": "",
        }
        # Only compute has_response if not explicitly provided and response is set
        if "has_response" not in kwargs:
            response_val = kwargs.get("response", defaults["response"])
            defaults["has_response"] = (
                response_val is not None and len(str(response_val).strip()) > 0
            )
        defaults.update(kwargs)
        return defaults

    # ========================================
    # Basic Condition Evaluation
    # ========================================

    def test_empty_condition_returns_true(self):
        """Empty conditions should always return True."""
        evaluator = ConditionEvaluator({})
        result, error = evaluator.evaluate("")
        assert result is True
        assert error is None

    def test_whitespace_condition_returns_true(self):
        """Whitespace-only conditions should return True."""
        evaluator = ConditionEvaluator({})
        result, error = evaluator.evaluate("   ")
        assert result is True
        assert error is None

    def test_status_equality_success(self):
        """Test status equality check for success."""
        results = {"step1": self.create_results(status="success")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.status}} == "success"')
        assert result is True
        assert error is None

    def test_status_equality_failed(self):
        """Test status equality check for failed."""
        results = {"step1": self.create_results(status="failed")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.status}} == "failed"')
        assert result is True
        assert error is None

    def test_status_inequality(self):
        """Test status inequality checks."""
        results = {"step1": self.create_results(status="success")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.status}} != "failed"')
        assert result is True
        assert error is None

    def test_response_contains(self):
        """Test response substring checks."""
        results = {
            "step1": self.create_results(response="The analysis shows positive results")
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"positive" in {{step1.response}}')
        assert result is True
        assert error is None

    def test_response_not_contains(self):
        """Test response not contains check."""
        results = {"step1": self.create_results(response="positive results")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"negative" not in {{step1.response}}')
        assert result is True
        assert error is None

    # ========================================
    # Boolean Operators
    # ========================================

    def test_and_operator_both_true(self):
        """Test AND operator when both conditions are true."""
        results = {
            "step1": self.create_results(status="success"),
            "step2": self.create_results(status="success"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{step1.status}} == "success" and {{step2.status}} == "success"'
        )
        assert result is True
        assert error is None

    def test_and_operator_one_false(self):
        """Test AND operator when one condition is false."""
        results = {
            "step1": self.create_results(status="success"),
            "step2": self.create_results(status="failed"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{step1.status}} == "success" and {{step2.status}} == "success"'
        )
        assert result is False
        assert error is None

    def test_or_operator_one_true(self):
        """Test OR operator when one condition is true."""
        results = {
            "step1": self.create_results(status="failed"),
            "step2": self.create_results(status="success"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{step1.status}} == "success" or {{step2.status}} == "success"'
        )
        assert result is True
        assert error is None

    def test_or_operator_both_false(self):
        """Test OR operator when both conditions are false."""
        results = {
            "step1": self.create_results(status="failed"),
            "step2": self.create_results(status="failed"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{step1.status}} == "success" or {{step2.status}} == "success"'
        )
        assert result is False
        assert error is None

    def test_not_operator(self):
        """Test NOT boolean operator."""
        results = {"step1": self.create_results(has_response=False)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("not {{step1.has_response}}")
        assert result is True
        assert error is None

    def test_complex_boolean_expression(self):
        """Test complex boolean expressions with parentheses."""
        results = {
            "a": self.create_results(status="success"),
            "b": self.create_results(status="failed"),
            "c": self.create_results(status="success"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '({{a.status}} == "success" or {{b.status}} == "success") and {{c.status}} == "success"'
        )
        assert result is True
        assert error is None

    # ========================================
    # Numeric Comparisons
    # ========================================

    def test_attempts_greater_than(self):
        """Test numeric greater than comparison."""
        results = {"step1": self.create_results(attempts=2)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.attempts}} > 1")
        assert result is True
        assert error is None

    def test_attempts_greater_equal(self):
        """Test numeric greater or equal comparison."""
        results = {"step1": self.create_results(attempts=2)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.attempts}} >= 2")
        assert result is True
        assert error is None

    def test_attempts_less_than(self):
        """Test numeric less than comparison."""
        results = {"step1": self.create_results(attempts=2)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.attempts}} < 3")
        assert result is True
        assert error is None

    def test_attempts_equality(self):
        """Test numeric equality comparison."""
        results = {"step1": self.create_results(attempts=2)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.attempts}} == 2")
        assert result is True
        assert error is None

    # ========================================
    # Helper Functions
    # ========================================

    def test_len_function(self):
        """Test len() function."""
        results = {"step1": self.create_results(response="Hello World")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("len({{step1.response}}) == 11")
        assert result is True
        assert error is None

    def test_len_function_comparison(self):
        """Test len() with comparison operators."""
        results = {"step1": self.create_results(response="Hello World")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("len({{step1.response}}) > 5")
        assert result is True
        assert error is None

    def test_lower_function(self):
        """Test lower() function."""
        results = {"step1": self.create_results(response="YES")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('lower({{step1.response}}) == "yes"')
        assert result is True
        assert error is None

    def test_upper_function(self):
        """Test upper() function."""
        results = {"step1": self.create_results(response="yes")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('upper({{step1.response}}) == "YES"')
        assert result is True
        assert error is None

    def test_trim_function(self):
        """Test trim() function."""
        results = {"step1": self.create_results(response="  hello  ")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('trim({{step1.response}}) == "hello"')
        assert result is True
        assert error is None

    # ========================================
    # Edge Cases
    # ========================================

    def test_unknown_prompt_name_returns_error(self):
        """Test that unknown prompt names return error."""
        evaluator = ConditionEvaluator({})

        result, error = evaluator.evaluate('{{unknown.status}} == "success"')
        assert result is False
        assert error is not None
        assert "unknown prompt name" in error.lower()

    def test_null_response(self):
        """Test handling of null/None response."""
        results = {"step1": self.create_results(response=None)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.status}} == "success"')
        assert result is True
        assert error is None

    def test_response_with_special_characters(self):
        """Test handling of special characters in response."""
        results = {
            "step1": self.create_results(
                response='Response with "quotes" and \\backslash'
            )
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"quotes" in {{step1.response}}')
        assert result is True
        assert error is None

    def test_response_with_newlines(self):
        """Test handling of newlines in response."""
        results = {"step1": self.create_results(response="Line 1\nLine 2\nLine 3")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"Line 2" in {{step1.response}}')
        assert result is True
        assert error is None

    def test_empty_response(self):
        """Test handling of empty response."""
        results = {"step1": self.create_results(response="")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("len({{step1.response}}) == 0")
        assert result is True
        assert error is None

    # ========================================
    # Security Tests
    # ========================================

    def test_no_code_execution(self):
        """Test that code injection is prevented."""
        results = {"step1": self.create_results(status="success")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('__import__("os").system("echo hacked")')
        assert result is False
        assert error is not None

    def test_no_arbitrary_function_calls(self):
        """Test that arbitrary function calls are blocked."""
        results = {"step1": self.create_results(status="success")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('open("/etc/passwd")')
        assert result is False
        assert error is not None

    def test_only_whitelisted_functions(self):
        """Test that only whitelisted functions are allowed."""
        results = {"step1": self.create_results(response="test")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("print({{step1.response}})")
        assert result is False
        assert error is not None
        assert "unknown function" in error.lower()

    # ========================================
    # Extract Referenced Names
    # ========================================

    def test_extract_single_reference(self):
        """Test extracting a single prompt reference."""
        names = ConditionEvaluator.extract_referenced_names(
            '{{step1.status}} == "success"'
        )
        assert names == [("step1", "status")]

    def test_extract_multiple_references(self):
        """Test extracting multiple prompt references."""
        names = ConditionEvaluator.extract_referenced_names(
            '{{step1.status}} == "success" and {{step2.attempts}} > 1'
        )
        assert set(names) == {("step1", "status"), ("step2", "attempts")}

    def test_extract_no_references(self):
        """Test extracting when no references exist."""
        names = ConditionEvaluator.extract_referenced_names("true")
        assert names == []

    # ========================================
    # Syntax Validation
    # ========================================

    def test_validate_valid_syntax(self):
        """Test validation of valid condition syntax."""
        is_valid, error = ConditionEvaluator.validate_syntax(
            '{{step1.status}} == "success"'
        )
        assert is_valid is True
        assert error is None

    def test_validate_empty_condition(self):
        """Test validation of empty condition."""
        is_valid, error = ConditionEvaluator.validate_syntax("")
        assert is_valid is True
        assert error is None

    # ========================================
    # Status Property Tests
    # ========================================

    def test_skipped_status(self):
        """Test condition on skipped status."""
        results = {"step1": self.create_results(status="skipped")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.status}} == "skipped"')
        assert result is True
        assert error is None

    # ========================================
    # Has Response Property Tests
    # ========================================

    def test_has_response_true_with_content(self):
        """Test has_response property when response exists."""
        results = {"step1": self.create_results(response="some content")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.has_response}} == True")
        assert result is True
        assert error is None

    def test_has_response_false_empty(self):
        """Test has_response property when response is empty."""
        results = {"step1": self.create_results(response="")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.has_response}} == False")
        assert result is True
        assert error is None

    def test_has_response_false_none(self):
        """Test has_response property when response is None."""
        results = {"step1": self.create_results(response=None)}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.has_response}} == False")
        assert result is True
        assert error is None

    def test_has_response_false_whitespace(self):
        """Test has_response property when response is only whitespace."""
        results = {"step1": self.create_results(response="   ")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.has_response}} == False")
        assert result is True
        assert error is None

    # ========================================
    # Error Property Tests
    # ========================================

    def test_error_property_on_failure(self):
        """Test error property when step failed."""
        results = {
            "step1": self.create_results(status="failed", error="Connection timeout")
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.error}} != ""')
        assert result is True
        assert error is None

    def test_error_property_on_success(self):
        """Test error property when step succeeded."""
        results = {"step1": self.create_results(status="success", error="")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.error}} == ""')
        assert result is True
        assert error is None
