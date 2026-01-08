import os
import json
import requests
from collections import defaultdict
import datetime
import uuid

def call_api(path: str, method: str = "GET", headers: dict = None, data: dict = None, params: dict = None):
    API_BASE_URL = os.getenv("API_BASE_URL")
    endpoint = f"{API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    method = method.upper()
    headers = headers or {}
    
    try:
        response = requests.request(
            method=method,
            url=endpoint,
            headers=headers,
            json=data,
            params=params
        )
        response.raise_for_status()
        print(f"Response from {method} {endpoint}: Successfull")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err} - Response: {response.text}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None
