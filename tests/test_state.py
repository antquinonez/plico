# Copyright (c) 2025 Antonio Quinonez / Far Finer LLC
# SPDX-License-Identifier: MIT
# Contact: antquinonez@farfiner.com

"""Tests for state management."""

from src.orchestrator.state import PromptNode


class TestPromptNode:
    """Tests for PromptNode."""

    def test_init_basic(self):
        """Test basic initialization."""
        node = PromptNode(sequence=1, prompt={"prompt": "Hello"})
        assert node.sequence == 1
        assert node.prompt == {"prompt": "Hello"}
        assert node.dependencies == set()
        assert node.level == 0

    def test_init_with_dependencies(self):
        """Test initialization with dependencies."""
        node = PromptNode(
            sequence=3,
            prompt={"prompt": "Test"},
            dependencies={1, 2},
            level=1,
        )
        assert node.sequence == 3
        assert node.dependencies == {1, 2}
        assert node.level == 1

    def test_hash(self):
        """Test hashing by sequence."""
        node1 = PromptNode(sequence=1, prompt={"a": "b"})
        node2 = PromptNode(sequence=1, prompt={"c": "d"})

        assert hash(node1) == hash(node2)
        assert node1 == node2

    def test_not_equal(self):
        """Test inequality."""
        node1 = PromptNode(sequence=1, prompt={})
        node2 = PromptNode(sequence=2, prompt={})

        assert node1 != node2

    def test_is_ready_no_dependencies(self):
        """Test is_ready with no dependencies."""
        node = PromptNode(sequence=1, prompt={})
        assert node.is_ready(set()) is True
        assert node.is_ready({2, 3}) is True

    def test_is_ready_with_dependencies(self):
        """Test is_ready with dependencies."""
        node = PromptNode(sequence=3, prompt={}, dependencies={1, 2})

        assert node.is_ready(set()) is False
        assert node.is_ready({1}) is False
        assert node.is_ready({1, 2}) is True
        assert node.is_ready({1, 2, 4}) is True

    def test_add_dependency(self):
        """Test adding a dependency."""
        node = PromptNode(sequence=2, prompt={})
        node.add_dependency(1)

        assert 1 in node.dependencies

    def test_get_prompt_name(self):
        """Test getting prompt name."""
        node = PromptNode(sequence=1, prompt={"prompt_name": "test"})
        assert node.get_prompt_name() == "test"

        node2 = PromptNode(sequence=2, prompt={})
        assert node2.get_prompt_name() is None
