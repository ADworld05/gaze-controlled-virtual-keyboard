"""One-time online model download; local, original tone generation."""
from pathlib import Path
import hashlib
import math
import struct
import urllib.request
import wave

ROOT = Path(__file__).resolve().parent.parent
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task'


def tones():
    folder = ROOT / 'assets/sounds'
    folder.mkdir(parents=True, exist_ok=True)
    for name, frequency, duration in [('select', 660, .085), ('navigate', 440, .035)]:
        destination = folder / f'{name}.wav'
        if destination.exists():
            continue
        rate = 44100
        count = int(rate * duration)
        samples = [int(6500 * math.sin(2 * math.pi * frequency * i / rate) * math.sin(math.pi * i / count) ** 2) for i in range(count)]
        with wave.open(str(destination), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(struct.pack(f'<{count}h', *samples))


def main():
    tones()
    path = ROOT / 'assets/models/face_landmarker.task'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix('.download')
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                tmp.write_bytes(response.read())
            if tmp.stat().st_size < 1000000:
                raise RuntimeError('Model download is unexpectedly small')
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (path.parent / 'SHA256.txt').write_text(f'{digest}  face_landmarker.task\n', encoding='utf-8')
    print(f'Model ready: {path}\nSHA256: {digest}\nLocal tones ready. Startup does not use the network.')


if __name__ == '__main__':
    main()
