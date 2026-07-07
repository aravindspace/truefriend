"""Azure OpenAI LLM provider."""
import os
import logging
from langchain_openai import AzureChatOpenAI
from langchain_core.language_models import BaseChatModel
from llm.provider import LLMProvider

logger = logging.getLogger(__name__)


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI via langchain-openai."""

    def __init__(
        self,
        api_key_env: str = "AZURE_OPENAI_API_KEY",
        endpoint_env: str = "AZURE_OPENAI_ENDPOINT",
        api_version_env: str = "AZURE_OPENAI_API_VERSION",
    ):
        self._api_key_env = api_key_env
        self._endpoint_env = endpoint_env
        self._api_version_env = api_version_env

        self._api_key = os.environ.get(api_key_env)
        self._endpoint = os.environ.get(endpoint_env)
        self._api_version = os.environ.get(api_version_env, "2024-12-01-preview")

        if not self._api_key:
            logger.warning(f"Azure OpenAI API key not found in env var '{api_key_env}'")
        if not self._endpoint:
            logger.warning(f"Azure OpenAI endpoint not found in env var '{endpoint_env}'")

    def create_chat_model(
        self,
        model: str = "o4-mini",
        streaming: bool = True,
    ) -> BaseChatModel:
        if not self._api_key:
            raise ValueError(
                f"Azure OpenAI API key missing. Set {self._api_key_env} in .env"
            )
        if not self._endpoint:
            raise ValueError(
                f"Azure OpenAI endpoint missing. Set {self._endpoint_env} in .env"
            )
        return AzureChatOpenAI(
            azure_deployment=model,
            azure_endpoint=self._endpoint,
            api_key=self._api_key,
            api_version=self._api_version,
            streaming=streaming,
        )

    def validate_config(self) -> bool:
        return (
            self._api_key is not None
            and len(self._api_key) > 0
            and self._endpoint is not None
            and len(self._endpoint) > 0
        )
