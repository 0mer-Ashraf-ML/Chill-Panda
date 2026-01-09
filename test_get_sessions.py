import requests
import sys

def test_get_sessions():
    user_id = "user_abc123"
    # Assuming the server is running on localhost:8000
    # If the user has it running on a different port, this might fail, 
    # but based on common FastAPI defaults and previous context it's likely 8000 or similar.
    url = f"http://127.0.0.1:8000/api/v1/sessions/{user_id}"
    print(f"Testing URL: {url}")
    try:
        response = requests.get(url)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if len(data) > 0:
                if "user_id" in data[0]:
                    print("✅ Success: user_id found in response")
                else:
                    print("❌ Failure: user_id NOT found in response")
            else:
                print("ℹ️ No sessions found for this user, but request succeeded.")
        else:
            print(f"❌ Failure: Unexpected status code {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")

if __name__ == "__main__":
    test_get_sessions()
