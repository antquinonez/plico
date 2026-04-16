"""Tests for retry utilities."""

from __future__ import annotations

import pytest

from src.retry_utils import (
    RETRYABLE_EXCEPTIONS,
    RateLimitError,
    ServiceUnavailableError,
    create_rate_limit_error,
    extract_retry_after,
    get_configured_retry_decorator,
    get_retry_decorator,
    retry_with_backoff,
    should_retry_exception,
)


class TestRateLimitError:
    def test_is_exception(self):
        assert issubclass(RateLimitError, Exception)

    def test_message(self):
        err = RateLimitError("rate limited")
        assert str(err) == "rate limited"


class TestServiceUnavailableError:
    def test_is_exception(self):
        assert issubclass(ServiceUnavailableError, Exception)

    def test_message(self):
        err = ServiceUnavailableError("503")
        assert str(err) == "503"


class TestShouldRetryException:
    def test_rate_limit_error(self):
        assert should_retry_exception(RateLimitError("test")) is True

    def test_service_unavailable_error(self):
        assert should_retry_exception(ServiceUnavailableError("test")) is True

    def test_connection_error(self):
        assert should_retry_exception(ConnectionError("test")) is True

    def test_timeout_error(self):
        assert should_retry_exception(TimeoutError("test")) is True

    def test_generic_exception_not_retryable(self):
        assert should_retry_exception(ValueError("oops")) is False

    def test_runtime_error_not_retryable(self):
        assert should_retry_exception(RuntimeError("oops")) is False

    def test_key_error_not_retryable(self):
        assert should_retry_exception(KeyError("oops")) is False

    def test_exception_with_429_message(self):
        assert should_retry_exception(Exception("Error 429 Too Many")) is True

    def test_exception_with_rate_limit_message(self):
        assert should_retry_exception(Exception("rate limit exceeded")) is True

    def test_exception_with_too_many_requests(self):
        assert should_retry_exception(Exception("too many requests")) is True

    def test_exception_with_quota_exceeded(self):
        assert should_retry_exception(Exception("quota exceeded")) is True

    def test_exception_with_resource_exhausted(self):
        assert should_retry_exception(Exception("resource_exhausted")) is True

    def test_exception_with_503_message(self):
        assert should_retry_exception(Exception("503 service unavailable")) is True

    def test_exception_with_service_unavailable_message(self):
        assert should_retry_exception(Exception("service unavailable")) is True

    def test_exception_with_502_message(self):
        assert should_retry_exception(Exception("502 bad gateway")) is True

    def test_exception_with_bad_gateway_message(self):
        assert should_retry_exception(Exception("bad gateway")) is True

    def test_exception_with_504_message(self):
        assert should_retry_exception(Exception("504 gateway timeout")) is True

    def test_exception_with_gateway_timeout_message(self):
        assert should_retry_exception(Exception("gateway timeout")) is True

    def test_exception_with_timeout_message(self):
        assert should_retry_exception(Exception("request timeout")) is True

    def test_exception_with_connection_message(self):
        assert should_retry_exception(Exception("connection refused")) is True

    def test_exception_with_unrelated_message(self):
        assert should_retry_exception(Exception("something else happened")) is False


class TestExtractRetryAfter:
    def test_retry_in_pattern(self):
        result = extract_retry_after(Exception("retry in 5.5 s"))
        assert result == 5.5

    def test_retry_after_pattern(self):
        result = extract_retry_after(Exception("retry after 3s"))
        assert result == 3.0

    def test_retrydelay_pattern(self):
        result = extract_retry_after(Exception('retrydelay: "10"'))
        assert result == 10.0

    def test_wait_seconds_pattern(self):
        result = extract_retry_after(Exception("wait 2.5 seconds"))
        assert result == 2.5

    def test_no_match_returns_none(self):
        result = extract_retry_after(Exception("no delay info here"))
        assert result is None

    def test_integer_value(self):
        result = extract_retry_after(Exception("retry after 10 s"))
        assert result == 10.0

    def test_case_insensitive(self):
        result = extract_retry_after(Exception("RETRY IN 3S"))
        assert result == 3.0


