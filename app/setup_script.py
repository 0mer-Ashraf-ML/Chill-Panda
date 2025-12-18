import os
import sys
from dotenv import load_dotenv

load_dotenv()

def setup_environment():
    """Setup script for initial configuration"""
    
    # Check environment variables
    required_vars = [
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_ENVIRONMENT"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        for var in missing_vars:
            print(f"  - {var}")
        return False
    
    os.system("pip install -r requirements.txt")
    
    return True

if __name__ == "__main__":
    setup_environment()