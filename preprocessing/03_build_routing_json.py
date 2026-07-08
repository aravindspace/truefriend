"""
03_build_routing_json.py

Read ministructure.txt + chunks_tagged.jsonl → LLM-assisted expansion
into routing/ministructure.json via Azure o4-mini structured output.
"""

import json
import re
from typing import Literal
from pydantic import BaseModel, field_validator, model_validator

from config import (
    get_azure_llm,
    retry_with_backoff,
    processing_pause,
    get_logger,
    MINISTRUCTURE_PATH,
    CHUNKS_TAGGED_PATH,
    ROUTING_JSON_PATH,
    ROUTING_DIR,
)

logger = get_logger("build_routing_json")

# ── Pydantic models for structured output ────────────────────────────

class RoutingEntry(BaseModel):
    anartha: Literal["Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya"]
    guna: Literal["Satva", "Rajas", "Tamas"]
    section: int

    @model_validator(mode="before")
    @classmethod
    def normalize_keys_and_values(cls, data):
        if not isinstance(data, dict):
            return data
        
        # 1. Normalize Keys
        if "dominant_anartha" in data and "anartha" not in data:
            data["anartha"] = data.pop("dominant_anartha")
        if "dominant_guna" in data and "guna" not in data:
            data["guna"] = data.pop("dominant_guna")
        if "dominant_mode" in data and "guna" not in data:
            data["guna"] = data.pop("dominant_mode")

        # 2. Normalize Anartha (Case and substring matching)
        anartha_val = data.get("anartha")
        if isinstance(anartha_val, str):
            anartha_val = anartha_val.strip()
            valid_anarthas = ["Kama", "Krodha", "Lobha", "Moha", "Mada", "Matsarya"]
            for val in valid_anarthas:
                if val.lower() == anartha_val.lower() or val.lower() in anartha_val.lower():
                    data["anartha"] = val
                    break

        # 3. Normalize Guna (Sattva -> Satva)
        guna_val = data.get("guna")
        if isinstance(guna_val, str):
            guna_val = guna_val.strip().lower()
            if "sattva" in guna_val or "satva" in guna_val:
                data["guna"] = "Satva"
            elif "rajas" in guna_val:
                data["guna"] = "Rajas"
            elif "tamas" in guna_val:
                data["guna"] = "Tamas"

        # 4. Normalize Section
        sect_val = data.get("section")
        if isinstance(sect_val, str):
            match = re.search(r"\d+", sect_val)
            if match:
                data["section"] = int(match.group())
            else:
                sect_val_lower = sect_val.lower()
                if "foundation" in sect_val_lower or "reality" in sect_val_lower:
                    data["section"] = 1
                elif "guna" in sect_val_lower or "environment" in sect_val_lower or "modes" in sect_val_lower:
                    data["section"] = 2
                elif "anartha" in sect_val_lower or "reaction" in sect_val_lower or "generation" in sect_val_lower:
                    data["section"] = 3
                elif "karma" in sect_val_lower or "direction" in sect_val_lower:
                    data["section"] = 4
                elif "yoga" in sect_val_lower or "ladder" in sect_val_lower or "escape" in sect_val_lower:
                    data["section"] = 5

        return data


class RoutingSchema(BaseModel):
    routing_table: dict[str, RoutingEntry]  # problem_domain -> routing
    anartha_canonical_incidents: dict[str, list[str]]  # anartha -> chunk_ids / brief_summaries
    yoga_analogies_fallback: dict[str, list[str]]  # yoga -> chunk_ids / brief_summaries
    personality_dynasty_lookup: dict[str, str]  # personality -> dynasty info


# ── Helpers ──────────────────────────────────────────────────────────

