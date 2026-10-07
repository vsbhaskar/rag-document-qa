import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
CHROMA_PATH = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "documents"

# Database: use DATABASE_URL if set (handy for deployment), otherwise build it from DB_* settings.
# Building it from parts means special characters in the password need no manual URL-encoding.
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
else:
    if not os.getenv("DB_PASSWORD"):
        raise RuntimeError("DB_PASSWORD is missing from .env")
    DATABASE_URL = URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "rag_user"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "rag_app"),
        query={"charset": "utf8mb4"},
    )

EMBED_MODEL = "all-MiniLM-L6-v2"
MAX_CHARS = 800
MIN_CHUNK_CHARS = 100
TOP_K = 4
MIN_SCORE = 0.45
MAX_UPLOAD_MB = 20

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing from .env")
TOKEN_EXPIRE_MINUTES = 60

LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")