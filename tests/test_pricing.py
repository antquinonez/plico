# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

from src.core.pricing import estimate_cost


class TestEstimateCost:
    """Tests for model cost estimation."""

    def test_known_model(self):
        cost = estimate_cost("mistral-small-2503", 1000, 500)
        assert cost > 0
        expected = (1000 / 1000) * 0.0001 + (500 / 1000) * 0.0003
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_returns_zero(self):
        cost = estimate_cost("nonexistent-model", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens(self):
        cost = estimate_cost("sonar", 0, 0)
        assert cost == 0.0

    def test_case_insensitive(self):
        cost = estimate_cost("Mistral-Small-2503", 100, 50)
        assert cost > 0

    def test_partial_match(self):
        cost = estimate_cost("google/gemini-1.5-pro-002", 100, 50)
        assert cost > 0

    def test_perplexity_sonar(self):
        cost = estimate_cost("sonar", 1000, 1000)
        expected = (1000 / 1000) * 0.001 + (1000 / 1000) * 0.001
        assert abs(cost - expected) < 1e-10

    def test_gemini_flash(self):
        cost = estimate_cost("gemini-2.5-flash-lite", 1000, 500)
        assert cost > 0
