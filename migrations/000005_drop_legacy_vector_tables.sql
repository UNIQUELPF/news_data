-- 彻底删除冗余的向量与切片表
-- 这些数据现已完全存储在 Qdrant (news_articles collection) 的 Payload 中。

DROP TABLE IF EXISTS article_embeddings CASCADE;
DROP TABLE IF EXISTS article_chunks CASCADE;
