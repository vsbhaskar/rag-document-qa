import pytest

from app import config
from app.retrieve import retrieve
from app.store import collection

ALICE_TEXT = "overfitting model training data " * 6
BOB_TEXT = "tokenizer vocabulary embedding vector " * 6
QUESTION = "overfitting model training data"


@pytest.fixture
def docs(pdf_pages):
    pdf_pages["alice.pdf"] = [ALICE_TEXT]
    pdf_pages["bob.pdf"] = [BOB_TEXT]
    pdf_pages["scan.pdf"] = [""]          # a PDF with no extractable text


def _user_id(client, headers):
    return client.get("/auth/me", headers=headers).json()["id"]


def test_upload_indexes_a_pdf(client, alice, docs, upload_pdf):
    r = upload_pdf(alice, "alice.pdf")
    assert r.status_code == 200
    assert r.json()["chunks_added"] == 1
    listed = client.get("/documents", headers=alice).json()
    assert [(d["filename"], d["chunks"]) for d in listed] == [("alice.pdf", 1)]


def test_reuploading_replaces_instead_of_duplicating(client, alice, docs, upload_pdf):
    upload_pdf(alice, "alice.pdf")
    upload_pdf(alice, "alice.pdf")
    assert len(client.get("/documents", headers=alice).json()) == 1
    assert collection.count() == 1


def test_non_pdf_is_rejected(client, alice, docs, upload_pdf):
    assert upload_pdf(alice, "notes.txt", "text/plain").status_code == 400


def test_pdf_without_text_is_rejected_and_not_kept(client, alice, docs, upload_pdf):
    assert upload_pdf(alice, "scan.pdf").status_code == 422
    uid = _user_id(client, alice)
    assert not (config.DATA_DIR / str(uid) / "scan.pdf").exists()


def test_unreadable_pdf_is_rejected(client, alice, docs, upload_pdf):
    assert upload_pdf(alice, "broken.pdf").status_code == 422


def test_oversized_upload_is_rejected(client, alice, docs, upload_pdf, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_MB", 0)
    assert upload_pdf(alice, "alice.pdf").status_code == 413


def test_users_only_see_their_own_documents(client, alice, bob, docs, upload_pdf):
    upload_pdf(alice, "alice.pdf")
    assert client.get("/documents", headers=bob).json() == []
    assert [d["filename"] for d in client.get("/documents", headers=alice).json()] == ["alice.pdf"]


def test_two_users_can_upload_the_same_file_name(client, alice, bob, docs, upload_pdf):
    assert upload_pdf(alice, "alice.pdf").status_code == 200
    assert upload_pdf(bob, "alice.pdf").status_code == 200
    assert len(client.get("/documents", headers=alice).json()) == 1
    assert len(client.get("/documents", headers=bob).json()) == 1


def test_retrieval_never_returns_another_users_chunks(client, alice, bob, docs, upload_pdf):
    upload_pdf(alice, "alice.pdf")
    upload_pdf(bob, "bob.pdf")
    bob_id = _user_id(client, bob)
    # min_score=-1 disables the relevance cutoff, so only the user_id filter can keep Alice out
    results = retrieve(QUESTION, user_id=bob_id, min_score=-1.0)
    assert results
    assert all(meta["user_id"] == bob_id for _, meta, _ in results)
    assert all("overfitting" not in text for text, _, _ in results)


def test_ask_uses_only_the_askers_documents(client, alice, bob, docs, upload_pdf, fake_llm):
    upload_pdf(alice, "alice.pdf")
    upload_pdf(bob, "bob.pdf")
    r = client.post("/ask", json={"question": QUESTION}, headers=alice)
    assert r.status_code == 200
    assert r.json()["sources"] == [{"file": "alice.pdf", "page": 1}]
    assert len(fake_llm.calls) == 1
    prompt = fake_llm.calls[0]["messages"][1]["content"]
    assert "overfitting" in prompt and "tokenizer" not in prompt


def test_other_users_question_is_refused_without_calling_the_llm(client, alice, bob, docs, upload_pdf, fake_llm):
    upload_pdf(alice, "alice.pdf")
    upload_pdf(bob, "bob.pdf")
    r = client.post("/ask", json={"question": QUESTION}, headers=bob)
    assert "don't have information" in r.json()["answer"]
    assert fake_llm.calls == []


def test_ask_without_documents_gives_a_friendly_message(client, alice, fake_llm):
    r = client.post("/ask", json={"question": QUESTION}, headers=alice)
    assert "haven't uploaded" in r.json()["answer"]
    assert fake_llm.calls == []


def test_cannot_delete_another_users_document(client, alice, bob, docs, upload_pdf):
    upload_pdf(alice, "alice.pdf")
    doc_id = client.get("/documents", headers=alice).json()[0]["id"]
    assert client.delete(f"/documents/{doc_id}", headers=bob).status_code == 404
    assert len(client.get("/documents", headers=alice).json()) == 1
    assert retrieve(QUESTION, user_id=_user_id(client, alice), min_score=-1.0)


def test_owner_can_delete_a_document_and_its_vectors(client, alice, docs, upload_pdf):
    upload_pdf(alice, "alice.pdf")
    doc_id = client.get("/documents", headers=alice).json()[0]["id"]
    assert client.delete(f"/documents/{doc_id}", headers=alice).status_code == 200
    assert client.get("/documents", headers=alice).json() == []
    assert collection.count() == 0


def test_deleting_a_missing_document_returns_404(client, alice):
    assert client.delete("/documents/999", headers=alice).status_code == 404