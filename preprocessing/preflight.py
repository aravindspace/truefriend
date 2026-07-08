"""
Preflight check — verify all external services and files before running the pipeline.

Self-healing: automatically downloads the GGUF model if not found.

Usage:
    python preflight.py
"""

import sys
import time
from pathlib import Path

from config import (
    get_azure_llm,
    get_embeddings,
    get_logger,
    GITA_TEXT_PATH,
    MINISTRUCTURE_PATH,
    KURU_FAMILY_PATH,
    LLAMA_EMBEDDING_MODEL_PATH,
    NOMIC_EMBEDDING_DIMS,
    PROJECT_ROOT,
)

logger = get_logger("preflight")

# ---------------------------------------------------------------------------
# GGUF model download URL
# ---------------------------------------------------------------------------
GGUF_DOWNLOAD_URL = (
    "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF"
    "/resolve/main/nomic-embed-text-v1.5.Q8_0.gguf"
)


def check_files() -> bool:
    """Verify all required source files exist and are non-empty."""
    ok = True
    files = [
        ("Gita transcript", GITA_TEXT_PATH),
        ("Ministructure", MINISTRUCTURE_PATH),
        ("Kuru family", KURU_FAMILY_PATH),
    ]
    for label, path in files:
        if not path.exists():
            print(f"  ❌ {label}: NOT FOUND at {path}")
            ok = False
        elif path.stat().st_size == 0:
            print(f"  ❌ {label}: EMPTY at {path}")
            ok = False
        else:
            size_kb = path.stat().st_size / 1024
            print(f"  ✅ {label}: {size_kb:.1f} KB at {path}")
    return ok


def check_azure_llm() -> bool:
    """Ping Azure OpenAI deployment with a simple message."""
    try:
        llm = get_azure_llm()
        start = time.time()
        response = llm.invoke("Say 'Hare Krishna' and nothing else.")
        elapsed = time.time() - start
        content = response.content.strip() if hasattr(response, "content") else str(response).strip()
        print(f"  ✅ Azure o4-mini responded in {elapsed:.1f}s: \"{content[:80]}\"")
        return True
    except Exception as exc:
        print(f"  ❌ Azure o4-mini FAILED: {exc}")
        return False


def ensure_gguf_model() -> bool:
    """
    Check that the GGUF model file exists.  If not, download it from
    Hugging Face (~260 MB for Q8_0).
    """
    import urllib.request

    model_path = Path(LLAMA_EMBEDDING_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path

    if model_path.exists() and model_path.stat().st_size > 0:
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"  ✅ GGUF model found: {model_path.name} ({size_mb:.0f} MB)")
        return True

    # Download
    model_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  📥 GGUF model not found at {model_path}")
    print(f"     Downloading nomic-embed-text-v1.5.Q8_0.gguf …")

    tmp_path = model_path.with_suffix(".gguf.tmp")
    try:
        req = urllib.request.Request(
            GGUF_DOWNLOAD_URL,
            headers={"User-Agent": "gita-rag-preflight/1.0"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 / total
                        mb = downloaded / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        print(
                            f"\r     {mb:.0f}/{total_mb:.0f} MB ({pct:.0f}%)",
                            end="", flush=True,
                        )
        print()  # newline after progress
        tmp_path.rename(model_path)
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"  ✅ Downloaded: {model_path.name} ({size_mb:.0f} MB)")
        return True
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        print(f"  ❌ Download failed: {exc}")
        print(f"     Manual download: wget -O {model_path} {GGUF_DOWNLOAD_URL}")
        return False


def check_embeddings() -> bool:
    """Load the embedding model and run a test embedding."""
    try:
        print("  ⏳ Loading nomic-embed-text-v1.5 model …")
        start = time.time()
        embeddings = get_embeddings()
        load_time = time.time() - start
        print(f"  ✅ Model loaded in {load_time:.1f}s")

        start = time.time()
        result = embeddings.embed_documents(["Bhagavad Gita test embedding"])
        elapsed = time.time() - start
        dim = len(result[0]) if result else 0
        print(f"  ✅ Test embedding in {elapsed:.2f}s: {dim}-dim vector")
        if dim != NOMIC_EMBEDDING_DIMS:
            print(f"  ⚠️  Expected {NOMIC_EMBEDDING_DIMS} dimensions, got {dim}")
        return True
    except Exception as exc:
        print(f"  ❌ Embedding test FAILED: {exc}")
        return False


def check_env_vars() -> bool:
    """Check that required environment variables are set."""
    import os
    ok = True
    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
        "LLAMA_EMBEDDING_MODEL_PATH",
    ]
    for var in required:
        val = os.getenv(var)
        if not val:
            print(f"  ❌ {var}: NOT SET")
            ok = False
        else:
            # Show first 8 chars + masked rest
            masked = val[:8] + "..." if len(val) > 8 else val
            print(f"  ✅ {var}: {masked}")
    return ok


def main() -> None:
    """Run all preflight checks."""
    print("\n" + "=" * 60)
    print("  GITA RAG — PREFLIGHT CHECK")
    print("=" * 60)

    all_ok = True

    print("\n📁 Source Files:")
    all_ok &= check_files()

    print("\n🔑 Environment Variables:")
    all_ok &= check_env_vars()

    print("\n🤖 Azure OpenAI (o4-mini):")
    all_ok &= check_azure_llm()

    print("\n📦 GGUF Embedding Model:")
    all_ok &= ensure_gguf_model()

    if all_ok:
        print(f"\n🧮 nomic-embed-text-v1.5 (Matryoshka {NOMIC_EMBEDDING_DIMS}-dim):")
        all_ok &= check_embeddings()

    print("\n" + "=" * 60)
    if all_ok:
        print("  ✅ ALL CHECKS PASSED — ready to run pipeline!")
    else:
        print("  ❌ SOME CHECKS FAILED — fix issues above before running")
    print("=" * 60 + "\n")

    return all_ok


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
