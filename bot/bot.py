import os
import threading
import requests
import boto3
import json
import gzip
import base64
import time
from dotenv import load_dotenv
from botocore.exceptions import BotoCoreError, ClientError

from game_state.api import *
from .persona import (
    format_reply,
    INTENT_DIFFICULTY,
    INTENT_VOLUME,
    INTENT_RULES,
    INTENT_FALLBACK,
    INTENT_PAUSE,
    INTENT_RESUME,
)
from .audio_out import speak
from .audio_vad import record_one_utterance_vad
from .interaction_logger import log_interaction


# --- Constants and Setup ---
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BOT_ID = os.getenv("LEX_BOT_ID")
BOT_ALIAS_ID = os.getenv("LEX_ALIAS_ID")
LOCALE_ID = os.getenv("LEX_LOCALE_ID", "en_US")
SESSION_ID = os.getenv("LEX_SESSION_ID", "pi_voice_session") # Use voice session

lex = boto3.client("lexv2-runtime", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
agent_client = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)

VALID_LEVELS = {"easy", "normal", "hard"}
MIN_CONF = 0.9

# --- Lex Helper Functions ---

def llm_reply(user_text: str, game_state: dict):
    prompt = f"""
You are a sarcastic, slightly rude, playful AI companion inside a tower-defense game.

Your tone:
- snarky but not evil
- tease the player about their choices
- comment on the game state if useful
- ONE short sentence only
- do NOT be polite or formal

Current game state (JSON):
{json.dumps(game_state)}

User said: "{user_text}"

Reply with ONE short, snarky sentence.
"""

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 60,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    }
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",  
        body=json.dumps(body),
    )
    resp_body = json.loads(response["body"].read())

    return resp_body["content"][0]["text"].strip()



def _decode_b64_gzip_json(s: str):
    if not s:
        return None
    raw = base64.b64decode(s)
    data = gzip.decompress(raw)
    return json.loads(data.decode("utf-8"))


def parse_lex_utterance_response(resp):
    headers = resp.get("ResponseMetadata", {}).get("HTTPHeaders", {})

    session_state = _decode_b64_gzip_json(headers.get("x-amz-lex-session-state")) or {}
    intent_obj = session_state.get("intent", {}) or {}
    intent_name = intent_obj.get("name", INTENT_FALLBACK)

    interpretations = _decode_b64_gzip_json(headers.get("x-amz-lex-interpretations")) or []
    confidence = None
    if interpretations:
        top = interpretations[0]
        intent_name = top.get("intent", {}).get("name", intent_name) or intent_name
        confidence = top.get("nluConfidence", {}).get("score")

    raw_slots = intent_obj.get("slots", {}) or {}
    slots = {}
    for k, v in raw_slots.items():
        if v and "value" in v and "interpretedValue" in v["value"]:
            slots[k] = v["value"]["interpretedValue"]

    input_transcript = None
    if "x-amz-lex-input-transcript" in headers:
        try:
            input_transcript = (
                gzip.decompress(base64.b64decode(headers["x-amz-lex-input-transcript"]))
                .decode("utf-8")
            )
        except Exception:
            input_transcript = None

    return intent_name, confidence, slots, input_transcript


def _call_lex_with_retry(audio_bytes: bytes, max_retries: int = 3):
    delay = 0.3
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            resp = lex.recognize_utterance(
                botId=BOT_ID,
                botAliasId=BOT_ALIAS_ID,
                localeId=LOCALE_ID,
                sessionId=SESSION_ID,
                requestContentType="audio/l16; rate=16000; channels=1",
                responseContentType="text/plain; charset=utf-8",
                inputStream=audio_bytes,
            )
            latency_ms = (time.time() - t0) * 1000.0
            return resp, latency_ms
        except (BotoCoreError, ClientError) as e:
            last_exc = e
            print(f"[Lex ERROR] attempt {attempt}/{max_retries}: {e}")
            time.sleep(delay)
            delay *= 2
    raise last_exc


def handle_intent(intent, slots):
    if intent == INTENT_DIFFICULTY:
        level = slots["level"]
        set_difficulty(level)
        action = f"set_difficulty:{level}"
    elif intent == INTENT_VOLUME:
        percent = int(slots["percent"])
        set_volume(percent)
        action = f"set_volume:{percent}"
    elif intent == INTENT_PAUSE:
        issue_command("pause")
        action = "pause_game"
    elif intent == INTENT_RESUME:
        issue_command("resume")
        action = "resume_game"
    elif intent == INTENT_FALLBACK:
        action = "fallback"
    else:
        action = "noop"

    print(f"[State] {get_state()}")
    return action