def read_ministructure() -> str:
    """Read the philosophical framework text file."""
    logger.info("Reading ministructure from %s", MINISTRUCTURE_PATH)
    with open(MINISTRUCTURE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def read_chunks_condensed() -> list[dict]:
    """
    Read chunks_tagged.jsonl and return a condensed list suitable for
    the LLM context window.  Only the fields the LLM needs are kept.
    """
    logger.info("Reading tagged chunks from %s", CHUNKS_TAGGED_PATH)
    condensed = []
    with open(CHUNKS_TAGGED_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            condensed.append({
                "chunk_id": chunk["chunk_id"],
                "chunk_type": chunk["chunk_type"],
                "brief_summary": chunk.get("brief_summary", ""),
                "personality": chunk.get("personality", ""),
                "anartha_tag": chunk.get("anartha_tag", ""),
                "yoga_solution": chunk.get("yoga_solution", ""),
                "guna_environment": chunk.get("guna_environment", ""),
                "problem_domain": chunk.get("problem_domain", ""),
            })
    logger.info("Condensed %d chunks for LLM context", len(condensed))
    return condensed


SYSTEM_PROMPT = """\
You are a Vedic scholar creating a routing schema for a Bhagavad Gita RAG system.

You have two inputs:
1. The philosophical teaching framework (ministructure) with 5 sections covering: \
Foundation of Reality, Three Gunas, Six Anarthas, Three-fold Karma, and the Yoga Ladder.
2. A list of tagged chunks from the Gita discourse, each with metadata including \
chunk_type, personality, anartha_tag, yoga_solution, guna_environment, problem_domain, \
and brief_summary.

Your task: Build a routing schema that maps user problems to the correct Gita teachings.

ROUTING TABLE:
- Map each problem_domain (found across all chunks) to its most relevant Anartha, \
dominant Guna, and teaching Section.
- Problem domains include: career, family, duty, purpose, loss, envy, identity, \
relationships, morality, self-realization, etc.
- Base your mappings on the philosophical framework: which Anartha drives problems \
in each domain? Which Guna environment produces that Anartha?

ANARTHA CANONICAL INCIDENTS:
- For each of the 6 Anarthas, list the chunk brief_summaries (or chunk_ids) of \
HISTORICAL_ACCOUNT chunks that best illustrate that Anartha.
- These are the go-to incidents the system will retrieve when a user's problem maps \
to a given Anartha.

YOGA ANALOGIES FALLBACK:
- For each of the 4 Yoga paths, list the chunk brief_summaries (or chunk_ids) of \
ANALOGY chunks that best illustrate that Yoga.
- These serve as fallback analogies if the graph traversal misses.

PERSONALITY DYNASTY LOOKUP:
- For each personality found in the chunks, provide their dynasty and role.
- Examples: "Arjuna": "Kuru (Pandava), warrior, disciple of Krishna", \
"Krishna": "Yadu dynasty, Supreme Personality of Godhead"

Be comprehensive — capture every problem_domain and personality found in the chunks.\
"""


# ── Main pipeline ────────────────────────────────────────────────────

@retry_with_backoff()
def call_llm_structured(llm, system_prompt: str, user_prompt: str) -> RoutingSchema:
    """Call Azure o4-mini with structured output and return RoutingSchema."""
    from pydantic import ValidationError
    structured_llm = llm.with_structured_output(RoutingSchema, method="function_calling")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        return structured_llm.invoke(messages)
    except ValidationError as e:
        # Get the raw response to inspect the keys/values
        try:
            raw_response = llm.invoke(messages)
            print("\n=== DEBUG: RAW LLM RESPONSE (UNTRUNCATED) ===")
            print(raw_response.content)
            print("============================================\n")
        except Exception as e2:
            print(f"Failed to fetch raw response for debug: {e2}")
        raise e


def main():
    logger.info("=== 03_build_routing_json: START ===")

    # 1. Read inputs
    ministructure_text = read_ministructure()
    chunks_condensed = read_chunks_condensed()

    # 2. Build user prompt with both inputs
    chunks_json_str = json.dumps(chunks_condensed, indent=2, ensure_ascii=False)
    user_prompt = (
        "## Ministructure (Philosophical Framework)\n\n"
        f"{ministructure_text}\n\n"
        "## Tagged Chunks from the Gita Discourse\n\n"
        f"```json\n{chunks_json_str}\n```\n\n"
        "Using both inputs above, produce the complete RoutingSchema."
    )

    # 3. Call LLM with structured output
    logger.info("Calling Azure o4-mini for structured routing schema...")
    llm = get_azure_llm()
    processing_pause()
    routing_schema = call_llm_structured(llm, SYSTEM_PROMPT, user_prompt)

    # 4. Serialize and save
    ROUTING_DIR.mkdir(parents=True, exist_ok=True)
    result_dict = routing_schema.model_dump()

    with open(ROUTING_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)
    logger.info("Saved routing schema to %s", ROUTING_JSON_PATH)

    # 5. Print summary
    print("\n" + "=" * 60)
    print("ROUTING SCHEMA GENERATED")
    print("=" * 60)
    print(f"  Problem domains mapped:  {len(result_dict['routing_table'])}")
    print(f"  Anartha incidents:       {sum(len(v) for v in result_dict['anartha_canonical_incidents'].values())} across 6 anarthas")
    print(f"  Yoga fallback analogies: {sum(len(v) for v in result_dict['yoga_analogies_fallback'].values())} across yoga paths")
    print(f"  Personalities cataloged: {len(result_dict['personality_dynasty_lookup'])}")
    print(f"\nSaved to: {ROUTING_JSON_PATH}")
    print("=" * 60)

    # Print full JSON for inspection
    print("\nFull routing schema:")
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))

    logger.info("=== 03_build_routing_json: DONE ===")


if __name__ == "__main__":
    main()
