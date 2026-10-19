"""Local blank-frame inference and pinned package imports, no camera/network."""
from pathlib import Path
import sys
import hashlib
import cv2
import mediapipe as mp
import numpy as np
import PySide6

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.tracking import normalize


def main():
    model = ROOT / 'assets/models/face_landmarker.task'
    expected = (model.parent / 'SHA256.txt').read_text().split()[0]
    assert hashlib.sha256(model.read_bytes()).hexdigest() == expected
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1)
    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
        rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        for timestamp in (0, 33, 66):
            result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
            assert not result.face_landmarks
    print(f'PASS: local model load / blank VIDEO inference / no-face handling; Python {sys.version.split()[0]}, OpenCV {cv2.__version__}, MediaPipe {mp.__version__}, NumPy {np.__version__}, PySide6 {PySide6.__version__}')


if __name__ == '__main__':
    main()