def main():
    print("=== Pi Voice Chatbot===")
    print("Speak when I'm listening; after my reply, I'll listen again. Ctrl+C to exit.\n")

    while True:
        set_chat_status("listen")
        audio_bytes = record_one_utterance_vad(
            samplerate=16000,
            block_size=1024,
            energy_threshold=50.0,   
            max_speech_ms=6000,
            silence_ms=600,
        )
        if not audio_bytes:
            continue

        duration_sec = len(audio_bytes) / (2 * 16000)  # int16 (2 bytes), 16kHz
        if duration_sec < 0.5:
            print(f"[VAD] Too short ({duration_sec:.2f}s), ignoring.")
            continue

        set_chat_status("think")

        try:
            resp, latency_ms = _call_lex_with_retry(audio_bytes)
        except Exception as e:
            print(f"[Lex FATAL] Failed after retries: {e}")
            speak("I had a problem talking to the server. Please try again in a moment.")
            log_interaction(
                modality="voice",
                input_transcript="",
                intent=INTENT_FALLBACK,
                confidence=None,
                slots={},
                action="lex_error",
                success=False,
                latency_ms=0.0,
            )
            continue

        intent_name, confidence, slots, transcript = parse_lex_utterance_response(resp)
        print(f"[Lex] transcript={transcript!r}, intent={intent_name}, conf={confidence}, slots={slots}")

        if transcript is None or transcript.strip().strip('"') == "":
            print("[Lex] Empty transcript, ignoring this utterance.")
            continue

        MIN_CONF = 0.6
        final_intent = intent_name
        final_slots = dict(slots)

        if intent_name == INTENT_DIFFICULTY:
            lvl = slots.get("level")
            if lvl not in VALID_LEVELS or (confidence is not None and confidence < MIN_CONF):
                final_intent = INTENT_FALLBACK
                final_slots = {}
        elif intent_name == INTENT_VOLUME:
            pct = slots.get("percent")
            try:
                pct_int = int(pct) if pct is not None else None
            except ValueError:
                pct_int = None
            if (
                pct_int is None
                or pct_int < 0
                or pct_int > 100
                or (confidence is not None and confidence < MIN_CONF)
            ):
                final_intent = INTENT_FALLBACK
                final_slots = {}
            else:
                final_slots["percent"] = pct_int
        elif intent_name == INTENT_RULES:
            pass
        elif intent_name == INTENT_FALLBACK:
            state = get_state() or {}

            text = (transcript or "").strip().strip('"')
            if len(text) <= 6 and " " not in text:
                reply = f'"{text}" huh? That''s all you''ve got?'
                print(f"[LocalFallback] {reply}")
                speak(reply)
                continue

            try:
                agent_reply = llm_reply(transcript, state)
                print(f"[Agent] {agent_reply}")
                speak(agent_reply)
            except Exception as e:
                print(f"[Agent ERROR] {e}")
                speak("I have no idea what you just said, but it sounded questionable.")
            continue
    
        try:
            action = handle_intent(final_intent, final_slots)
            success = True
        except Exception as e:
            print(f"[Game ERROR] Failed to handle intent {final_intent}: {e}")
            action = f"game_error:{final_intent}"
            success = False

        log_interaction(
            modality="voice",
            input_transcript=transcript or "",
            intent=final_intent,
            confidence=confidence if confidence is not None else 0.0,
            slots=final_slots,
            action=action,
            success=success,
            latency_ms=latency_ms,
        )

        reply = format_reply(final_intent, final_slots)
        set_chat_status("speak")
        speak(reply)
        set_chat_status(None)
        time.sleep(0.2)


menu_speaked = False
gameover_speaked = False
hp2_speaked = False
dead_speaked = False
few_enemy_speaked = False

def reset_triggers_for_new_round():
    global hp2_speaked, dead_speaked, few_enemy_speaked, gameover_speaked
    hp2_speaked = False
    dead_speaked = False
    few_enemy_speaked = False
    gameover_speaked = False

def trigger_loop(interval: float = 3.0):
    global menu_speaked, gameover_speaked
    global hp2_speaked, dead_speaked, few_enemy_speaked

    last_stage = None

    while True:
        try:
            state = get_state()
            if not state:
                time.sleep(interval)
                continue

            stage = state['stage']

            if last_stage != stage:
                if stage == 'menu' and last_stage in ('game_over', 'playing'):
                    reset_triggers_for_new_round()
                last_stage = stage

            if stage == 'menu' and menu_speaked is False:
                set_chat_status("speak")
                speak("Aha! Welcome to the game! What can I help you?")
                set_chat_status(None)
                menu_speaked = True

            if stage == 'playing':
                if state['player_hp'] == 2 and not hp2_speaked:
                    set_chat_status("speak")
                    speak("Uh-oh, your HP's looking kinda tragic… maybe try not getting hit?")
                    set_chat_status(None)
                    hp2_speaked = True
            
                if state['player_hp'] <= 0 and not dead_speaked:
                    set_chat_status("speak")
                    speak("Wow. Impressive. You managed to die again. Shall we try that one more time?")
                    set_chat_status(None)
                    dead_speaked = True

                if state['remaining_enemies'] <= 5 and not few_enemy_speaked:
                    set_chat_status("speak")
                    speak("Only a few enemies left. Don't choke now—I'm watching.")
                    set_chat_status(None)
                    few_enemy_speaked = True

            if stage == 'game_over' and gameover_speaked is False:
                set_chat_status("speak")
                speak("Aha! You dead now!")
                set_chat_status(None)
                gameover_speaked = True

        except Exception as e:
            print(f"[Trigger] error during periodic task: {e}")

        time.sleep(interval)

if __name__ == "__main__":
    trigger_thread = threading.Thread(target=trigger_loop, args=(3.0,), daemon=True)
    trigger_thread.start()
    main()