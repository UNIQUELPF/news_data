import os
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "news_articles"

def get_qdrant_client(timeout=10.0):
    return QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=timeout)

def init_qdrant_schema(vector_size: int = None):
    if vector_size is None:
        # Keep Qdrant collection dimensions aligned with the configured embedding model.
        provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        if provider == "demo":
            vector_size = 4
            model = ""
        elif provider == "local":
            model = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-m3")
        else:
            model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        if provider != "demo":
            model_name = model.lower()
            if "bge-m3" in model_name or "bge-large" in model_name:
                vector_size = 1024
            elif "bge-small" in model_name or "bge-base" in model_name:
                vector_size = 768
            else:
                vector_size = 1536 # Default for OpenAI ada-002 and text-embedding-3-small

    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        print(f"Creating Qdrant collection: {COLLECTION_NAME} (size={vector_size})")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    else:
        print(f"Qdrant collection {COLLECTION_NAME} already exists.")
        
    # Create metadata payload indexes for fast filtering
    print(f"Ensuring payload indexes for {COLLECTION_NAME}...")
    client.create_payload_index(COLLECTION_NAME, field_name="company", field_schema="keyword")
    client.create_payload_index(COLLECTION_NAME, field_name="category", field_schema="keyword")
    client.create_payload_index(COLLECTION_NAME, field_name="publish_time", field_schema="datetime")
    print("Qdrant schema initialization complete.")
