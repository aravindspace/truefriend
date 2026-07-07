"""Base LLM provider interface."""
from abc import ABC, abstractmethod
from typing import AsyncIterator
from langchain_core.language_models import BaseChatModel


class LLMProvider(ABC):
    """Abstract LLM provider — swap implementations without changing agent code."""

    @abstractmethod
    def create_chat_model(
        self,
        model: str,
        temperature: float = 0.7,
        streaming: bool = True,
    ) -> BaseChatModel:
        """Return a LangChain-compatible chat model."""
        ...

    @abstractmethod
    def validate_config(self) -> bool:
        """Check if provider is properly configured (API key exists, etc)."""
        ...
