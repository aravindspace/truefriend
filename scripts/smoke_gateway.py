#!/usr/bin/env python3
"""P1.2 smoke test — dev tooling, outside the write boundary.

One tiny completion through each tier alias (voice, fast, judge) via the
LiteLLM Router built from config/litellm.yaml, plus one local embedding call.
Prints the model actually used per alias.

    python scripts/smoke_gateway.py                 # all tiers + embedding
    python scripts/smoke_gateway.py --test-fallback # bad primary key on fast tier
                                                    # must still answer via fallback
"""

import copy
import os
import sys

import yaml
from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
LITELLM_CONFIG = os.path.join(REPO_ROOT, "config", "litellm.yaml")

PROMPT = [{"role": "user", "content": "Reply with exactly one word: OM"}]


def load_config():
    with open(LITELLM_CONFIG) as f:
        return yaml.safe_load(f)


def resolve_env_refs(cfg):
    """Expand 'os.environ/NAME' values the way the litellm proxy does."""
    for entry in cfg["model_list"]:
        params = entry["litellm_params"]
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("os.environ/"):
                params[key] = os.environ.get(value.split("/", 1)[1], "")
    return cfg


def build_router(cfg):
    import litellm
    from litellm import Router

    litellm.drop_params = cfg.get("litellm_settings", {}).get("drop_params", False)
    rs = cfg["router_settings"]
    return Router(
        model_list=cfg["model_list"],
        num_retries=rs["num_retries"],
        timeout=rs["timeout"],
        fallbacks=rs["fallbacks"],
        content_policy_fallbacks=rs.get("content_policy_fallbacks", []),
    )


def smoke_completions(router, aliases=("voice", "fast", "judge")):
    ok = True
    for alias in aliases:
        try:
            resp = router.completion(model=alias, messages=PROMPT, max_tokens=1000)
            used = resp.model
            text = (resp.choices[0].message.content or "").strip()
            print(f"  {alias:<8} PASS  model={used!r}  reply={text[:40]!r}")
        except Exception as exc:
            ok = False
            print(f"  {alias:<8} FAIL  {type(exc).__name__}: {str(exc)[:120]}")
    return ok


def smoke_embedding():
    from preprocessing.config import LlamaCppEmbeddings, NOMIC_EMBEDDING_DIMS

    vec = LlamaCppEmbeddings().embed_query("search_document: smoke test")
    assert len(vec) == NOMIC_EMBEDDING_DIMS, f"got {len(vec)} dims"
    print(f"  embed    PASS  local nomic-embed, {len(vec)} dims")
    return True


def test_fallback(cfg):
    """Corrupt the primary fast deployment's key; fallback must still answer."""
    broken = copy.deepcopy(cfg)
    for entry in broken["model_list"]:
        if entry["model_name"] == "fast":
            entry["litellm_params"]["api_key"] = "sk-deliberately-broken"
    router = build_router(broken)
    resp = router.completion(model="fast", messages=PROMPT, max_tokens=1000)
    print(f"  fallback PASS  primary key broken, answered by model={resp.model!r}")
    return True


def main():
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
    cfg = resolve_env_refs(load_config())

    if "--test-fallback" in sys.argv:
        print("Fallback test (fast tier, primary key deliberately broken):")
        sys.exit(0 if test_fallback(cfg) else 1)

    print("Tier completions:")
    ok = smoke_completions(build_router(cfg))
    print("Embedding:")
    ok = smoke_embedding() and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
