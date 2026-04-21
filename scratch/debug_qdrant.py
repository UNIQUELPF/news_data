import os
from qdrant_client import QdrantClient

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
print(f"Client type: {type(client)}")
print(f"Has search: {hasattr(client, 'search')}")
print(f"Has query_points: {hasattr(client, 'query_points')}")
print(f"Methods: {[m for m in dir(client) if not m.startswith('_')]}")
