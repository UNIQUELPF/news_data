import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from pipeline.db import get_db_connection
from pipeline.llm_client import translate_article_content

def debug_article_28720():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT title_original, content_original, language FROM articles WHERE id = 28720")
        row = cursor.fetchone()
        if not row:
            print("Article 28720 not found.")
            return
            
        title, content, lang = row
        print(f"Original Title: {title}")
        print("Calling LLM for extraction...")
        
        result = translate_article_content(
            title=title,
            content=content,
            source_language=lang
        )
        
        print("\n--- LLM FULL RESPONSE ---")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    finally:
        connection.close()

if __name__ == "__main__":
    debug_article_28720()
