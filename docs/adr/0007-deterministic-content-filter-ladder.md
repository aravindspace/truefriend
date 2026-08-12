# ADR 0007 — Deterministic content-filter mitigation, not provider fallback

**Status:** Accepted (2026-07-21)

## Context

Arjun counsels from the Bhagavad Gita, whose Canon is a battlefield discourse — the
retrieved chunks are dense with "kill", "slay", "slaughter", "bloodshed", and the
people who come to him sometimes speak of ending their own lives. Both are exactly
the content a provider safety filter is built to block.

The original design (§5, ADR-era) leaned on LiteLLM `content_policy_fallbacks`: when
Azure's filter rejects a prompt, re-send it to another provider. The P1.21 golden run
proved this insufficient, for reasons found empirically, not assumed:

1. **The fallback providers had no quota.** Anthropic was hard-capped until
   2026-08-01; Gemini's free tier had dropped to 20 requests/day and was spent; Groq's
   free tier caps at 8000 TPM while a counseling compose prompt (after the P1.20
   backfill enriched the graph to ~40 retrieved chunks) runs ~22000 tokens. With every
   non-Azure escape unavailable, `content_policy_fallbacks` degraded straight to the
   honest fallback — and a self-harm turn that falls to the generic fallback loses its
   helpline. That is a safety failure, not a cosmetic one.
2. **Azure does not filter on keywords.** Probing showed single words ("kill",
   "suicide") and lone sentences pass; the filter scores **aggregate contextual
   severity**, so the trigger is the *accumulation* of heavy content in one prompt.
3. **The block is intermittent.** At the medium-severity boundary where our prompts
   sit, the *same* prompt filters on one call and passes on the next.

## Decision

Handle content-policy rejections deterministically in the harness
(`arjun/harness/content_filter.py`), not by hoping another provider is free. Azure o4-mini
is the default for every tier including judge (§15 independence stays waived); other
providers remain only as 429/5xx fallbacks. On a `ContentPolicyViolationError` the
gateway walks a three-rung ladder:

1. **Retry** the same call once — intermittency alone often clears it.
2. **Sanitize + retry** — soften the heaviest violence words to drop aggregate
   severity below the threshold. The `chunk_id` is untouched, so citation traceability
   (§10) holds; only the displayed quote softens, as a last resort. Skipped when only
   `self_harm` fired — a person's own words are never reworded.
3. **Give up gracefully**, branching on the Azure error's category (`self_harm` = the
   person; `violence`/`hate`/`sexual` = the Canon). A structured caller gets `""` and
   degrades to its safe default; `frontal_compose` raises `ContentFilterBlocked` and
   voices a **tailored safe reply** built WITHOUT the triggering text — helpline +
   warmth on self-harm, a firm in-character decline on off-mission. The Gut treats a
   content-filtered input as a strong distress signal (fail-safe: flags self-harm when
   the filter named it). Output-side filtering (200 + `finish_reason=content_filter`)
   enters the same ladder.

## Consequences

- **Self-harm turns are robust to the filter.** P1.21: self-harm scenarios went from
  0/5 to 5/5 passing (helpline present), independent of any other provider's quota.
- **A softened Canon quote is possible** on a filtered violence turn — an accepted,
  documented tradeoff (traceability preserved) in exchange for keeping the turn alive
  rather than dropping to the dead fallback. Supersedes the strict "never rephrase
  Canon" wording of §5.
- **The golden set is the regression guard**: battlefield + multilingual self-harm
  scenarios force the heaviest content every run, so a filter or ladder regression
  fails evals, not production.
- Cross-provider `content_policy_fallbacks` is removed from `config/litellm.yaml`.
