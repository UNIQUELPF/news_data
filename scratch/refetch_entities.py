import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from pipeline.db import get_db_connection
from pipeline.llm_client import translate_article_content

def refetch_missing_entities():
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        
        # 查找这 624 篇国际文章（已翻译但企业字段仍为空的）
        cursor.execute("""
            SELECT 
                a.id, 
                a.title_original, 
                a.content_original,
                a.language
            FROM articles a
            JOIN article_translations t ON a.id = t.article_id
            WHERE a.country_code != 'CHN' 
              AND (a.company IS NULL OR a.company = '' OR a.company = '—')
            ORDER BY a.id DESC
            LIMIT 100; -- 先修复最近的 100 篇高频新闻
        """)
        
        candidates = cursor.fetchall()
        print(f"Found {len(candidates)} high-value articles needing entity re-extraction.")
        
        updated_count = 0
        for art_id, title_orig, content_orig, lang in candidates:
            # 使用新的情报提示词重跑逻辑
            result = translate_article_content(
                title=title_orig,
                content=content_orig,
                source_language=lang
            )
            
            new_companies = result.get("involved_companies")
            new_cat = result.get("category")
            
            if new_companies:
                cursor.execute(
                    """
                    UPDATE articles 
                    SET company = %s, 
                        category = COALESCE(%s, category),
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE id = %s
                    """,
                    (new_companies, new_cat, art_id)
                )
                connection.commit() # 即时提交，防止事务丢失
                updated_count += 1
                print(f"[{updated_count}] DB-COMMITTED ID {art_id}: {new_companies}")
        
        connection.commit()
        print(f"Batch recovery complete. Updated entities for {updated_count} articles.")
        
    except Exception as e:
        print(f"Error during entity recovery: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    refetch_missing_entities()
