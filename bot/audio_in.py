import sounddevice as sd
import numpy as np
import pygame
import time

try:
    import RPi.GPIO as GPIO
    _gpio_initialized = False
except:
    print('Warning: Not in the Respi Env!')

def record_utterance(seconds: float = 2.5, samplerate: int = 16000) -> bytes:
    """
    Record a short audio clip and return the 16-bit PCM (little-endian) bytes,
    to be used as the inputStream for Lex RecognizeUtterance.
    Usage:
    Press Enter to start recording, speak for 2.5 seconds, and the recording will stop automatically.
    """
    input(">>> Press ENTER to start speaking...")
    print(f"[REC] Recording {seconds:.1f}s at {samplerate} Hz, mono...")
    audio = sd.rec(
        int(seconds * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    print("[REC] Done.")
    # audio: shape (N, 1), int16 → bytes
    return audio.tobytes()

def init_pygame_for_keys():
    """
    Init the pygame keyborad.
    """
    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((320, 100))
        pygame.display.set_caption("Press and hold SPACE to talk")


def record_until_space_release(samplerate: int = 16000, max_seconds: float = 6.0) -> bytes:
    """
    Press and hold the Space key to start recording; release it to stop.
        - Audio format: 16 kHz, mono, 16-bit PCM (compatible with Lex RecognizeUtterance)
        - max_seconds: Safety limit to prevent the user from holding the key indefinitely; recording is automatically truncated when the limit is reached.
    Returns raw bytes, which can be directly used as the Lex inputStream.
    """
    init_pygame_for_keys()

    print(">>> Hold SPACE to talk, release SPACE to finish (Esc to cancel).")

    recording = []
    started = False
    stream = None

    def callback(indata, frames, time, status):
        # indata: shape (frames, channels)
        recording.append(indata.copy())

    clock = pygame.time.Clock()
    elapsed = 0.0

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    print("[REC] Cancelled by ESC.")
                    running = False
                    break

                if event.key == pygame.K_SPACE and not started:
                    print("[REC] Recording... (hold SPACE)")
                    stream = sd.InputStream(
                        samplerate=samplerate,
                        channels=1,
                        dtype="int16",
                        callback=callback,
                    )
                    stream.start()
                    started = True

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_SPACE and started:
                    print("[REC] SPACE released, stopping.")
                    running = False
                    break

        if started:
            elapsed += clock.get_time() / 1000.0
            if elapsed >= max_seconds:
                print(f"[REC] Max {max_seconds}s reached, stopping.")
                running = False

        clock.tick(60) 

    if stream is not None:
        stream.stop()
        stream.close()

    if not recording:
        print("[REC] No audio captured.")
        return b""

    audio_np = np.concatenate(recording, axis=0)  # (N, 1)
    print(f"[REC] Captured {audio_np.shape[0] / samplerate:.2f}s audio.")
    return audio_np.tobytes()

def init_gpio_for_button(pin: int):
    global _gpio_initialized
    if _gpio_initialized:
        return
    BUTTON_PIN = pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    _gpio_initialized = True
    print(f"[GPIO] Button on BCM pin {BUTTON_PIN}, pull-up enabled.")

def record_until_button_release(
    pin: int,
    samplerate: int = 16000,
    max_seconds: float = 6.0
) -> bytes:
    
    init_gpio_for_button(pin)

    print(f">>> Hold the physical button (BCM {pin}) to talk, release to send.")

    print("[REC] Waiting for button press...")
    try:
        while GPIO.input(pin) == GPIO.HIGH:
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("[REC] Interrupted before recording.")
        return b""

    print("[REC] Button pressed, start recording...")

    recording_chunks = []
    start_time = time.time()

    def callback(indata, frames, time_info, status):
        # indata: shape (frames, channels), dtype=int16
        recording_chunks.append(indata.copy())

    stream = sd.InputStream(
        samplerate=samplerate,
        channels=1,
        dtype="int16",
        callback=callback,
    )
    stream.start()

    try:
        while True:
            if GPIO.input(pin) == GPIO.HIGH:
                print("[REC] Button released, stopping.")
                break
            if time.time() - start_time >= max_seconds:
                print(f"[REC] Max {max_seconds}s reached, stopping.")
                break
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("[REC] Interrupted during recording.")

    stream.stop()
    stream.close()

    if not recording_chunks:
        print("[REC] No audio captured.")
        return b""

    audio_np = np.concatenate(recording_chunks, axis=0)  # (N, 1)
    duration = audio_np.shape[0] / samplerate
    print(f"[REC] Captured {duration:.2f}s audio.")
    return audio_np.tobytes()
