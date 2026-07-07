"""Ollama local LLM provider."""
import os
import logging
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Local Ollama inference via langchain-ollama."""

    def __init__(
        self,
        base_url_env: str = "OLLAMA_BASE_URL",
        base_url_default: str = "http://localhost:11434",
    ):
        self._base_url = os.environ.get(base_url_env, base_url_default)

    def create_chat_model(
        self,
        model: str = "llama3",
        temperature: float = 0.7,
        streaming: bool = True,
    ) -> BaseChatModel:
        return ChatOllama(
            model=model,
            base_url=self._base_url,
            temperature=temperature,
        )

    def validate_config(self) -> bool:
        # Ollama = local, no API key needed. Just check if URL is set.
        return self._base_url is not None
