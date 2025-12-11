import os
import io
import time
import threading
from typing import Dict

import boto3
import pygame
from dotenv import load_dotenv
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError

#load_dotenv()

_tts_cache: Dict[str, bytes] = {}
_cache_lock = threading.Lock()
_pygame_inited = False


def _get_polly_client():
    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )
    return session.client("polly")


def _ensure_pygame_mixer():
    global _pygame_inited
    if not _pygame_inited:
        pygame.mixer.init()
        _pygame_inited = True


def _synthesize_with_retry(text: str, voice_id: str, max_retries: int = 3) -> bytes:
    delay = 0.5
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            polly = _get_polly_client()
            resp = polly.synthesize_speech(
                Text=text,
                VoiceId=voice_id,
                OutputFormat="mp3",
            )
            return resp["AudioStream"].read()
        except (BotoCoreError, ClientError, NoCredentialsError) as e:
            last_exc = e
            print(f"[Polly ERROR] attempt {attempt}/{max_retries}: {e}")
            time.sleep(delay)
            delay *= 2
    raise last_exc


def speak(text: str, voice_id: str = None):
    if not text:
        return

    voice_id = voice_id or os.getenv("POLLY_VOICE", "Joanna")
    print(f"[Polly] → {text}")

    with _cache_lock:
        audio_stream = _tts_cache.get(text)

    if audio_stream is None:
        try:
            audio_stream = _synthesize_with_retry(text, voice_id)
            with _cache_lock:
                _tts_cache[text] = audio_stream
        except Exception as e:
            print(f"[Polly FATAL] Failed to synthesize speech: {e}")

            fallback_msg = "Sorry, my voice is having trouble right now."

            print(f"[Polly] (fallback, no audio) → {fallback_msg}")
            return

    _ensure_pygame_mixer()
    pygame.mixer.music.load(io.BytesIO(audio_stream))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(10)
