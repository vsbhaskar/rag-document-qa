import chromadb
from sentence_transformers import SentenceTransformer
from app import config

model = SentenceTransformer(config.EMBED_MODEL)
client = chromadb.PersistentClient(path=config.CHROMA_PATH)
collection = client.get_or_create_collection(config.COLLECTION_NAME)