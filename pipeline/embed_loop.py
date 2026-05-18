import time
from pipeline.db import get_db_connection
from pipeline.tasks.embed import embed_article

print("Starting custom embedding loop...")
try:
    while True:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM articles 
                WHERE translation_status = 'completed' 
                  AND embedding_status = 'pending'
                ORDER BY id DESC
                LIMIT 50
                """
            )
            rows = cursor.fetchall()
            if not rows:
                time.sleep(2)
                continue
            
            article_ids = [row[0] for row in rows]
            print(f"Found {len(article_ids)} articles to embed. Processing...")
            for aid in article_ids:
                try:
                    res = embed_article(aid)
                    print(f"Embedded article {aid}: {res['status']}")
                except Exception as e:
                    print(f"Failed to embed article {aid}: {e}")
        finally:
            conn.close()
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")
