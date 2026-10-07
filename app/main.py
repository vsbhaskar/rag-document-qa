import shutil
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app import config
from app.auth import router as auth_router
from app.db import Base, engine, get_db
from app.deps import get_current_user
from app.generate import answer
from app.ingest import delete_vectors, ingest_pdf
from app.models import Document, User

Base.metadata.create_all(bind=engine)   # creates the tables in MySQL on first start

app = FastAPI(title="RAG Document Q&A")
app.include_router(auth_router)


class AskRequest(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    ).all()
    return [{"id": d.id, "filename": d.filename, "chunks": d.chunk_count} for d in docs]


@app.post("/upload")
def upload(file: UploadFile = File(...), user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    name = Path(file.filename).name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    user_dir = config.DATA_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    if dest.stat().st_size > config.MAX_UPLOAD_MB * 1024 * 1024:
        dest.unlink()
        raise HTTPException(status_code=413, detail=f"File is larger than {config.MAX_UPLOAD_MB} MB.")

    try:
        chunks = ingest_pdf(dest, user.id)
    except Exception:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Could not read this PDF.")
    if chunks == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="No readable text found (scanned PDFs are not supported).")

    doc = db.scalar(select(Document).where(Document.user_id == user.id, Document.filename == name))
    if doc:
        doc.chunk_count = chunks
    else:
        db.add(Document(user_id=user.id, filename=name, chunk_count=chunks))
    db.commit()
    return {"filename": name, "chunks_added": chunks}


@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc or doc.user_id != user.id:          # 404, so other users' IDs aren't revealed
        raise HTTPException(status_code=404, detail="Document not found.")
    delete_vectors(user.id, doc.filename)
    (config.DATA_DIR / str(user.id) / doc.filename).unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
    return {"deleted": doc.filename}


@app.post("/ask")
def ask(req: AskRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    has_docs = db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user.id))
    if not has_docs:
        return {"answer": "You haven't uploaded any documents yet. Upload a PDF in the sidebar first.",
                "sources": []}
    text, sources = answer(req.question, user.id)
    return {"answer": text, "sources": [{"file": s, "page": p} for s, p in sources]}