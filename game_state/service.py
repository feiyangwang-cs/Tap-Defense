from flask import Flask, jsonify, request
import threading


class GameState:
    def __init__(self):
        self.difficulty = "normal"  # "easy" / "normal" / "hard"
        self.volume = 50  # 0 - 100
        self.stage = "menu"  # "menu", "playing", "paused", "game_over"
        self.want_start = False
        self.want_pause = False
        self.want_resume = False
        self.want_restart = False
        self.want_exit = False
        self.remaining_enemies = 0
        self.player_hp = 0
        self.chat_status = None # listen, think, speak

    def to_dict(self):
        return {
            "difficulty": self.difficulty,
            "volume": self.volume,
            "stage": self.stage,
            "want_start": self.want_start,
            "want_pause": self.want_pause,
            "want_resume": self.want_resume,
            "want_restart": self.want_restart,
            "want_exit": self.want_exit,
            "remaining_enemies": self.remaining_enemies,
            "player_hp": self.player_hp,
            "chat_status": self.chat_status
        }

# Use a lock to ensure thread-safe access to the state object
state_lock = threading.Lock()
state = GameState()

# --- Flask App ---
app = Flask(__name__)

@app.route('/state', methods=['GET'])
def get_state():
    """Returns the current game state."""
    with state_lock:
        return jsonify(state.to_dict())

@app.route('/state', methods=['PUT'])
def update_state():
    """Allows the game client to update parts of the state."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    with state_lock:
        for key, value in data.items():
            if hasattr(state, key):
                setattr(state, key, value)
        print(f"[API] Game client updated state: {data}")
    return jsonify(state.to_dict())

@app.route('/config/difficulty', methods=['POST'])
def set_difficulty_endpoint():
    """Sets the game difficulty."""
    data = request.get_json()
    level = data.get('level')
    if level not in {"easy", "normal", "hard"}:
        return jsonify({"error": "Invalid difficulty level"}), 400

    with state_lock:
        state.difficulty = level
        print(f"[API] Difficulty set to {level}")
    return jsonify({"status": "success", "difficulty": level})

@app.route('/config/chat_status', methods=['POST'])
def set_chat_status_endpoint():
    """Sets the chat status."""
    data = request.get_json()
    status = data.get('status')
    if status not in { None, "listen", "think", "speak" }:
        return jsonify({"error": "Invalid status"}), 400

    with state_lock:
        state.chat_status = status
        print(f"[API] Difficulty set to {level}")
    return jsonify({"status": "success", "chat_status": status})

@app.route('/config/volume', methods=['POST'])
def set_volume_endpoint():
    """Sets the game volume."""
    data = request.get_json()
    percent = data.get('percent')
    if not isinstance(percent, int) or not (0 <= percent <= 100):
        return jsonify({"error": "Volume must be an integer between 0 and 100"}), 400

    with state_lock:
        state.volume = percent
        print(f"[API] Volume set to {percent}%")
    return jsonify({"status": "success", "volume": percent})

@app.route('/command/<string:command_name>', methods=['POST'])
def issue_command(command_name):
    """Issues a command to the game (e.g., start, pause)."""
    attr_name = f"want_{command_name}"
    if not hasattr(state, attr_name):
        return jsonify({"error": "Invalid command"}), 400

    with state_lock:
        setattr(state, attr_name, True)
        print(f"[API] Command issued: {command_name}")
    return jsonify({"status": "success", "command_issued": command_name})

@app.route('/command/<string:command_name>', methods=['DELETE'])
def consume_command(command_name):
    """Called by the game to signal it has consumed a command."""
    attr_name = f"want_{command_name}"
    if not hasattr(state, attr_name):
        return jsonify({"error": "Invalid command"}), 400

    with state_lock:
        setattr(state, attr_name, False)
        print(f"[API] Command consumed: {command_name}")
    return jsonify({"status": "success", "command_consumed": command_name})

def run_app():
    app.run(host='127.0.0.1', port=5050, debug=False)

if __name__ == '__main__':
    print("=== Game API Server ===")
    print("Listening on http://127.0.0.1:5050")
    run_app()