"""Summarization middleware — §7.1: long counseling sessions are condensed
in-flight; the checkpoint stays intact.

Uses LangChain 1.x ``SummarizationMiddleware`` (verified against installed
API 2026-07-17: trigger/keep take ``("tokens"|"messages"|"fraction", n)``
tuples). The summarizer model defaults to the shared subagent model
(Azure o4-mini, owner decision 2026-07-18).
"""

from langchain.agents.middleware import SummarizationMiddleware

#: Summarize once the window passes this size; keep the recent tail intact.
TRIGGER = ("tokens", 6000)
KEEP = ("messages", 20)


def make_summarization(model=None) -> SummarizationMiddleware:
    """§20.3 stack position 3. Uses the shared subagent model (Azure o4-mini)
    for summaries by default; pass a model to override."""
    if model is None:
        from arjun.harness.gateway import fast_chat_model

        model = fast_chat_model()
    return SummarizationMiddleware(model=model, trigger=TRIGGER, keep=KEEP)