class TestGetRetryDecorator:
    def test_returns_callable(self):
        decorator = get_retry_decorator()
        assert callable(decorator)

    def test_decorator_wraps_function(self):
        decorator = get_retry_decorator(max_attempts=2)
        func = decorator(lambda: "ok")
        assert func() == "ok"

    def test_decorator_retries_on_failure(self):
        call_count = 0

        @get_retry_decorator(max_attempts=3, min_wait=0.01, max_wait=0.01)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("try again")
            return "success"

        result = flaky()
        assert result == "success"
        assert call_count == 3

    def test_decorator_reraises_on_non_retryable(self):
        @get_retry_decorator(max_attempts=3)
        def fail():
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            fail()

    def test_decorator_exhausts_attempts(self):
        @get_retry_decorator(max_attempts=2, min_wait=0.01, max_wait=0.01)
        def always_fail():
            raise RateLimitError("always")

        with pytest.raises(RateLimitError):
            always_fail()

    def test_custom_retry_exceptions(self):
        custom = (ValueError,)

        @get_retry_decorator(max_attempts=2, min_wait=0.01, max_wait=0.01, retry_exceptions=custom)
        def fail_value():
            raise ValueError("retry me")

        with pytest.raises(ValueError):
            fail_value()


class TestRetryWithBackoff:
    def test_success_on_first_try(self):
        result = retry_with_backoff(lambda: 42, max_attempts=3)
        assert result == 42

    def test_retries_then_succeeds(self):
        call_count = 0

        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("try again")
            return "ok"

        result = retry_with_backoff(flaky, max_attempts=3, min_wait=0.01, max_wait=0.01)
        assert result == "ok"
        assert call_count == 2

    def test_raises_on_non_retryable(self):
        with pytest.raises(ValueError):
            retry_with_backoff(lambda: (_ for _ in ()).throw(ValueError("nope")), max_attempts=3)

    def test_exhausts_retries(self):
        with pytest.raises(RateLimitError):
            retry_with_backoff(
                lambda: (_ for _ in ()).throw(RateLimitError("always")),
                max_attempts=2,
                min_wait=0.01,
                max_wait=0.01,
            )

    def test_passes_kwargs_to_function(self):
        def greet(name, greeting="hello"):
            return f"{greeting} {name}"

        result = retry_with_backoff(greet, max_attempts=1, name="world", greeting="hi")
        assert result == "hi world"


class TestCreateRateLimitError:
    def test_with_retry_after(self):
        exc = Exception("retry after 5s")
        err = create_rate_limit_error(exc)
        assert isinstance(err, RateLimitError)
        assert "5s" in str(err)
        assert "Rate limit exceeded" in str(err)

    def test_without_retry_after(self):
        exc = Exception("something went wrong")
        err = create_rate_limit_error(exc)
        assert isinstance(err, RateLimitError)
        assert "Rate limit exceeded" in str(err)
        assert "something went wrong" in str(err)


class TestRetryableExceptions:
    def test_includes_expected_types(self):
        assert RateLimitError in RETRYABLE_EXCEPTIONS
        assert ServiceUnavailableError in RETRYABLE_EXCEPTIONS
        assert ConnectionError in RETRYABLE_EXCEPTIONS
        assert TimeoutError in RETRYABLE_EXCEPTIONS

    def test_is_tuple(self):
        assert isinstance(RETRYABLE_EXCEPTIONS, tuple)


class TestGetConfiguredRetryDecorator:
    def test_returns_callable(self):
        decorator = get_configured_retry_decorator()
        assert callable(decorator)

    def test_falls_back_to_defaults_without_config(self):
        call_count = 0

        @get_configured_retry_decorator()
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("try again")
            return "success"

        result = flaky()
        assert result == "success"
        assert call_count == 3

    def test_uses_config_values(self):
        from unittest.mock import MagicMock, patch

        mock_retry = MagicMock()
        mock_retry.max_attempts = 2
        mock_retry.min_wait_seconds = 0.01
        mock_retry.max_wait_seconds = 0.01
        mock_retry.exponential_base = 2
        mock_retry.exponential_jitter = True

        mock_config = MagicMock()
        mock_config.retry = mock_retry

        with patch("src.config.get_config", return_value=mock_config):
            call_count = 0

            @get_configured_retry_decorator()
            def flaky():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RateLimitError("try again")
                return "success"

            result = flaky()
            assert result == "success"
            assert call_count == 2

    def test_reraises_non_retryable(self):
        @get_configured_retry_decorator()
        def fail():
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            fail()

    def test_handles_config_import_error(self):
        from unittest.mock import patch

        with patch("src.config.get_config", side_effect=Exception("no config")):
            call_count = 0

            @get_configured_retry_decorator()
            def flaky():
                nonlocal call_count
                call_count += 1
                if call_count < 2:
                    raise RateLimitError("try again")
                return "ok"

            result = flaky()
            assert result == "ok"
            assert call_count == 2
