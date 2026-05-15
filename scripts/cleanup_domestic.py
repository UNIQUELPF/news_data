import os
import psycopg2
from qdrant_client import QdrantClient
from qdrant_client.http import models as q_models

# DB Config
DB_NAME = os.getenv("POSTGRES_DB", "scrapy_db")
DB_USER = os.getenv("POSTGRES_USER", "your_user")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "your_password")
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

# Qdrant Config
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = "news_articles"

def cleanup():
    print("Starting cleanup for Domestic News (CHN)...")
    
    # 1. Postgres Cleanup
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT
        )
        cur = conn.cursor()
        
        # Get IDs for Qdrant cleanup later
        cur.execute("SELECT id FROM articles WHERE country_code = 'CHN'")
        article_ids = [row[0] for row in cur.fetchall()]
        print(f"Found {len(article_ids)} domestic articles in Postgres.")
        
        if article_ids:
            # Delete translations first (though cascade should handle it)
            cur.execute("DELETE FROM article_translations WHERE article_id = ANY(%s)", (article_ids,))
            print(f"Deleted translations for {len(article_ids)} articles.")
            
            # Delete articles
            cur.execute("DELETE FROM articles WHERE id = ANY(%s)", (article_ids,))
            print(f"Deleted {len(article_ids)} articles from Postgres.")
            
        conn.commit()
        cur.close()
        conn.close()
        print("Postgres cleanup complete.")
    except Exception as e:
        print(f"Postgres cleanup error: {e}")

    # 2. Qdrant Cleanup
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        
        # Delete by filter
        result = client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=q_models.Filter(
                must=[
                    q_models.FieldCondition(
                        key="country_code",
                        match=q_models.MatchValue(value="CHN"),
                    )
                ]
            ),
        )
        print(f"Qdrant cleanup command sent for CHN. Result: {result}")
    except Exception as e:
        print(f"Qdrant cleanup error: {e}")

if __name__ == "__main__":
    cleanup()
