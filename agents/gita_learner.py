"""Gita Learner — offline batch agent that studies Gita and writes notes.

Reads from: KuzuDB (sacred source)
Writes to: Study Notes (MD files in knowledge/notes/)
Triggered: manually via scripts/run_learner.py
"""
import logging
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from llm import create_llm
from stores import KuzuStore

logger = logging.getLogger(__name__)


def _safe_filename(concept_name: str) -> str:
    """Convert concept name to safe filename."""
    # Only allow alphanumeric, underscore, hyphen
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", concept_name.lower().strip())
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        raise ValueError(f"Cannot create filename for concept: {concept_name}")
    return safe


async def study_concept(concept_name: str, kuzu: KuzuStore) -> str | None:
    """Study a single concept and generate notes."""
    # Get graph data for this concept
    graph_data = kuzu.query_concepts([concept_name])
    
    if not graph_data:
        logger.warning(f"No graph data for concept: {concept_name}")
        return None
    
    # Format graph data
    graph_text = ""
    for r in graph_data:
        graph_text += f"Name: {r['concept']}\n"
        graph_text += f"Description: {r.get('description', 'N/A')}\n"
        if r.get('related_concepts'):
            graph_text += f"Related: {', '.join(r['related_concepts'])}\n"
        if r.get('analogies'):
            graph_text += f"Analogies: {', '.join(r['analogies'])}\n"
        if r.get('verses'):
            graph_text += f"Verses: {', '.join(r['verses'])}\n"
    
    # LLM: generate study notes
    llm = create_llm("gita_learner")
    prompt_template = Path(__file__).parent.parent.joinpath("prompts/gita_learner.txt").read_text()
    
    system_prompt = prompt_template.format(
        concept=concept_name,
        graph_data=graph_text,
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Write comprehensive study notes for: {concept_name}"),
    ]
    
    response = await llm.ainvoke(messages)
    return response.content


async def run_learner(
    output_dir: str = "knowledge/notes",
    concepts: list[str] | None = None,
) -> list[str]:
    """Run the Gita Learner batch process.
    
    Args:
        output_dir: Where to write MD note files
        concepts: Specific concepts to study. If None, studies all from graph.
    
    Returns:
        List of generated note file paths.
    """
    notes_dir = Path(output_dir)
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    kuzu = KuzuStore()
    
    if concepts is None:
        concepts = kuzu.get_all_concepts()
    
    if not concepts:
        logger.warning("No concepts found to study")
        return []
    
    logger.info(f"Gita Learner starting — {len(concepts)} concepts to study")
    generated = []
    
    for concept in concepts:
        logger.info(f"Studying: {concept}")
        try:
            notes = await study_concept(concept, kuzu)
            if notes:
                safe_name = _safe_filename(concept)
                filepath = notes_dir / f"{safe_name}.md"
                filepath.write_text(notes)
                generated.append(str(filepath))
                logger.info(f"Notes written: {filepath}")
        except Exception as e:
            logger.error(f"Failed to study '{concept}': {e}")
    
    kuzu.close()
    logger.info(f"Gita Learner complete — {len(generated)} notes generated")
    return generated
