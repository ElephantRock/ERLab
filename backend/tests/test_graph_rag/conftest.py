"""Restore real chromadb for graph embedding tests and provide EphemeralClient fixture."""

import sys

import pytest


def _restore_real_chromadb():
    """Force real chromadb into sys.modules by removing all traces and reimporting."""
    keys = [k for k in list(sys.modules) if k == "chromadb" or k.startswith("chromadb.")]
    for k in keys:
        del sys.modules[k]
    import chromadb
    return chromadb


_chromadb = _restore_real_chromadb()


@pytest.fixture
def chroma_client():
    # Ensure sys.modules has real chromadb before creating client
    current = sys.modules.get("chromadb")
    if current is None or not hasattr(current, "EphemeralClient"):
        _restore_real_chromadb()
    return sys.modules["chromadb"].EphemeralClient()
