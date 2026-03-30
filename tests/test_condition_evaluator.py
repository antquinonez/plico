# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""
Tests for ConditionEvaluator class.

Run with: python -m pytest tests/test_condition_evaluator.py -v

Note: This test file imports the condition_evaluator module directly to avoid
triggering imports from src/__init__.py which requires polars.
"""

import importlib.util
import os

# Import condition_evaluator directly to avoid polars dependency
_spec = importlib.util.spec_from_file_location(
    "condition_evaluator",
    os.path.join(os.path.dirname(__file__), "..", "src", "orchestrator", "condition_evaluator.py"),
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
        results = {"step1": self.create_results(response="The analysis shows positive results")}
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
        results = {"step1": self.create_results(response='Response with "quotes" and \\backslash')}
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
        names = ConditionEvaluator.extract_referenced_names('{{step1.status}} == "success"')
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
        is_valid, error = ConditionEvaluator.validate_syntax('{{step1.status}} == "success"')
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
        results = {"step1": self.create_results(status="failed", error="Connection timeout")}
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

    # ========================================
    # String Method Tests
    # ========================================

    def test_startswith_method(self):
        """Test .startswith() string method."""
        results = {"step1": self.create_results(response="SUCCESS: Operation completed")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.startswith("SUCCESS")')
        assert result is True
        assert error is None

    def test_startswith_method_false(self):
        """Test .startswith() string method returns False correctly."""
        results = {"step1": self.create_results(response="ERROR: Something went wrong")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.startswith("SUCCESS")')
        assert result is False
        assert error is None

    def test_endswith_method(self):
        """Test .endswith() string method."""
        results = {"step1": self.create_results(response="file.json")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.endswith(".json")')
        assert result is True
        assert error is None

    def test_lower_method(self):
        """Test .lower() string method."""
        results = {"step1": self.create_results(response="YES")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.lower() == "yes"')
        assert result is True
        assert error is None

    def test_upper_method(self):
        """Test .upper() string method."""
        results = {"step1": self.create_results(response="yes")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.upper() == "YES"')
        assert result is True
        assert error is None

    def test_strip_method(self):
        """Test .strip() string method."""
        results = {"step1": self.create_results(response="  hello  ")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.strip() == "hello"')
        assert result is True
        assert error is None

    def test_replace_method(self):
        """Test .replace() string method."""
        results = {"step1": self.create_results(response="hello world")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{step1.response}}.replace("world", "there") == "hello there"'
        )
        assert result is True
        assert error is None

    def test_count_method(self):
        """Test .count() string method."""
        results = {"step1": self.create_results(response="error error error")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.count("error") == 3')
        assert result is True
        assert error is None

    def test_split_method_with_subscript(self):
        """Test .split() string method with subscript access."""
        results = {"step1": self.create_results(response="a,b,c")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.split(",")[0] == "a"')
        assert result is True
        assert error is None

    def test_find_method(self):
        """Test .find() string method."""
        results = {"step1": self.create_results(response="hello world")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.find("world") == 6')
        assert result is True
        assert error is None

    def test_isdigit_method(self):
        """Test .isdigit() string method."""
        results = {"step1": self.create_results(response="12345")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.response}}.isdigit() == True")
        assert result is True
        assert error is None

    def test_isalpha_method(self):
        """Test .isalpha() string method."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.response}}.isalpha() == True")
        assert result is True
        assert error is None

    def test_chained_string_methods(self):
        """Test chained string method calls."""
        results = {"step1": self.create_results(response="  SUCCESS  ")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('{{step1.response}}.strip().lower() == "success"')
        assert result is True
        assert error is None

    def test_private_method_blocked(self):
        """Test that private methods are blocked."""
        results = {"step1": self.create_results(response="test")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("{{step1.response}}.__class__")
        assert result is False
        assert error is not None
        assert "private" in error.lower()

    # ========================================
    # JSON Function Tests
    # ========================================

    def test_json_get_simple_key(self):
        """Test json_get with simple key."""
        results = {"step1": self.create_results(response='{"status": "ok", "count": 42}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "status") == "ok"')
        assert result is True
        assert error is None

    def test_json_get_nested_key(self):
        """Test json_get with nested key using dot notation."""
        results = {"step1": self.create_results(response='{"data": {"user": {"name": "Alice"}}}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            'json_get({{step1.response}}, "data.user.name") == "Alice"'
        )
        assert result is True
        assert error is None

    def test_json_get_array_index(self):
        """Test json_get with array index."""
        results = {"step1": self.create_results(response='{"items": ["a", "b", "c"]}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "items[0]") == "a"')
        assert result is True
        assert error is None

    def test_json_get_nested_array(self):
        """Test json_get with nested array access."""
        results = {
            "step1": self.create_results(response='{"data": {"items": [{"id": 1}, {"id": 2}]}}')
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "data.items[1].id") == 2')
        assert result is True
        assert error is None

    def test_json_get_default_missing_key(self):
        """Test json_get returns None for missing keys."""
        results = {"step1": self.create_results(response='{"status": "ok"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "missing") == None')
        assert result is True
        assert error is None

    def test_json_get_default_function(self):
        """Test json_get_default with custom default value."""
        results = {"step1": self.create_results(response='{"status": "ok"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get_default({{step1.response}}, "count", 0) == 0')
        assert result is True
        assert error is None

    def test_json_get_default_returns_value(self):
        """Test json_get_default returns actual value when present."""
        results = {"step1": self.create_results(response='{"count": 10}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get_default({{step1.response}}, "count", 0) == 10')
        assert result is True
        assert error is None

    def test_json_has_existing_key(self):
        """Test json_has returns True for existing key."""
        results = {"step1": self.create_results(response='{"error": "something failed"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_has({{step1.response}}, "error") == True')
        assert result is True
        assert error is None

    def test_json_has_missing_key(self):
        """Test json_has returns False for missing key."""
        results = {"step1": self.create_results(response='{"status": "ok"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_has({{step1.response}}, "error") == False')
        assert result is True
        assert error is None

    def test_json_keys_function(self):
        """Test json_keys returns list of keys."""
        results = {"step1": self.create_results(response='{"a": 1, "b": 2, "c": 3}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"a" in json_keys({{step1.response}})')
        assert result is True
        assert error is None

    def test_json_keys_count(self):
        """Test json_keys with len function."""
        results = {"step1": self.create_results(response='{"a": 1, "b": 2}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("len(json_keys({{step1.response}})) == 2")
        assert result is True
        assert error is None

    def test_json_parse_function(self):
        """Test json_parse returns parsed dict."""
        results = {"step1": self.create_results(response='{"name": "test"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_parse({{step1.response}}).get("name") == "test"')
        assert result is True
        assert error is None

    def test_json_type_string(self):
        """Test json_type returns correct type for string."""
        results = {"step1": self.create_results(response='{"value": "hello"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_type({{step1.response}}, "value") == "string"')
        assert result is True
        assert error is None

    def test_json_type_number(self):
        """Test json_type returns correct type for number."""
        results = {"step1": self.create_results(response='{"count": 42}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_type({{step1.response}}, "count") == "number"')
        assert result is True
        assert error is None

    def test_json_type_array(self):
        """Test json_type returns correct type for array."""
        results = {"step1": self.create_results(response='{"items": [1, 2, 3]}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_type({{step1.response}}, "items") == "array"')
        assert result is True
        assert error is None

    def test_json_type_boolean(self):
        """Test json_type returns correct type for boolean."""
        results = {"step1": self.create_results(response='{"active": true}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_type({{step1.response}}, "active") == "boolean"')
        assert result is True
        assert error is None

    def test_json_invalid_returns_none(self):
        """Test that invalid JSON returns None/default gracefully."""
        results = {"step1": self.create_results(response="not valid json")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "key") == None')
        assert result is True
        assert error is None

    # ========================================
    # New Function Tests
    # ========================================

    def test_split_function(self):
        """Test split() function."""
        results = {"step1": self.create_results(response="a,b,c")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('len(split({{step1.response}}, ",")) == 3')
        assert result is True
        assert error is None

    def test_replace_function(self):
        """Test replace() function."""
        results = {"step1": self.create_results(response="hello world")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            'replace({{step1.response}}, "world", "there") == "hello there"'
        )
        assert result is True
        assert error is None

    def test_count_function(self):
        """Test count() function."""
        results = {"step1": self.create_results(response="error error error")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('count({{step1.response}}, "error") == 3')
        assert result is True
        assert error is None

    def test_slice_function(self):
        """Test slice() function."""
        results = {"step1": self.create_results(response="hello world")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('slice({{step1.response}}, 0, 5) == "hello"')
        assert result is True
        assert error is None

    def test_abs_function(self):
        """Test abs() function."""
        results = {"step1": self.create_results(response="-42")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("abs(int({{step1.response}})) == 42")
        assert result is True
        assert error is None

    def test_min_function(self):
        """Test min() function."""
        results = {"step1": self.create_results(response="5")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("min(int({{step1.response}}), 10) == 5")
        assert result is True
        assert error is None

    def test_max_function(self):
        """Test max() function."""
        results = {"step1": self.create_results(response="15")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("max(int({{step1.response}}), 10) == 15")
        assert result is True
        assert error is None

    def test_round_function(self):
        """Test round() function."""
        results = {"step1": self.create_results(response="3.14159")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("round(float({{step1.response}}), 2) == 3.14")
        assert result is True
        assert error is None

    def test_is_null_function(self):
        """Test is_null() function with json_get returning None."""
        results = {"step1": self.create_results(response='{"key": "value"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            'is_null(json_get({{step1.response}}, "missing")) == True'
        )
        assert result is True
        assert error is None

    def test_is_null_function_false(self):
        """Test is_null() returns False for non-null values."""
        results = {"step1": self.create_results(response="content")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("is_null({{step1.response}}) == False")
        assert result is True
        assert error is None

    def test_is_empty_function_string(self):
        """Test is_empty() with empty string."""
        results = {"step1": self.create_results(response="")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("is_empty({{step1.response}}) == True")
        assert result is True
        assert error is None

    def test_is_empty_function_whitespace(self):
        """Test is_empty() with whitespace-only string."""
        results = {"step1": self.create_results(response="   ")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("is_empty({{step1.response}}) == True")
        assert result is True
        assert error is None

    def test_is_empty_function_with_content(self):
        """Test is_empty() returns False for string with content."""
        results = {"step1": self.create_results(response="content")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("is_empty({{step1.response}}) == False")
        assert result is True
        assert error is None

    def test_bool_function(self):
        """Test bool() function."""
        results = {"step1": self.create_results(response="yes")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate("bool({{step1.response}}) == True")
        assert result is True
        assert error is None

    # ========================================
    # List/Dict Membership Tests
    # ========================================

    def test_in_list_membership(self):
        """Test 'in' operator with list from json_keys."""
        results = {"step1": self.create_results(response='{"id": 1, "name": "test"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"id" in json_keys({{step1.response}})')
        assert result is True
        assert error is None

    def test_not_in_list_membership(self):
        """Test 'not in' operator with list from json_keys."""
        results = {"step1": self.create_results(response='{"id": 1, "name": "test"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"missing" not in json_keys({{step1.response}})')
        assert result is True
        assert error is None

    def test_dict_get_method(self):
        """Test dict.get() method via json_parse."""
        results = {"step1": self.create_results(response='{"count": 5}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_parse({{step1.response}}).get("count") == 5')
        assert result is True
        assert error is None

    def test_dict_get_method_default(self):
        """Test dict.get() method with default value."""
        results = {"step1": self.create_results(response='{"status": "ok"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_parse({{step1.response}}).get("missing", 0) == 0')
        assert result is True
        assert error is None

    def test_list_count_method(self):
        """Test list.count() method."""
        results = {"step1": self.create_results(response='{"items": ["a", "a", "b"]}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "items").count("a") == 2')
        assert result is True
        assert error is None

    # ========================================
    # Complex Integration Tests
    # ========================================

    def test_json_with_string_method_chain(self):
        """Test JSON extraction followed by string method."""
        results = {"step1": self.create_results(response='{"status": "SUCCESS_OK"}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            'json_get({{step1.response}}, "status").lower().startswith("success")'
        )
        assert result is True
        assert error is None

    def test_complex_condition_with_json(self):
        """Test complex condition combining JSON and boolean logic."""
        results = {
            "fetch": self.create_results(response='{"data": {"items": [1, 2, 3]}}'),
            "analyze": self.create_results(status="success"),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '{{analyze.status}} == "success" and json_has({{fetch.response}}, "data.items")'
        )
        assert result is True
        assert error is None

    def test_json_numeric_comparison(self):
        """Test JSON value extraction with numeric comparison."""
        results = {"step1": self.create_results(response='{"score": 0.85}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "score") > 0.8')
        assert result is True
        assert error is None

    def test_ternary_with_json(self):
        """Test ternary expression with JSON extraction."""
        results = {"step1": self.create_results(response='{"value": 10}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate(
            '"high" if json_get({{step1.response}}, "value") > 5 else "low" == "high"'
        )
        assert result is True
        assert error is None

    def test_error_recovery_with_json(self):
        """Test error recovery pattern with JSON response checking."""
        results = {
            "api_call": self.create_results(response='{"error": "rate limited"}'),
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_has({{api_call.response}}, "error")')
        assert result is True
        assert error is None

    def test_json_with_markdown_code_block(self):
        """Test JSON extraction from markdown code blocks."""
        results = {
            "step1": self.create_results(response='```json\n{"status": "ok", "count": 5}\n```')
        }
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "status") == "ok"')
        assert result is True
        assert error is None

    def test_json_keys_with_markdown(self):
        """Test json_keys with markdown-wrapped JSON."""
        results = {"step1": self.create_results(response='```json\n{"a": 1, "b": 2}\n```')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"a" in json_keys({{step1.response}})')
        assert result is True
        assert error is None

    def test_json_parse_with_markdown(self):
        """Test json_parse with markdown-wrapped JSON."""
        results = {"step1": self.create_results(response='```json\n{"value": 42}\n```')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_parse({{step1.response}}).get("value") == 42')
        assert result is True
        assert error is None

    # ========================================
    # json-repair Edge Case Tests
    # ========================================

    def test_json_with_trailing_comma(self):
        """Test JSON with trailing comma (common LLM output)."""
        results = {"step1": self.create_results(response='{"status": "ok", "count": 42,}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "count") == 42')
        assert result is True
        assert error is None

    def test_json_with_unquoted_keys(self):
        """Test JSON with unquoted keys (common LLM output)."""
        results = {"step1": self.create_results(response='{status: "ok", count: 42}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "status") == "ok"')
        assert result is True
        assert error is None

    def test_json_with_single_quotes(self):
        """Test JSON with single quotes (common LLM output)."""
        results = {"step1": self.create_results(response="{'status': 'ok', 'count': 42}")}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "count") == 42')
        assert result is True
        assert error is None

    def test_json_keys_with_trailing_comma(self):
        """Test json_keys with trailing comma."""
        results = {"step1": self.create_results(response='{"a": 1, "b": 2,}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('"a" in json_keys({{step1.response}})')
        assert result is True
        assert error is None

    def test_json_nested_with_trailing_comma(self):
        """Test nested JSON access with trailing comma."""
        results = {"step1": self.create_results(response='{"data": {"items": [1, 2, 3],}}')}
        evaluator = ConditionEvaluator(results)

        result, error = evaluator.evaluate('json_get({{step1.response}}, "data.items[0]") == 1')
        assert result is True
        assert error is None

    # ========================================
    # _parse_llm_json edge cases
    # ========================================

    def test_parse_llm_json_empty_string(self):
        """_parse_llm_json returns None for empty string."""
        result = _ce._parse_llm_json("")
        assert result is None

    def test_parse_llm_json_whitespace(self):
        """_parse_llm_json returns None for whitespace-only string."""
        result = _ce._parse_llm_json("   ")
        assert result is None

    def test_parse_llm_json_invalid_json(self):
        """_parse_llm_json returns None for unparseable JSON."""
        result = _ce._parse_llm_json("not json at all!!")
        assert result is None

    # ========================================
    # _safe_json_has edge cases
    # ========================================

    def test_safe_json_has_none_input(self):
        """_safe_json_has returns False for None."""
        result = _ce._safe_json_has(None, "key")
        assert result is False

    def test_safe_json_has_invalid_json(self):
        """_safe_json_has returns False for invalid JSON."""
        result = _ce._safe_json_has("not json", "key")
        assert result is False

    # ========================================
    # _safe_json_type edge cases
    # ========================================

    def test_safe_json_type_null_value(self):
        """_safe_json_type returns 'null' for null value."""
        result = _ce._safe_json_type('{"key": null}', "key")
        assert result == "null"

    def test_safe_json_type_none_input(self):
        """_safe_json_type returns 'null' for None input."""
        result = _ce._safe_json_type(None, "key")
        assert result == "null"

    def test_safe_json_type_invalid_json(self):
        """_safe_json_type returns 'null' for invalid JSON (parsed as None)."""
        result = _ce._safe_json_type("not json", "key")
        assert result == "null"

    def test_safe_json_type_missing_path(self):
        """_safe_json_type returns 'unknown' for missing path."""
        result = _ce._safe_json_type('{"a": 1}', "b")
        assert result == "unknown"

    def test_safe_json_type_number(self):
        """_safe_json_type returns 'number' for numeric value."""
        result = _ce._safe_json_type('{"val": 42}', "val")
        assert result == "number"

    def test_safe_json_type_array(self):
        """_safe_json_type returns 'array' for array value."""
        result = _ce._safe_json_type('{"val": [1, 2]}', "val")
        assert result == "array"

    def test_safe_json_type_object(self):
        """_safe_json_type returns 'object' for object value."""
        result = _ce._safe_json_type('{"val": {"nested": true}}', "val")
        assert result == "object"

    # ========================================
    # Computed properties
    # ========================================

    def test_has_response_computed_from_response(self):
        """has_response computed from response field."""
        results = {"step1": self.create_results(response="hello", has_response=None)}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.has_response}} == True")
        assert result is True

    def test_has_response_false_when_empty_response(self):
        """has_response is False when response is whitespace."""
        results = {"step1": self.create_results(response="  ", has_response=None)}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.has_response}} == False")
        assert result is True

    def test_agent_mode_none(self):
        """agent_mode defaults to False when None."""
        results = {"step1": self.create_results()}
        results["step1"]["agent_mode"] = None
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.agent_mode}} == False")
        assert result is True

    def test_tool_calls_count_from_list(self):
        """tool_calls_count computed from tool_calls list."""
        results = {"step1": self.create_results()}
        results["step1"]["tool_calls"] = [{"name": "a"}, {"name": "b"}]
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.tool_calls_count}} == 2")
        assert result is True

    def test_tool_calls_count_default_zero(self):
        """tool_calls_count defaults to 0."""
        results = {"step1": self.create_results()}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.tool_calls_count}} == 0")
        assert result is True

    def test_last_tool_name_from_list(self):
        """last_tool_name extracted from tool_calls."""
        results = {"step1": self.create_results()}
        results["step1"]["tool_calls"] = [{"tool_name": "calc"}, {"tool_name": "search"}]
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.last_tool_name}} == "search"')
        assert result is True

    def test_last_tool_name_empty_when_no_tool_calls(self):
        """last_tool_name is empty when no tool_calls."""
        results = {"step1": self.create_results()}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.last_tool_name}} == ""')
        assert result is True

    def test_total_rounds_none(self):
        """total_rounds defaults to 0 when None."""
        results = {"step1": self.create_results()}
        results["step1"]["total_rounds"] = None
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.total_rounds}} == 0")
        assert result is True

    def test_total_llm_calls_none(self):
        """total_llm_calls defaults to 0 when None."""
        results = {"step1": self.create_results()}
        results["step1"]["total_llm_calls"] = None
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.total_llm_calls}} == 0")
        assert result is True

    def test_response_none_becomes_empty_string(self):
        """response None is converted to empty string."""
        results = {"step1": self.create_results()}
        results["step1"]["response"] = None
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.response}} == ""')
        assert result is True

    def test_attempts_none_becomes_zero(self):
        """attempts None is converted to 0."""
        results = {"step1": self.create_results()}
        results["step1"]["attempts"] = None
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("{{step1.attempts}} == 0")
        assert result is True

    # ========================================
    # _value_to_literal edge cases
    # ========================================

    def test_value_to_literal_none(self):
        """None becomes empty string literal."""
        results = {"step1": self.create_results()}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.error}} == ""')

    def test_value_to_literal_nonstandard_type(self):
        """Non-standard type is converted to string."""
        results = {"step1": self.create_results()}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.status}} == "success"')
        assert result is True

    # ========================================
    # _eval_node edge cases
    # ========================================

    def test_eval_name_true_lowercase(self):
        """'true' identifier is recognized as True."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("true == True")
        assert result is True

    def test_eval_name_false_lowercase(self):
        """'false' identifier is recognized as False."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("false == False")
        assert result is True

    def test_eval_name_unknown_raises(self):
        """Unknown identifier raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("unknown_var == True")
        assert result is False
        assert "Unknown identifier" in (error or "")

    def test_eval_unsupported_expression(self):
        """Unsupported AST node type raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("[1, 2, 3] == [1, 2, 3]")
        assert result is False

    # ========================================
    # Comparison operator errors
    # ========================================

    def test_unsupported_comparison_operator(self):
        """Unsupported comparison operator raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("1 is 1")
        assert result is False

    # ========================================
    # 'in' operator edge cases
    # ========================================

    def test_in_operator_non_string_left(self):
        """'in' operator with string right requires string left."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("1 in {{step1.response}}")
        assert result is False

    def test_in_operator_unsupported_type(self):
        """'in' operator on unsupported type raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('"key" in 42')
        assert result is False

    # ========================================
    # Boolean operator errors
    # ========================================

    def test_unsupported_boolean_operator(self):
        """Unsupported boolean operator raises error (coverage)."""
        results = {}
        evaluator = ConditionEvaluator(results)
        evaluator._eval_boolop = lambda node: (_ for _ in ()).throw(
            _ce.ValueError("Unsupported boolean operator: Not")
        )
        result, error = evaluator.evaluate("not True")
        assert result is False

    # ========================================
    # Keyword arguments errors
    # ========================================

    def test_keyword_args_in_function_call(self):
        """Keyword arguments not supported in conditions."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('len(obj="test")')
        assert result is False
        assert "Keyword arguments" in (error or "")

    def test_keyword_args_in_method_call(self):
        """Keyword arguments not supported in method calls."""
        results = {"step1": self.create_results(response="hello world")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('{{step1.response}}.split(sep=" ")')
        assert result is False
        assert "Keyword arguments" in (error or "")

    # ========================================
    # Method call errors
    # ========================================

    def test_private_method_call_blocked(self):
        """Private method calls are blocked."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("{{step1.response}}._private()")
        assert result is False
        assert "private" in (error or "").lower()

    def test_unknown_string_method(self):
        """Unknown string method raises error."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("{{step1.response}}.nonexistent()")
        assert result is False

    def test_attribute_access_on_list(self):
        """Attribute access on list with unknown method raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('["a"].nonexistent()')
        assert result is False

    def test_attribute_access_on_dict(self):
        """Attribute access on dict with unknown method raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('{"a": 1}.nonexistent()')
        assert result is False

    def test_attribute_access_on_unknown_type(self):
        """Attribute access on unsupported type raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("42.lower()")
        assert result is False

    # ========================================
    # Subscript errors
    # ========================================

    def test_subscript_non_constant(self):
        """Non-constant subscript raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('["a"][1:2]')
        assert result is False

    def test_subscript_access_failure(self):
        """Failed subscript access raises error."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("{{step1.response}}[999]")
        assert result is False

    # ========================================
    # Binary operations
    # ========================================

    def test_binop_mod_matches(self):
        """Mod operator implements 'matches' regex."""
        results = {"step1": self.create_results(response="Hello World")}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.response}} % "Hello"')
        assert result is True

    def test_binop_mod_no_match(self):
        """Mod operator returns False when no match."""
        results = {"step1": self.create_results(response="Hello World")}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.response}} % "xyz"')
        assert result is False

    def test_binop_mod_invalid_regex(self):
        """Mod operator with invalid regex raises error."""
        results = {"step1": self.create_results(response="hello")}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate('{{step1.response}} % "[invalid"')
        assert result is False

    def test_binop_mod_non_string(self):
        """Mod operator with non-strings raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("42 % 'pattern'")
        assert result is False

    def test_binop_add(self):
        """Add binary operation."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("1 + 2 == 3")
        assert result is True

    def test_binop_sub(self):
        """Sub binary operation."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("5 - 3 == 2")
        assert result is True

    def test_binop_mult(self):
        """Multiply binary operation."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("3 * 4 == 12")
        assert result is True

    def test_binop_div(self):
        """Divide binary operation."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate("10 / 2 == 5")
        assert result is True

    def test_binop_unsupported(self):
        """Unsupported binary operator raises error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("2 // 1 == 2")
        assert result is False

    # ========================================
    # Ternary if-exp
    # ========================================

    def test_ifexp_else_branch(self):
        """Ternary expression else branch."""
        results = {"step1": self.create_results()}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('("yes" if True else "no") == "yes"')
        assert result is True

    # ========================================
    # resolve_variables empties result
    # ========================================

    def test_resolved_empty_returns_true(self):
        """Empty response resolves to empty string, which is falsy."""
        results = {"step1": self.create_results(response="")}
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.response}} == ""')
        assert result is True

    # ========================================
    # Syntax error in evaluate
    # ========================================

    def test_syntax_error_in_evaluate(self):
        """Unsupported operator in condition returns False with error."""
        results = {}
        evaluator = ConditionEvaluator(results)
        result, error = evaluator.evaluate("1 + + 2")
        assert result is False
        assert error is not None

    # ========================================
    # validate_syntax exception
    # ========================================

    def test_validate_syntax_syntax_error(self):
        """validate_syntax returns False for syntax errors after resolution."""
        result, error = ConditionEvaluator.validate_syntax("{{step1.status}} == 'ok' and")
        assert result is False
        assert error is not None
        assert "Syntax error" in error

    # ========================================
    # status default
    # ========================================

    def test_status_defaults_to_pending(self):
        """Status defaults to 'pending' when empty."""
        results = {"step1": self.create_results()}
        results["step1"]["status"] = ""
        evaluator = ConditionEvaluator(results)
        result, _ = evaluator.evaluate('{{step1.status}} == "pending"')
        assert result is True
