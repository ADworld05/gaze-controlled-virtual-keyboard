"""Worker startup/error/release tests with a fake capture and real local model."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import time
from unittest.mock import patch
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QCoreApplication
from app.camera import CameraWorker


class Capture:
    def __init__(self, opened=True, read_ok=True):
        self.opened, self.read_ok = opened, read_ok
        self.released = False

    def isOpened(self):
        return self.opened

    def set(self, *args):
        return True

    def read(self):
        if self.read_ok:
            return True, np.zeros((240, 320, 3), dtype=np.uint8)
        return False, None

    def release(self):
        self.released = True


def main():
    app = QCoreApplication([])
    for opened, read_ok in [(False, False), (True, False), (True, True)]:
        capture = Capture(opened, read_ok)
        packets = []
        worker = CameraWorker(0, preview=True)
        worker.available.connect(lambda: packets.append(worker.take()))
        with patch('app.camera.cv2.VideoCapture', return_value=capture):
            worker.start()
            deadline = time.monotonic() + 15
            while worker.isRunning() and time.monotonic() < deadline:
                app.processEvents()
                if opened and read_ok and packets:
                    worker.requestInterruption()
                worker.wait(10)
            assert not worker.isRunning(), 'Worker did not shut down'
            app.processEvents()
        assert capture.released, 'Camera must be released even on errors'
        assert packets
        if opened and read_ok:
            assert packets[-1].status == 'Looking for face' and packets[-1].measurement is None
            assert packets[-1].image is not None
        else:
            assert packets[-1].status.startswith('Camera unavailable')
    print('PASS: fake unavailable camera, repeated read failure, blank capture/no face, preview, interruption, webcam release and worker completion with real local model.')


if __name__ == '__main__':
    main()
