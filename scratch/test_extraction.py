import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.getcwd())

from pipeline.llm_client import translate_article_content

def test():
    # 测试文章：ID 5817 的原始信息
    title = "Google expands AI chip partnership with Intel"
    content = "Google Cloud and Intel announced today an expanded partnership to develop new AI-focused infrastructure..."
    
    print("Testing with Optimized Intelligence Prompt...")
    result = translate_article_content(
        title=title,
        content=content,
        source_language="en"
    )
    
    print("\n--- Extraction Result ---")
    print(f"Title Translated: {result.get('title_translated')}")
    print(f"Entities Found: {result.get('involved_companies')}")
    print(f"Category: {result.get('category')}")

if __name__ == "__main__":
    test()
