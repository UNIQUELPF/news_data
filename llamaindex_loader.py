from llama_index.readers.database import DatabaseReader
from llama_index.core import VectorStoreIndex, StorageContext
import os

def load_news_to_llamaindex(table_name="bra_247"):
    """
    Example script to load scraped news from PostgreSQL into LlamaIndex.
    """
    print(f"Starting data load from table: {table_name}...")
    
    # Initialize DatabaseReader with your Docker settings
    # Note: Use 'localhost' if running this script outside the Docker network.
    # Use 'postgres' if running as a container in the same network.
    reader = DatabaseReader(
        scheme="postgresql",
        host="localhost", 
        port=5432,
        user="your_user",
        password="your_password",
        dbname="scrapy_db",
    )

    # SQL Query to fetch the relevant columns
    query = f"SELECT content, title, url, publish_time FROM {table_name};"

    # Load data into LlamaIndex Documents
    # The 'content' column is used as the text, others become metadata
    documents = reader.load_data(query=query)
    
    print(f"Successfully loaded {len(documents)} documents from {table_name}.")
    
    # Optional: Build an index (requires OPENAI_API_KEY environment variable)
    # if "OPENAI_API_KEY" in os.environ:
    #     index = VectorStoreIndex.from_documents(documents)
    #     print("Vector Index built successfully.")
    #     return index
    
    return documents

if __name__ == "__main__":
    # Example: Load Brazil data
    docs = load_news_to_llamaindex("bra_247")
    
    # Inspect the first document
    if docs:
        print("\n--- Example Document ---")
        print(f"Title: {docs[0].metadata.get('title')}")
        print(f"URL: {docs[0].metadata.get('url')}")
        print(f"Text Snippet: {docs[0].text[:100]}...")
