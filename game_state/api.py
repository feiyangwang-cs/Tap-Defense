import requests
API_BASE_URL = "http://127.0.0.1:5050"

# --- API Client Functions ---

def set_difficulty(level: str):
    """Sets game difficulty via API."""
    try:
        requests.post(f"{API_BASE_URL}/config/difficulty", json={"level": level}, timeout=0.5)
    except requests.RequestException as e:
        print(f"[API Error] Failed to set difficulty: {e}")

def set_chat_status(status: str):
    """Sets game chat status via API."""
    try:
        requests.post(f"{API_BASE_URL}/config/chat_status", json={"status": status}, timeout=0.5)
    except requests.RequestException as e:
        print(f"[API Error] Failed to set chat_status: {e}")

def set_volume(percent: int):
    """Sets game volume via API."""
    try:
        requests.post(f"{API_BASE_URL}/config/volume", json={"percent": percent}, timeout=0.5)
    except requests.RequestException as e:
        print(f"[API Error] Failed to set volume: {e}")

def get_state():
    """Gets current game state via API."""
    try:
        response = requests.get(f"{API_BASE_URL}/state", timeout=0.5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[API Error] Failed to get state: {e}")
        return None

def issue_command(command: str):
    """Issues a command like 'start' or 'pause' via API."""
    try:
        requests.post(f"{API_BASE_URL}/command/{command}", timeout=0.5)
    except requests.RequestException as e:
        print(f"[API Error] Failed to issue command '{command}': {e}")

def update_state(fields: dict):
    try:
        response = requests.put(f"{API_BASE_URL}/state", json=fields, timeout=0.5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"[API Error] Failed to get state: {e}")
        return None