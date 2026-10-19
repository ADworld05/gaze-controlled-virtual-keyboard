"""Offscreen UI integration and rendering. No camera or physical display required."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sys
import time
from unittest.mock import patch
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from app.ui import Window
from app.settings import Settings
from app.tracking import Measurement
from app.camera import CameraWorker, Packet
from app.calibration import demo_profile, STEPS
from app.settings_ui import SettingsDialog


def main():
    app = QApplication([])
    window = Window(simulate=True)
    window.timer.stop()
    window.s = Settings(sound=False)
    window.feedback.s = window.s
    window.rebuild_control()
    window.show()
    app.processEvents()
    clock = [time.monotonic()]
    m_open = Measurement(.5, 0, .25, .25)
    m_closed = Measurement(.5, 0, .04, .04)

    def inject(m, dt=.1):
        clock[0] += dt
        window.process(m, clock[0], 'Ready' if m else 'Looking for face')

    def double():
        inject(m_open)
        inject(m_closed)
        inject(m_open, .15)
        inject(m_closed, .15)
        inject(m_open, .15)

    def focus(key):
        for r, row in enumerate(window.keyboard.rows):
            if key in row:
                window.keyboard.row, window.keyboard.col = r, row.index(key)
                window.reset_gestures()
                return
        raise AssertionError(key)

    with patch('app.ui.time.monotonic', lambda: clock[0]):
        focus('q')
        double()
        assert window.text.toPlainText() == 'q'
        # Closure while directional gaze is held must not move focus.
        focus('a')
        before = (window.keyboard.row, window.keyboard.col)
        inject(Measurement(.65, 0, .04, .04))
        inject(Measurement(.65, 0, .04, .04))
        assert (window.keyboard.row, window.keyboard.col) == before
        inject(None)
        inject(m_open)
        inject(m_closed)
        inject(m_open, .15)
        assert window.text.toPlainText() == 'q'  # face loss clears first blink
        # Pending single blink followed by fallback focus change cannot select a different key.
        focus('a')
        inject(m_open)
        inject(m_closed)
        inject(m_open, .15)
        window.move('right')
        inject(m_closed)
        inject(m_open, .15)
        assert window.text.toPlainText() == 'q'
        focus('Pause')
        window.select()
        assert window.keyboard.rows == [['Resume', 'Calibrate']]
        clock[0] += 1
        double()
        assert not window.keyboard.paused
        focus('Case')
        window.select()
        focus('a')
        window.select()
        focus('Space')
        window.select()
        focus('New Line')
        window.select()
        assert window.text.toPlainText() == 'qA \n'
        focus('Backspace')
        window.select()
        assert window.text.toPlainText() == 'qA '
        focus('Copy')
        window.select()
        assert app.clipboard().text() == 'qA '
        focus('Clear')
        window.select()
        assert window.keyboard.target == 'Cancel Clear'
        window.select()
        assert window.text.toPlainText() == 'qA '
        focus('Clear')
        window.select()
        window.move('right')
        window.select()
        assert window.text.toPlainText() == ''
        # Stale packet must not begin movement or a blink.
        window.process(Measurement(.65, 0, .04, .04), clock[0] - 1)
        assert not window.blink.busy and window.nav.direction is None
        window.s.mode = 'dwell'
        window.s.dwell_duration = .6
        window.rebuild_control()
        focus('q')
        for _ in range(15):
            inject(m_open)
        assert window.text.toPlainText() == 'Q'
        inject(None)
        for _ in range(12):
            inject(m_open)
        assert window.text.toPlainText() == 'Q'
        window.move('right')
        for _ in range(10):
            inject(m_open)
        assert window.text.toPlainText() == 'QW'
        window.toggle_pause()
        for _ in range(12):
            inject(m_open)
        assert window.keyboard.paused  # A new Resume board is not an intentional dwell.
        window.move('right')
        window.move('left')
        for _ in range(10):
            inject(m_open)
        assert not window.keyboard.paused
        window.s.mode = 'double'
        window.rebuild_control()
        # Guided settling, sampling and step transitions under a synthetic clock.
        profile = demo_profile()
        window.start_calibration()
        for _ in range(900):
            if not window.calibrating or window.cal_failed_at is not None:
                break
            step = STEPS[window.cal_step]
            p = profile.neutral if step == 'blink' else getattr(profile, step)
            closed = step == 'blink' and int((clock[0] - window.cal_started) * 20) % 12 < 4
            opening = .04 if closed else .25
            inject(Measurement(*p, opening, opening), .05)
            window.update_calibration(clock[0])
        assert not window.calibrating and window.cal_failed_at is None
        window.text.clear()
    window.text.setPlainText('Hello, one look at a time.\nA local assistive typing prototype.')
    focus('q')
    window.confirmed_key = None
    window.paint_focus()
    window.instruction.setText('Look to move. Double blink to select the focused key.')
    window.tick()
    window.resize(1120, 860)
    app.processEvents()
    screenshot = ROOT / 'docs/ui_preview.png'
    assert window.grab().save(str(screenshot))
    window.resize(900, 800)
    app.processEvents()
    assert window.grab().save(str(ROOT / 'docs/ui_minimum.png'))
    for row in window.buttons:
        for button in row:
            assert button.width() >= 45 and button.height() >= 54
            assert window.board.rect().contains(button.mapTo(window.board, button.rect().bottomRight()))
    assert window.board.geometry().bottom() < window.confirmation.geometry().top()
    assert window.centralWidget().rect().contains(window.board.geometry().bottomRight())
    window.preview.setVisible(True)
    app.processEvents()
    assert window.board.geometry().bottom() < window.confirmation.geometry().top()
    assert window.grab().save(str(ROOT / 'docs/ui_with_preview.png'))
    window.preview.setVisible(False)
    window.start_calibration()
    window.preview.setVisible(True)
    window.tick()
    app.processEvents()
    assert window.grab().save(str(ROOT / 'docs/ui_calibration.png'))
    window.cancel_calibration()
    window.toggle_pause()
    window.tick()
    app.processEvents()
    assert window.grab().save(str(ROOT / 'docs/ui_paused.png'))
    window.toggle_pause()
    settings = SettingsDialog(window.s, window)
    settings.show()
    app.processEvents()
    assert settings.grab().save(str(ROOT / 'docs/ui_settings.png'))
    settings.close()
    # Mailbox coalesces 100 publications into one notification and keeps latest.
    worker = CameraWorker(20)
    notices = []
    worker.available.connect(lambda: notices.append(1))
    for i in range(100):
        worker.publish(Packet(i))
    assert len(notices) == 1 and worker.take().captured_at == 99
    worker.publish(Packet(100))
    assert len(notices) == 2
    window.close()
    app.processEvents()
    print('PASS: simulated blink/dwell typing, closure navigation suppression, tracking loss, target changes, hands-free resume, case/text actions, clear confirmation, timed guided calibration, stale results, minimum sizing, settings rendering and bounded mailbox.')
    print(f'UI screenshots: {screenshot.parent}')

    # Inspect decoding of all 38 local speech assets; never play them here.
    player = QMediaPlayer()
    output = QAudioOutput()
    player.setAudioOutput(output)
    checked = []
    for path in sorted((ROOT / 'assets/sounds/voice').glob('*.mp3')):
        player.setSource(QUrl.fromLocalFile(str(path)))
        deadline = time.monotonic() + 3
        while player.duration() == 0 and time.monotonic() < deadline and player.error() == QMediaPlayer.Error.NoError:
            app.processEvents()
        assert player.error() == QMediaPlayer.Error.NoError and player.duration() > 0, (path, player.errorString())
        checked.append((path.name, player.duration()))
        player.setSource(QUrl())
    assert len(checked) == 38
    print(f'PASS: 38 MP3 files decode, durations {min(v for _, v in checked)}–{max(v for _, v in checked)} ms (audibility requires manual check).')


if __name__ == '__main__':
    main()
