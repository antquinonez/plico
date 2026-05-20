import json

from src.core.prompt_utils import extract_json_field, interpolate_prompt


class TestExtractJsonField:
    def test_simple_field(self):
        assert extract_json_field({"name": "alice"}, "name") == "alice"

    def test_nested_field(self):
        assert extract_json_field({"a": {"b": 5}}, "a.b") == "5"

    def test_array_index(self):
        assert extract_json_field({"items": [10, 20, 30]}, "items.0") == "10"
        assert extract_json_field({"items": [10, 20, 30]}, "items.2") == "30"

    def test_combined_path(self):
        data = {"users": [{"name": "alice"}, {"name": "bob"}]}
        assert extract_json_field(data, "users.1.name") == "bob"

    def test_missing_field_returns_empty(self):
        assert extract_json_field({"a": 1}, "b") == ""

    def test_missing_nested_returns_empty(self):
        assert extract_json_field({"a": {"b": 1}}, "a.c") == ""

    def test_index_out_of_range_returns_empty(self):
        assert extract_json_field({"items": [1]}, "items.5") == ""

    def test_non_dict_non_list_returns_empty(self):
        assert extract_json_field("string", "field") == ""

    def test_none_value_returns_empty(self):
        assert extract_json_field({"a": None}, "a.b") == ""

    def test_dict_value_serialized(self):
        result = extract_json_field({"a": {"nested": True}}, "a")
        assert json.loads(result) == {"nested": True}

    def test_list_value_serialized(self):
        result = extract_json_field({"a": [1, 2]}, "a")
        assert json.loads(result) == [1, 2]

    def test_integer_value(self):
        assert extract_json_field({"count": 42}, "count") == "42"

    def test_boolean_value(self):
        assert extract_json_field({"active": True}, "active") == "True"


class TestInterpolatePrompt:
    def test_single_replacement(self):
        result, names = interpolate_prompt(
            "The answer is {{math.response}}",
            {"math": "42"},
        )
        assert result == "The answer is 42"
        assert names == {"math"}

    def test_multiple_replacements(self):
        result, names = interpolate_prompt(
            "{{a.response}} and {{b.response}}",
            {"a": "alpha", "b": "beta"},
        )
        assert result == "alpha and beta"
        assert names == {"a", "b"}

    def test_unknown_name_replaced_with_empty(self):
        result, names = interpolate_prompt(
            "Result: {{missing.response}}",
            {"other": "value"},
        )
        assert result == "Result: "
        assert names == set()

    def test_field_path_extraction(self):
        result, names = interpolate_prompt(
            "Score: {{analysis.response.score}}",
            {"analysis": '{"score": 8, "reason": "good"}'},
        )
        assert result == "Score: 8"
        assert names == {"analysis"}

    def test_field_path_with_invalid_json_falls_back(self):
        result, names = interpolate_prompt(
            "Result: {{x.response.field}}",
            {"x": "not json"},
        )
        assert result == "Result: not json"
        assert names == {"x"}

    def test_no_patterns_returns_unchanged(self):
        result, names = interpolate_prompt("No patterns here", {"a": "b"})
        assert result == "No patterns here"
        assert names == set()

    def test_same_name_twice(self):
        result, names = interpolate_prompt(
            "{{x.response}} and {{x.response}}",
            {"x": "val"},
        )
        assert result == "val and val"
        assert names == {"x"}
