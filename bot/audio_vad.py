import time
from typing import Optional

import numpy as np
import sounddevice as sd


def record_one_utterance_vad(
    samplerate: int = 16000,
    block_size: int = 1024,
    energy_threshold: float = 50.0,
    min_speech_ms: int = 300,
    max_speech_ms: int = 6000,
    silence_ms: int = 600,
) -> bytes:
    min_speech_sec = min_speech_ms / 1000.0
    max_speech_sec = max_speech_ms / 1000.0
    silence_sec = silence_ms / 1000.0

    state = "idle"
    utterance_blocks = []
    speech_start_time: Optional[float] = None
    last_voice_time: Optional[float] = None

    print("[VAD] Listening for one utterance...")

    def callback(indata, frames, time_info, status):
        nonlocal state, utterance_blocks, speech_start_time, last_voice_time
        if status:
            print(f"[VAD] Input status: {status}")

        block = indata.copy()
        block_f32 = block.astype(np.float32)
        rms = float(np.sqrt(np.mean(block_f32 ** 2)))
        now = time.time()

        if state == "idle":
            if rms > energy_threshold:
                # start speaking
                state = "speaking"
                utterance_blocks = [block]
                speech_start_time = now
                last_voice_time = now
        else:
            utterance_blocks.append(block)
            if rms > energy_threshold:
                last_voice_time = now

    with sd.InputStream(
        samplerate=samplerate,
        channels=1,
        dtype="int16",
        blocksize=block_size,
        callback=callback,
    ):
        start = time.time()
        while True:
            now = time.time()
            if state == "idle":
                if now - start > 10.0:
                    break
            else:
                # speaking
                elapsed_speech = now - speech_start_time
                elapsed_silence = now - last_voice_time
                if elapsed_speech >= max_speech_sec:
                    print("[VAD] Max utterance length reached.")
                    break
                if elapsed_silence >= silence_sec and elapsed_speech >= min_speech_sec:
                    print("[VAD] Detected utterance end.")
                    break
            time.sleep(0.01)

    if not utterance_blocks:
        print("[VAD] No speech detected in this window.")
        return b""

    audio_np = np.concatenate(utterance_blocks, axis=0)
    duration = audio_np.shape[0] / samplerate
    print(f"[VAD] Captured {duration:.2f}s audio.")
    return audio_np.tobytes()
