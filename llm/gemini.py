"""Google Gemini LLM provider."""
import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models import BaseChatModel
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini via langchain-google-genai."""

    def __init__(self, api_key_env: str = "GEMINI_API_KEY"):
        self._api_key_env = api_key_env
        self._api_key = os.environ.get(api_key_env)
        if not self._api_key:
            logger.warning(f"Gemini API key not found in env var '{api_key_env}'")

    def create_chat_model(
        self,
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        streaming: bool = True,
    ) -> BaseChatModel:
        if not self._api_key:
            raise ValueError(
                f"Gemini API key missing. Set {self._api_key_env} in .env"
            )
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=self._api_key,
            temperature=temperature,
            streaming=streaming,
        )

    def validate_config(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 0
