"""Single producer, coalesced latest-result mailbox: bounded Qt delivery."""
from dataclasses import dataclass
from threading import Lock
import time
import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage
from .settings import ROOT
from .tracking import normalize, DEBUG_INDICES


@dataclass
class Packet:
    captured_at: float
    measurement: object = None
    image: object = None
    status: str = 'Looking for face'


class CameraWorker(QThread):
    available = Signal()

    def __init__(self, camera, preview=False, parent=None):
        super().__init__(parent)
        self.camera, self.preview = camera, preview
        self.lock = Lock()
        self.latest = None
        self.notified = False

    def publish(self, packet):
        with self.lock:
            self.latest = packet
            notify = not self.notified
            self.notified = True
        if notify:
            self.available.emit()

    def take(self):
        with self.lock:
            packet, self.latest = self.latest, None
            self.notified = False
        return packet

    def run(self):
        cap = None
        try:
            import mediapipe as mp
            model = ROOT / 'assets/models/face_landmarker.task'
            if not model.exists():
                raise RuntimeError('Model missing. Run python tools/setup_assets.py first.')
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO, num_faces=1)
            with mp.tasks.vision.FaceLandmarker.create_from_options(options) as detector:
                if self.isInterruptionRequested():
                    return
                cap = cv2.VideoCapture(self.camera)
                if not cap.isOpened():
                    self.publish(Packet(time.monotonic(), status='Camera unavailable — choose another camera in Settings'))
                    return
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                timestamp = -1
                failures = 0
                while not self.isInterruptionRequested():
                    ok, frame = cap.read()
                    captured = time.monotonic()
                    if not ok or frame is None:
                        failures += 1
                        self.publish(Packet(captured, status='Camera unavailable — frame read failed'))
                        if failures >= 5:
                            return
                        self.msleep(100)
                        continue
                    failures = 0
                    # Inference always uses UNMIRRORED input. Only the preview is mirrored.
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    timestamp = max(timestamp + 1, int(captured * 1000))
                    result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
                    m = None
                    if result.face_landmarks:
                        lm = result.face_landmarks[0]
                        points = np.array([(p.x, p.y) for p in lm])
                        m = normalize(points, frame.shape[1], frame.shape[0])
                        if self.preview:
                            for i in DEBUG_INDICES:
                                cv2.circle(rgb, (int(lm[i].x * frame.shape[1]), int(lm[i].y * frame.shape[0])), 2, (30, 220, 140), -1)
                    image = None
                    if self.preview:
                        if m is not None:
                            # An eye crop makes the landmark debug view readable at keyboard size.
                            eye_points = points[list(DEBUG_INDICES)] * [rgb.shape[1], rgb.shape[0]]
                            low = np.maximum(eye_points.min(axis=0) - [35, 25], [0, 0]).astype(int)
                            high = np.minimum(eye_points.max(axis=0) + [35, 25], [rgb.shape[1], rgb.shape[0]]).astype(int)
                            if np.all(high > low):
                                rgb = rgb[low[1]:high[1], low[0]:high[0]]
                        rgb = cv2.flip(rgb, 1)
                        rgb = cv2.resize(rgb, (512, 256))
                        debug = f'iris {m.x:.2f}, {m.y:.2f} | open {m.openness:.2f}' if m else 'No valid eye landmarks'
                        cv2.putText(rgb, debug, (12, 25), cv2.FONT_HERSHEY_SIMPLEX, .65, (255, 255, 255), 1)
                        h, w, _ = rgb.shape
                        image = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()
                    self.publish(Packet(captured, m, image, 'Ready' if m else 'Looking for face'))
                    self.msleep(10)
        except Exception as error:
            self.publish(Packet(time.monotonic(), status=f'Camera unavailable — {error}'))
        finally:
            if cap is not None:
                cap.release()
