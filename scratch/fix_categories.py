import sys
import os

# Add the project root to sys.path to import local modules
sys.path.append(os.getcwd())

from pipeline.db import get_db_connection
from pipeline.domestic_taxonomy import infer_domestic_category

def fix_missing_categories():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        
        # 查找已翻译但分类为空的国际文章
        cursor.execute("""
            SELECT 
                a.id, 
                t.title_translated, 
                t.content_translated, 
                a.section, 
                a.category as raw_category
            FROM articles a
            JOIN article_translations t ON a.id = t.article_id
            WHERE a.country_code != 'CHN' 
              AND (a.category IS NULL OR a.category = '')
            ORDER BY a.id DESC;
        """)
        
        candidates = cursor.fetchall()
        print(f"Found {len(candidates)} international articles with missing categories.")
        
        updated_count = 0
        for art_id, title_zh, content_zh, section, raw_cat in candidates:
            # 使用翻译后的内容进行分类推理
            new_cat = infer_domestic_category(
                title=title_zh,
                content=content_zh,
                section=section,
                raw_category=raw_cat
            )
            
            if new_cat and new_cat != "其他":
                cursor.execute(
                    "UPDATE articles SET category = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                    (new_cat, art_id)
                )
                updated_count += 1
                if updated_count % 50 == 0:
                    print(f"Updated {updated_count} articles...")
        
        connection.commit()
        print(f"Scan complete. Automatically classified {updated_count} articles based on translated content.")
        
    except Exception as e:
        print(f"Error during category fix: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    fix_missing_categories()
