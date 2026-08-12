"""LiteLLM Router accessor — §14: every model call goes through tier aliases.

The single runtime home for the router (scripts/smoke_gateway.py carries a
dev-time copy). Aliases, fallback chains, content_policy_fallbacks, retries,
and timeouts all come from config/litellm.yaml — code never hardcodes a
deployment.
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
LITELLM_CONFIG = REPO_ROOT / "config" / "litellm.yaml"


def _resolve_env_refs(cfg: dict) -> dict:
    """Expand 'os.environ/NAME' values the way the litellm proxy does."""
    for entry in cfg["model_list"]:
        params = entry["litellm_params"]
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("os.environ/"):
                params[key] = os.environ.get(value.split("/", 1)[1], "")
    return cfg


@lru_cache(maxsize=1)
def get_router():
    import litellm
    from litellm import Router

    load_dotenv(REPO_ROOT / ".env")
    with open(LITELLM_CONFIG) as f:
        cfg = _resolve_env_refs(yaml.safe_load(f))

    litellm.drop_params = cfg.get("litellm_settings", {}).get("drop_params", False)
    rs = cfg["router_settings"]
    return Router(
        model_list=cfg["model_list"],
        num_retries=rs["num_retries"],
        timeout=rs["timeout"],
        fallbacks=rs["fallbacks"],
        content_policy_fallbacks=rs.get("content_policy_fallbacks", []),
    )


#: Structured-output escape hatch: Groq gpt-oss intermittently rejects strict
#: json_schema ("json_validate_failed"). When a structured call on these tiers
#: fails, retry once on a JSON-reliable model (Gemini) — independent of the
#: router's own fallback chain, which dead-ends on the intermediate group.
_STRUCTURED_FALLBACK = {"fast": "fast-gemini", "voice": "voice-gemini", "judge": "judge-gemini"}


def _one_call(tier: str, messages: list[dict], response_format, max_tokens: int) -> str:
    """A single router completion. An OUTPUT content filter (Azure returns 200
    with finish_reason=content_filter and empty text — not an exception) is
    surfaced as ContentFilterBlocked so the same ladder handles it (§5)."""
    from arjun.harness.content_filter import ContentFilterBlocked

    kwargs = {"model": tier, "messages": messages, "max_tokens": max_tokens}
    if response_format is not None:
        kwargs["response_format"] = response_format
    resp = get_router().completion(**kwargs)
    choice = resp.choices[0]
    content = choice.message.content or ""
    if getattr(choice, "finish_reason", None) == "content_filter" and not content.strip():
        raise ContentFilterBlocked({"output"}, stage="output")
    return content


def complete(
    tier: str,
    messages: list[dict],
    *,
    response_format=None,
    max_tokens: int = 2000,
    raise_on_filter: bool = False,
) -> str:
    """One completion through a tier alias; returns the reply text.

    Two resiliencies (§5):
    - **Content filter (deterministic ladder, content_filter.py):** a provider
      safety rejection → retry (Azure's filter is intermittent) → sanitize+retry
      (soften violence words) → give up. On give-up: ``raise_on_filter`` callers
      (gut, compose) get ``ContentFilterBlocked`` to voice a tailored safe reply;
      everyone else gets "" and degrades to their safe default.
    - **Structured schema fallback:** a non-content-policy failure on a structured
      call retries once on a reliable-JSON fallback deployment."""
    from arjun.harness.content_filter import (
        ContentFilterBlocked,
        VIOLENCE_CATS,
        filtered_categories,
        sanitize_messages,
    )
    from litellm.exceptions import ContentPolicyViolationError

    import logging

    logger = logging.getLogger("arjun.harness")

    try:
        return _one_call(tier, messages, response_format, max_tokens)
    except ContentFilterBlocked as exc:  # OUTPUT filtered (from _one_call)
        if raise_on_filter:
            raise
        logger.warning("output content-filtered on %s — degrading", tier)
        return ""
    except ContentPolicyViolationError as exc:  # INPUT/prompt filtered (400)
        cats = filtered_categories(exc)
        logger.warning("content filter on %s (cats=%s) — mitigating", tier, sorted(cats))
        # Step 1: plain retry (the filter is intermittent at the boundary).
        try:
            return _one_call(tier, messages, response_format, max_tokens)
        except (ContentPolicyViolationError, ContentFilterBlocked):
            pass
        # Step 2: sanitize the heaviest violence words, then retry. Skip when
        # only self_harm fired — that is the person's own words, not to be reworded.
        if cats and not cats.issubset({"self_harm"}):
            try:
                return _one_call(tier, sanitize_messages(messages), response_format, max_tokens)
            except (ContentPolicyViolationError, ContentFilterBlocked):
                pass
        # Step 3: give up gracefully.
        if raise_on_filter:
            raise ContentFilterBlocked(cats, stage="input")
        return ""
    except Exception as exc:  # non-content-policy failure → structured fallback
        fallback = _STRUCTURED_FALLBACK.get(tier)
        if response_format is None or fallback is None:
            raise
        logger.warning("structured call on %s failed (%s) — retrying on %s", tier, exc, fallback)
        return _one_call(fallback, messages, response_format, max_tokens)


def fast_chat_model():
    """The default chat model for ``create_agent`` subagents — Azure o4-mini
    (owner decision 2026-07-18: quota headroom). Built from env exactly like
    ``preprocessing/config.py::get_azure_llm``; o4-mini is a reasoning model, so
    no ``temperature`` is sent. Pair with ``agent_fallback_models`` via
    ModelFallbackMiddleware to keep Groq/Gemini fallbacks."""
    import os

    from langchain_openai import AzureChatOpenAI

    load_dotenv(REPO_ROOT / ".env")
    return AzureChatOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
    )


def agent_fallback_models() -> list:
    """Fallback chat models for subagents (ModelFallbackMiddleware) when the
    Azure primary errors: Groq gpt-oss-120b → Gemini flash."""
    import os

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_groq import ChatGroq

    load_dotenv(REPO_ROOT / ".env")
    return [
        ChatGroq(model="openai/gpt-oss-120b", api_key=os.getenv("GROQ_API_KEY")),
        ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=os.getenv("GEMINI_API_KEY")),
    ]
