import os
import re
import sys
import tempfile
import types
import zlib
from pathlib import Path
from types import SimpleNamespace

# The app reads its settings when it is imported, so the test environment is set first.
_TMP = tempfile.mkdtemp(prefix="rag_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + Path(_TMP, "test.db").as_posix()
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["LLM_API_KEY"] = "test-key"
os.environ["LLM_BASE_URL"] = "http://localhost:9/v1"
os.environ["LLM_MODEL"] = "test-model"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
import numpy as np
import pytest
from fastapi.testclient import TestClient


class FakeModel:
    """Deterministic stand-in for the embedding model: hashed bag-of-words, unit length."""
    DIM = 256

    def encode(self, texts, normalize_embeddings=False, **kwargs):
        vectors = np.zeros((len(texts), self.DIM), dtype="float64")
        for i, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vectors[i, zlib.crc32(word.encode()) % self.DIM] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms


# Replace app.store (which would load the real model) with a fake plus a real in-memory Chroma.
_store = types.ModuleType("app.store")
_store.model = FakeModel()
_store.client = chromadb.EphemeralClient()
_store.collection = _store.client.get_or_create_collection("documents")
sys.modules["app.store"] = _store

from app import config
from app.db import Base, engine
from app.main import app as fastapi_app

PDF_PAGES = {}   # file name -> list of page texts the fake PDF reader will return


class FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class FakeReader:
    def __init__(self, path):
        self.pages = [FakePage(t) for t in PDF_PAGES[Path(path).name]]   # KeyError = unreadable PDF


class FakeLLM:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content="Answer from the documents (alice.pdf, page 1).")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    ids = _store.collection.get()["ids"]
    if ids:
        _store.collection.delete(ids=ids)
    PDF_PAGES.clear()
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("app.ingest.PdfReader", FakeReader)


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    llm = FakeLLM()
    monkeypatch.setattr("app.generate.client", llm)
    return llm


@pytest.fixture
def pdf_pages():
    return PDF_PAGES


@pytest.fixture
def client():
    return TestClient(fastapi_app)


def _register(client, email, password="correct-horse-1"):
    r = client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def alice(client):
    return _register(client, "alice@example.com")


@pytest.fixture
def bob(client):
    return _register(client, "bob@example.com")


@pytest.fixture
def upload_pdf(client):
    def _upload(headers, name, content_type="application/pdf"):
        return client.post("/upload", headers=headers,
                           files={"file": (name, b"%PDF-1.4 test", content_type)})
    return _upload