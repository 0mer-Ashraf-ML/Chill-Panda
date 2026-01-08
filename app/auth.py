from fastapi import Header, HTTPException
from .config import OPENAI_API_KEY

def verify_key(x_api_key: str = Header(None)):
    if x_api_key != OPENAI_API_KEY:
        raise HTTPException(status_code=401, detail='Invalid API Key')