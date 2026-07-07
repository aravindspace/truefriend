"""LLM factory — reads config.yaml, returns configured chat models per agent."""
import os
import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from langchain_core.language_models import BaseChatModel

from llm.provider import LLMProvider
from llm.gemini import GeminiProvider
from llm.groq import GroqProvider
from llm.ollama import OllamaProvider
from llm.azure_openai import AzureOpenAIProvider

logger = logging.getLogger(__name__)

# Load .env on import
load_dotenv()

# Provider registry
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "google": GeminiProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
    "azure_openai": AzureOpenAIProvider,
}

_config_cache: dict[str, Any] | None = None
_provider_cache: dict[str, LLMProvider] = {}


def _load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load and cache config.yaml."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r") as f:
        _config_cache = yaml.safe_load(f)

    return _config_cache


def _get_provider(provider_name: str, provider_config: dict) -> LLMProvider:
    """Get or create cached provider instance."""
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    if provider_name not in _PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider_name}'. "
            f"Available: {list(_PROVIDERS.keys())}"
        )

    provider_cls = _PROVIDERS[provider_name]

    # Build kwargs from provider config
    kwargs = {}
    if "api_key_env" in provider_config:
        kwargs["api_key_env"] = provider_config["api_key_env"]
    if "base_url_env" in provider_config:
        kwargs["base_url_env"] = provider_config["base_url_env"]
    if "base_url_default" in provider_config:
        kwargs["base_url_default"] = provider_config["base_url_default"]
    if "endpoint_env" in provider_config:
        kwargs["endpoint_env"] = provider_config["endpoint_env"]
    if "api_version_env" in provider_config:
        kwargs["api_version_env"] = provider_config["api_version_env"]

    provider = provider_cls(**kwargs)
    _provider_cache[provider_name] = provider
    return provider


def create_llm(
    agent_name: str,
    config_path: str | Path | None = None,
) -> BaseChatModel:
    """Create LLM for a specific agent based on config.yaml.

    Usage:
        llm = create_llm("supervisor_classify")
        llm = create_llm("scholar")
    """
    config = _load_config(config_path)

    # Get agent config
    agents_config = config.get("agents", {})
    if agent_name not in agents_config:
        raise ValueError(
            f"Agent '{agent_name}' not found in config.yaml. "
            f"Available: {list(agents_config.keys())}"
        )

    agent_cfg = agents_config[agent_name]
    provider_name = agent_cfg["provider"]
    model = agent_cfg.get("model")
    temperature = agent_cfg.get("temperature", 0.7)

    # Get provider config
    providers_config = config.get("llm", {}).get("providers", {})
    if provider_name not in providers_config:
        raise ValueError(
            f"Provider '{provider_name}' not found in config.yaml"
        )

    provider = _get_provider(provider_name, providers_config[provider_name])

    # Use model from agent config, fall back to provider default
    if model is None:
        model = providers_config[provider_name].get("default_model")

    logger.info(f"Creating LLM for '{agent_name}': {provider_name}/{model}")

    # Build kwargs — some providers (Azure o4-mini) don't support temperature
    kwargs = {"model": model, "streaming": True}
    import inspect
    sig = inspect.signature(provider.create_chat_model)
    if "temperature" in sig.parameters:
        kwargs["temperature"] = temperature

    return provider.create_chat_model(**kwargs)
