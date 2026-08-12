"""Retrieval subagent — VECTOR store only (ADR 0006). The graph belongs to the
routing subagent; this agent must have no Kuzu access at all."""

import pytest

import arjun.subagents.retrieval as retrieval_mod
from arjun.subagents.retrieval import RetrievalResult, run_retrieval, vector_retrieve


class TestNoGraphAccess:
    def test_module_imports_no_graph_modules(self):
        """Check real imports via AST — prose in the docstring doesn't count."""
        import ast

        tree = ast.parse(open(retrieval_mod.__file__).read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any("kuzu" in m for m in imported), imported
        assert "arjun.retrieval.kuzu_templates" not in imported

    def test_module_namespace_has_no_graph_symbols(self):
        assert not hasattr(retrieval_mod, "run_template")
        assert not hasattr(retrieval_mod, "hybrid_retrieve")


@pytest.mark.integration
class TestVectorRetrieval:
    def test_returns_canon_chunks_from_vector_store(self):
        result = vector_retrieve(
            "grief after losing my father", limbic_bias={"anartha_tag": "Moha"}
        )
        assert isinstance(result, RetrievalResult)
        assert result.found and result.chunks
        assert all(c.chunk_id.startswith("chunk_") for c in result.chunks)
        assert all(c.source in ("canon", "notebook") for c in result.chunks)

    def test_run_retrieval_delegates_to_vector(self):
        result = run_retrieval("battlefield despair", limbic_bias={"anartha_tag": "Moha"})
        assert result.found


class TestResultModel:
    def test_empty_result_validates(self):
        r = RetrievalResult()
        assert r.found is False and r.chunks == []
