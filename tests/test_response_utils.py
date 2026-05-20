from src.core.response_utils import _extract_from_markdown, clean_response, extract_json


class TestExtractFromMarkdown:
    def test_extracts_json_from_markdown(self):
        result = _extract_from_markdown('```json\n{"x": 1}\n```')
        assert result == '{"x": 1}'

    def test_extracts_without_language_tag(self):
        result = _extract_from_markdown('```\n{"x": 1}\n```')
        assert result == '{"x": 1}'

    def test_returns_none_when_no_markdown(self):
        result = _extract_from_markdown("plain text")
        assert result is None

    def test_strips_bom_and_whitespace(self):
        result = _extract_from_markdown('```json\n  {"x": 1}\n```')
        assert result == '{"x": 1}'


class TestExtractJson:
    def test_valid_json_at_start(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_in_markdown_code_block(self):
        result = extract_json('```json\n{"score": 5}\n```')
        assert result is None

    def test_plain_text_returns_none(self):
        assert extract_json("plain text") is None

    def test_json_with_whitespace_prefix(self):
        result = extract_json('  {"key": "val"}')
        assert result == {"key": "val"}

    def test_nested_json(self):
        result = extract_json('{"a": {"b": 1}}')
        assert result == {"a": {"b": 1}}

    def test_json_array(self):
        result = extract_json("[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_empty_string_returns_none(self):
        assert extract_json("") is None

    def test_json_after_20_chars_not_detected(self):
        result = extract_json("a" * 21 + '{"key": 1}')
        assert result is None

    def test_json_in_markdown_no_language(self):
        result = extract_json('```\n{"x": 1}\n```')
        assert result is None

    def test_json_first_20_with_invalid_markdown_falls_through(self):
        text = '{"a":1}             ```json\n{invalid}\n```'
        result = extract_json(text)
        assert result is None

    def test_json_first_20_with_invalid_markdown_and_clean_full_text(self):
        text = '{"a":1}             '
        result = extract_json(text)
        assert result == {"a": 1}


class TestCleanResponse:
    def test_non_string_passthrough_int(self):
        assert clean_response(42) == 42

    def test_non_string_passthrough_dict(self):
        assert clean_response({"a": 1}) == {"a": 1}

    def test_non_string_passthrough_none(self):
        assert clean_response(None) is None

    def test_non_string_passthrough_list(self):
        assert clean_response([1, 2]) == [1, 2]

    def test_removes_think_tags(self):
        result = clean_response("<think step 1</think >Hello world")
        assert result == "Hello world"

    def test_removes_think_tags_multiline(self):
        result = clean_response("<think\nstep 1\nstep 2\n</think >Actual response")
        assert result == "Actual response"

    def test_extracts_json_at_start(self):
        result = clean_response('{"score": 5}')
        assert result == {"score": 5}

    def test_long_json_returns_cleaned_string(self):
        result = clean_response('{"score": 5, "reason": "good"}')
        assert isinstance(result, str)
        assert '"score": 5' in result
        assert '"reason": "good"' in result

    def test_think_tags_in_json_values_stripped(self):
        result = clean_response('{"analysis": "<think hmm</think >actual"}')
        assert isinstance(result, str)
        assert "<think" not in result
        assert "actual" in result

    def test_plain_text_without_json(self):
        result = clean_response("Just a plain text response")
        assert result == "Just a plain text response"

    def test_empty_string(self):
        assert clean_response("") == ""

    def test_think_tags_without_closing_not_removed(self):
        result = clean_response("<think reasoning")
        assert "<think" in result
