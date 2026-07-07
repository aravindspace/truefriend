#!/usr/bin/env python3
"""Export the LangGraph compiled graph as a Mermaid diagram image.

Generates two outputs:
1. High-level graph topology (from LangGraph)
2. Detailed architecture diagram showing ReAct agents with their tools

Usage:
  python scripts/export_graph.py                    # PNG output (default)
  python scripts/export_graph.py -o my_graph.png    # custom output path
  python scripts/export_graph.py --mermaid          # raw Mermaid text

Requires: pip install grandalf (for PNG rendering via LangGraph)
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Detailed Mermaid diagram showing ReAct agents with tools
DETAILED_MERMAID = """%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#e8eaf6', 'primaryBorderColor': '#5c6bc0', 'lineColor': '#5c6bc0', 'secondaryColor': '#fff3e0', 'tertiaryColor': '#e8f5e9'}}}%%
graph TD
    START(("__start__")):::startEnd --> identify_user["🪪 identify_user"]:::simpleNode
    identify_user --> supervisor_classify["🧠 supervisor_classify"]:::simpleNode
    supervisor_classify --> maybe_recall:::reactNode
    maybe_recall --> maybe_scholar:::reactNode
    maybe_scholar --> maybe_world:::reactNode
    maybe_world --> supervisor_respond["🗣️ supervisor_respond"]:::simpleNode
    supervisor_respond --> memory_keeper["💾 memory_keeper"]:::simpleNode
    memory_keeper --> summarize_history["📝 summarize_history"]:::simpleNode
    summarize_history --> END(("__end__")):::startEnd

    subgraph recall_sub ["🔄 maybe_recall — ReAct Agent"]
        direction LR
        maybe_recall["🤖 LLM<br/>Think → Act → Observe"]
        recall_tool_1["🔍 search_conversation_memory<br/><i>ChromaDB</i>"]:::toolNode
        maybe_recall -.->|"tool call"| recall_tool_1
        recall_tool_1 -.->|"result"| maybe_recall
    end

    subgraph scholar_sub ["🔄 maybe_scholar — ReAct Agent"]
        direction LR
        maybe_scholar["🤖 LLM<br/>Think → Act → Observe"]
        scholar_tool_1["📖 search_gita_concepts<br/><i>KùzuDB</i>"]:::toolNode
        scholar_tool_2["📜 get_verse<br/><i>KùzuDB</i>"]:::toolNode
        scholar_tool_3["📚 list_all_concepts<br/><i>KùzuDB</i>"]:::toolNode
        scholar_tool_4["📝 search_study_notes<br/><i>MD Files</i>"]:::toolNode
        maybe_scholar -.->|"tool call"| scholar_tool_1
        maybe_scholar -.->|"tool call"| scholar_tool_2
        maybe_scholar -.->|"tool call"| scholar_tool_3
        maybe_scholar -.->|"tool call"| scholar_tool_4
        scholar_tool_1 -.->|"result"| maybe_scholar
        scholar_tool_2 -.->|"result"| maybe_scholar
        scholar_tool_3 -.->|"result"| maybe_scholar
        scholar_tool_4 -.->|"result"| maybe_scholar
    end

    subgraph world_sub ["🔄 maybe_world — ReAct Agent"]
        direction LR
        maybe_world["🤖 LLM<br/>Think → Act → Observe"]
        world_tool_1["🌐 web_search<br/><i>DuckDuckGo</i>"]:::toolNode
        maybe_world -.->|"tool call"| world_tool_1
        world_tool_1 -.->|"result"| maybe_world
    end

    classDef startEnd fill:#c5cae9,stroke:#283593,stroke-width:2px,color:#1a237e
    classDef simpleNode fill:#e8eaf6,stroke:#5c6bc0,stroke-width:1px,color:#1a237e
    classDef reactNode fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100
    classDef toolNode fill:#e8f5e9,stroke:#43a047,stroke-width:1px,color:#1b5e20
"""


def export_mermaid_text(output_path: str) -> None:
    """Export both the LangGraph topology and detailed architecture."""
    from graph.builder import build_graph

    graph = build_graph()
    langgraph_mermaid = graph.get_graph().draw_mermaid()

    combined = f"# LangGraph Topology\n\n```mermaid\n{langgraph_mermaid}\n```\n\n"
    combined += f"# Detailed Architecture (with ReAct Tools)\n\n```mermaid\n{DETAILED_MERMAID}\n```\n"

    out = Path(output_path)
    out.write_text(combined)
    logger.info(f"Mermaid diagrams written to {out}")
    print(f"\n{combined}")


def export_png(output_path: str) -> None:
    """Export the high-level graph as PNG, plus detailed Mermaid as .mmd file."""
    from graph.builder import build_graph

    graph = build_graph()

    # 1. High-level LangGraph PNG
    png_bytes = graph.get_graph().draw_mermaid_png()
    out = Path(output_path)
    out.write_bytes(png_bytes)
    logger.info(f"Graph PNG written to {out} ({len(png_bytes)} bytes)")

    # 2. Detailed architecture Mermaid file (with tools)
    mmd_path = out.with_name("graph_detailed.mmd")
    mmd_path.write_text(DETAILED_MERMAID)
    logger.info(f"Detailed Mermaid diagram written to {mmd_path}")

    # 3. Try to render detailed PNG via mermaid CLI if available
    try:
        import subprocess
        detailed_png = out.with_name("graph_detailed.png")
        result = subprocess.run(
            ["mmdc", "-i", str(mmd_path), "-o", str(detailed_png),
             "-b", "transparent", "-w", "2048"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            logger.info(f"Detailed PNG written to {detailed_png}")
        else:
            logger.info(
                f"mmdc not available or failed — detailed diagram saved as {mmd_path}\n"
                f"To render: npx -y @mermaid-js/mermaid-cli mmdc -i {mmd_path} -o {detailed_png}"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.info(
            f"mmdc CLI not found — detailed diagram saved as {mmd_path}\n"
            f"To render: npx -y @mermaid-js/mermaid-cli mmdc -i {mmd_path} -o graph_detailed.png"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export LangGraph as diagram")
    parser.add_argument(
        "--output", "-o",
        default="graph.png",
        help="Output file path (default: graph.png)",
    )
    parser.add_argument(
        "--mermaid",
        action="store_true",
        help="Export as Mermaid text instead of PNG",
    )
    args = parser.parse_args()

    if args.mermaid:
        out = args.output if args.output.endswith(".md") else "graph.mmd"
        export_mermaid_text(out)
    else:
        export_png(args.output)
