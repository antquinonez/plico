# PROPRIETARY AND CONTROLLED CODE
# Copyright (C) 2025 Antonio Quinonez / Far Finer LLC. All Rights Reserved.
#
# WARNING: This code contains sensitive technology requiring explicit authorization
# for possession or use. Unauthorized possession is strictly prohibited and will
# result in legal action. Licensed use requires signed agreement and compliance
# with all security requirements.
#
# Contact: antquinonez@farfiner.com
# filename: src/lib/AI/FFAIClientBase.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class FFAIClientBase(ABC):
    """Abstract base class for AI clients"""

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
        """Generate a response from the AI model"""
        pass

    @abstractmethod
    def clear_conversation(self):
        """Clear the conversation history"""
        pass

    @abstractmethod
    def get_conversation_history(self):
        """Get the conversation history"""
        pass

    @abstractmethod
    def set_conversation_history(self, history):
        """Set the conversation history"""
        pass

    @abstractmethod
    def clone(self) -> "FFAIClientBase":
        """Create a fresh clone of this client with empty history"""
        pass
