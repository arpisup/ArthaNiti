import json
import urllib.request

def run_test():
    base_url = "http://localhost:8000"
    
    # 1. Register
    reg_data = {
        "username": "test_farmer",
        "password": "password123",
        "profile": {
            "age": 30,
            "annual_income": 150000,
            "occupation": "farmer",
            "state": "Tamil Nadu",
            "sector": "agriculture",
            "employment_status": "self_employed",
            "area": "rural",
            "family_size": 4
        }
    }
    
    req = urllib.request.Request(f"{base_url}/api/register", data=json.dumps(reg_data).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print("Register:", res.keys())
            token = res.get("token")
    except Exception as e:
        print("Register Error:", e)
        # Maybe already exists, let's login
        req = urllib.request.Request(f"{base_url}/api/login", data=json.dumps(reg_data).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print("Login:", res.keys())
            token = res.get("token")
            
    # 2. Chat Query
    chat_data = {
        "message": "What happens if the government increases agriculture support massively?"
    }
    
    req = urllib.request.Request(f"{base_url}/api/chat", data=json.dumps(chat_data).encode(), headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print("\nIntent Parsed:", res["intent"])
            print("\nLLM Reply:", res["reply"])
    except Exception as e:
        print("Chat Error:", e)
        if hasattr(e, 'read'):
            print(e.read().decode())

if __name__ == "__main__":
    run_test()
