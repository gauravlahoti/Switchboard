import pytest

from app import audit
from app.store import store


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Every test gets its own synthetic database and its own audit file."""
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr(store, "_path", tmp_path / "synthetic.db")
    store.reset()
    yield tmp_path / "audit.jsonl"
