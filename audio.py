"""Word pronunciation via macOS built-in TTS."""
import subprocess
import threading

_lock = threading.Lock()
_proc: subprocess.Popen | None = None


def speak(text: str):
    global _proc
    with _lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()
        _proc = subprocess.Popen(["say", text])
