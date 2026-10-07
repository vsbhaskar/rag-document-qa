import re
from pathlib import Path
from pypdf import PdfReader
from app import config
from app.store import collection, model


def clean_text(text: str) -> str:
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = config.MAX_CHARS, overlap_sentences: int = 1) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current, length = [], [], 0
    for s in sentences:
        if length + len(s) > max_chars and current:
            chunks.append(" ".join(current))
            current = current[-overlap_sentences:]
            length = sum(len(x) for x in current)
        current.append(s)
        length += len(s)
    if current:
        chunks.append(" ".join(current))
    return chunks


def delete_vectors(user_id: int, filename: str) -> None:
    collection.delete(where={"$and": [{"user_id": user_id}, {"source": filename}]})


def ingest_pdf(path: Path, user_id: int) -> int:
    """Embed a PDF for one user. Returns the number of chunks added."""
    delete_vectors(user_id, path.name)          # re-uploading replaces, not duplicates
    reader = PdfReader(path)
    total = 0
    for page_num, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        chunks = [c for c in chunk_text(text) if len(c) >= config.MIN_CHUNK_CHARS]
        if not chunks:
            continue
        embeddings = model.encode(chunks, normalize_embeddings=True).tolist()
        collection.add(
            ids=[f"{user_id}-{path.name}-p{page_num}-c{i}" for i in range(len(chunks))],
            documents=chunks,
            embeddings=embeddings,
            metadatas=[{"user_id": user_id, "source": path.name, "page": page_num}] * len(chunks),
        )
        total += len(chunks)
    return total