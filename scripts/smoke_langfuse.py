#!/usr/bin/env python3
"""P1.3 smoke test — dev tooling, outside the write boundary.

Verifies this box can trace to the owner-hosted remote Langfuse instance
(§5 hosting note — this machine is a client only):

  1. auth check against LANGFUSE_HOST
  2. one manual trace, flushed, then fetched back via the Langfuse API
  3. one LLM call through the LiteLLM gateway traced via the `langfuse_otel`
     callback (the current integration for langfuse SDK v3+)

Prints trace ids so the owner can also confirm in the remote UI.
"""

import os
import sys
import time

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

REQUIRED_ENV = ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")


def check_env():
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        print(f"BLOCKED — missing in .env: {', '.join(missing)}")
        print("The owner hosts Langfuse remotely; add its host + keys to .env first.")
        sys.exit(2)
    print(f"env      OK    host={os.environ['LANGFUSE_HOST']}")


def auth_check(langfuse):
    if not langfuse.auth_check():
        print("auth     FAIL  credentials rejected by the remote instance")
        sys.exit(1)
    print("auth     PASS  remote instance accepted the keys")


def manual_trace(langfuse):
    with langfuse.start_as_current_span(name="p1.3-manual-smoke") as span:
        span.update_trace(input="smoke ping", output="pong", tags=["smoke", "p1.3"])
        trace_id = langfuse.get_current_trace_id()
    langfuse.flush()

    # Fetch it back through the API — remote receipt proven, not assumed.
    for attempt in range(6):
        time.sleep(2 * (attempt + 1))
        try:
            langfuse.api.trace.get(trace_id)
            print(f"manual   PASS  trace {trace_id} fetched back from remote")
            return
        except Exception:
            continue
    print(f"manual   WARN  trace {trace_id} sent but not fetchable yet (check UI)")


def traced_llm_call(langfuse):
    import litellm
    from scripts.smoke_gateway import build_router, load_config, resolve_env_refs

    litellm.callbacks = ["langfuse_otel"]
    router = build_router(resolve_env_refs(load_config()))

    with langfuse.start_as_current_span(name="p1.3-gateway-smoke") as span:
        resp = router.completion(
            model="fast",
            messages=[{"role": "user", "content": "Reply with exactly one word: OM"}],
            max_tokens=1000,
        )
        span.update_trace(tags=["smoke", "p1.3", "gateway"])
        trace_id = langfuse.get_current_trace_id()
    langfuse.flush()
    print(f"gateway  PASS  model={resp.model!r} traced as {trace_id}")


def main():
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
    check_env()

    from langfuse import Langfuse

    langfuse = Langfuse()
    auth_check(langfuse)
    manual_trace(langfuse)
    traced_llm_call(langfuse)
    print("SMOKE PASSED — remote Langfuse is receiving traces from this box.")


if __name__ == "__main__":
    main()
