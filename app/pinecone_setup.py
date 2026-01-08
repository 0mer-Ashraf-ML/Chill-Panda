import os
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

def initialize_pinecone():
    """Initialize Pinecone index for document storage"""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    
    index_name = os.getenv("PINECONE_INDEX_NAME", "chill-panda-index")
    
    # Check if index exists
    if index_name not in pc.list_indexes().names():
        # Create index if it doesn't exist
        pc.create_index(
            name=index_name,
            dimension=1536,  # OpenAI ada-002 embedding dimension
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
    
    return pc.Index(index_name)

def get_pinecone_index():
    """Get Pinecone index instance"""
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME", "chill-panda-index")
    return pc.Index(index_name)