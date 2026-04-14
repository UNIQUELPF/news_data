import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from pipeline.db import get_db_connection
from pipeline.llm_client import translate_article_content

def quick_fix():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT title_original, content_original, language FROM articles WHERE id = 28720")
        row = cursor.fetchone()
        
        title, content, lang = row
        result = translate_article_content(title=title, content=content, source_language=lang)
        
        new_companies = result.get("involved_companies")
        new_cat = result.get("category")
        
        if new_companies:
            cursor.execute(
                "UPDATE articles SET company = %s, category = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (new_companies, new_cat, 28720)
            )
            connection.commit()
            print(f"SUCCESS: Article 28720 updated with entities: {new_companies}")
    finally:
        connection.close()

if __name__ == "__main__":
    quick_fix()
