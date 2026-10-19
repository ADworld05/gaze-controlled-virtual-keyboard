from dataclasses import replace
import time
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence, QFontDatabase
from PySide6.QtWidgets import (QMainWindow, QWidget, QApplication, QVBoxLayout,
                              QHBoxLayout, QLabel, QPushButton, QTextEdit,
                              QProgressBar, QComboBox, QCheckBox, QSizePolicy)
from .settings import Settings
from .settings_ui import SettingsDialog
from .keyboard import Keyboard
from .calibration import Profile, STEPS, build_profile, demo_profile
from .control import GazeNavigator, BlinkDetector, DwellDetector
from .tracking import Measurement
from .camera import CameraWorker
from .sound import Feedback

STYLE = '''
QWidget { background: #f3f6fb; color: #192c43; font-family: 'Segoe UI'; font-size: 14px; }
QLabel#status { background: #20374a; color: #fff8e8; border-radius: 4px; padding: 6px 10px; font: 700 10px 'Consolas'; }
QLabel#instruction { background: #f9f4e8; color: #46382d; border: 1px solid #dfceb0; border-radius: 3px; padding: 6px 10px; font-size: 12px; }
QTextEdit { background: #fffdf8; border: 1px solid #c9c1b1; border-radius: 4px; padding: 14px; font: 24px 'Segoe UI'; selection-background-color: #f4c681; }
QLabel#cameraPreview { background: #e8e2d5; color: #625b50; border: 1px solid #c9c1b1; border-radius: 4px; }
QPushButton { background: #fffdf8; color: #23384a; border: 1px solid #c7c0b2; border-bottom: 3px solid #a8a293; border-radius: 4px; padding: 8px 13px; }
QPushButton:hover { background: #f8edda; border-color: #bd7b46; }
QPushButton:pressed { border-bottom-width: 1px; padding-top: 9px; }
QPushButton:focus { border: 2px dashed #c0703a; }
QPushButton[key="true"] { background: #fffdf7; border: 1px solid #d2c7b3; border-bottom: 4px solid #b7ad9b; border-radius: 5px; font: 650 20px 'Segoe UI'; padding: 5px; }
QPushButton[gaze="true"] { background: #f1ba67; color: #30261e; border: 3px solid #8f452d; border-bottom: 6px solid #8f452d; border-radius: 5px; }
QPushButton[selected="true"] { background: #95c3ad; color: #122f2a; border: 3px solid #386a57; border-bottom: 6px solid #386a57; }
QProgressBar { background: #ddd7ca; border: 0; border-radius: 2px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { background: #d98745; border-radius: 2px; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #fffdf8; color: #203448; border: 1px solid #c7c0b2; border-radius: 3px; padding: 7px 8px; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #bd7b46; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { background: #fffdf8; border: 1px solid #aaa394; border-radius: 3px; }
QCheckBox::indicator:checked { background: #d98745; border: 1px solid #8f452d; border-radius: 3px; }
'''


class Window(QMainWindow):
    def __init__(self, simulate=False):
        super().__init__()
        # Offscreen / restricted Windows sessions may expose no system fonts to Qt.
        # Register existing OS fonts explicitly; no font assets are redistributed.
        if 'Segoe UI' not in QFontDatabase.families():
            from pathlib import Path
            import os
            font_root = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
            for filename in ('segoeui.ttf', 'segoeuib.ttf'):
                if (font_root / filename).exists():
                    QFontDatabase.addApplicationFont(str(font_root / filename))
        self.simulate = simulate
        self.s = Settings.load()
        self.profile = demo_profile() if simulate else Profile.load()
        self.keyboard = Keyboard()
        self.worker = None
        self.closing = False
        self.restart_requested = False
        self.settings_open = False
        self.calibrating = False
        self.cal_failed_at = None
        self.last_packet = None
        self.seen_face = False
        self.last_status = 'Looking for face'
        self.confirmed_key = None
        self.confirmed_until = 0
        self.last_nav_sound = -100
        self.setWindowTitle('Gaze Keyboard' + (' · Simulation' if simulate else ''))
        self.setMinimumSize(900, 700)
        self.resize(1120, 760)
        self.setStyleSheet(STYLE)
        main = QWidget()
        self.setCentralWidget(main)
        outer = QVBoxLayout(main)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)
        toolbar = QHBoxLayout()
        self.pause_button = QPushButton('Pause')
        self.pause_button.clicked.connect(self.toggle_pause)
        toolbar.addWidget(self.pause_button)
        calibrate = QPushButton('Calibrate / Retry')
        calibrate.clicked.connect(self.start_calibration)
        toolbar.addWidget(calibrate)
        self.cancel_cal = QPushButton('Cancel calibration')
        self.cancel_cal.clicked.connect(self.cancel_calibration)
        self.cancel_cal.hide()
        toolbar.addWidget(self.cancel_cal)
        reconnect = QPushButton('Reconnect camera')
        reconnect.clicked.connect(self.restart_camera)
        reconnect.setEnabled(not simulate)
        toolbar.addWidget(reconnect)
        settings = QPushButton('Settings')
        settings.clicked.connect(self.edit_settings)
        toolbar.addWidget(settings)
        toolbar.addStretch()
        self.preview_check = QCheckBox('Camera preview')
        self.preview_check.setChecked(self.s.preview)
        self.preview_check.setEnabled(not simulate)
        self.preview_check.toggled.connect(self.set_preview)
        toolbar.addWidget(self.preview_check)
        self.status = QLabel('Looking for face')
        self.status.setObjectName('status')
        self.status.setWordWrap(False)
        self.status.setMinimumWidth(170)
        self.status.setMaximumWidth(220)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar.addWidget(self.status)
        outer.addLayout(toolbar)
        self.instruction = QLabel('Calibrate first, then look around the keyboard to move the focus.')
        if self.profile is not None:
            self.instruction.setText('Look to move the focus. Use your selection gesture to press a key.')
        self.instruction.setObjectName('instruction')
        self.instruction.setWordWrap(True)
        outer.addWidget(self.instruction)
        text_row = QHBoxLayout()
        self.text = QTextEdit()
        self.text.setPlaceholderText('Your words appear here…')
        self.text.setMinimumHeight(130)
        self.text.setAccessibleName('Typed text')
        text_row.addWidget(self.text, 3)
        self.preview = QLabel('Camera preview')
        self.preview.setObjectName('cameraPreview')
        self.preview.setFixedSize(340, 220)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setVisible(self.s.preview and not simulate)
        text_row.addWidget(self.preview)
        outer.addLayout(text_row, 2)
        self.focus_label = QLabel('')
        self.focus_label.setStyleSheet("color:#725238;font:600 12px 'Consolas';padding-top:2px")
        outer.addWidget(self.focus_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)
        self.board = QWidget()
        self.board_layout = QVBoxLayout(self.board)
        self.board_layout.setContentsMargins(0, 0, 0, 0)
        self.board_layout.setSpacing(8)
        outer.addWidget(self.board, 3)
        self.confirmation = QLabel('Ready for your next word.')
        outer.addWidget(self.confirmation)
        if simulate:
            debug = QHBoxLayout()
            debug.addWidget(QLabel('SIMULATION · gaze:'))
            self.sim_gaze = QComboBox()
            self.sim_gaze.addItems(['neutral', 'left', 'right', 'up', 'down'])
            debug.addWidget(self.sim_gaze)
            self.sim_closed = QCheckBox('Eyes closed (or hold F8)')
            debug.addWidget(self.sim_closed)
            self.sim_lost = QCheckBox('Face lost')
            debug.addWidget(self.sim_lost)
            outer.addLayout(debug)
        self.shortcuts = []
        for key, action in [('Ctrl+Left', lambda: self.move('left')), ('Ctrl+Right', lambda: self.move('right')),
                            ('Ctrl+Up', lambda: self.move('up')), ('Ctrl+Down', lambda: self.move('down')),
                            ('Ctrl+Return', self.select), ('Ctrl+P', self.toggle_pause), ('Ctrl+R', self.start_calibration)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)
        QApplication.instance().installEventFilter(self)
        self.feedback = Feedback(self, self.s)
        self.rebuild_control()
        self.render_board()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(30)
        if not simulate:
            self.start_camera()

    def eventFilter(self, obj, event):
        if self.simulate and not self.settings_open and event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease) and event.key() == Qt.Key.Key_F8:
            if not event.isAutoRepeat():
                self.sim_closed.setChecked(event.type() == QEvent.Type.KeyPress)
            return True
        return super().eventFilter(obj, event)

    def save_settings(self):
        try:
            self.s.save()
        except OSError as error:
            self.confirmation.setText(f'Settings could not be saved: {error}')

    def rebuild_control(self):
        self.nav = GazeNavigator(self.s, self.profile or demo_profile())
        self.blink = BlinkDetector(self.s)
        self.dwell = DwellDetector(self.s.dwell_duration)

    def reset_gestures(self):
        self.nav.reset()
        self.blink.reset()
        self.dwell.reset()
        self.progress.setValue(0)

    def guard_dwell_layout(self):
        # A layout change is not intentional focus navigation. Leave and return
        # before dwelling on its default key (especially Resume and Calibrate).
        if self.s.mode == 'dwell':
            self.dwell.target = self.keyboard.target
            self.dwell.fired = True
            self.dwell.reset()

    def start_camera(self):
        if self.closing or self.simulate:
            return
        self.last_packet = None
        self.seen_face = False
        self.last_status = 'Looking for face'
        self.worker = CameraWorker(self.s.camera, self.s.preview, self)
        self.worker.available.connect(self.receive)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def restart_camera(self):
        self.reset_gestures()
        self.cancel_calibration()
        if self.worker and self.worker.isRunning():
            self.restart_requested = True
            self.worker.requestInterruption()
            self.last_status = 'Camera restarting…'
        else:
            self.start_camera()

    def worker_finished(self):
        if self.restart_requested and not self.closing:
            self.restart_requested = False
            self.worker.deleteLater()
            self.start_camera()
        elif self.closing:
            self.close()

    def receive(self):
        packet = self.worker.take()
        if packet is not None:
            self.process(packet.measurement, packet.captured_at, packet.status)
            if packet.image is not None and self.s.preview:
                self.preview.setPixmap(QPixmap.fromImage(packet.image).scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def set_preview(self, enabled):
        self.s.preview = enabled
        self.preview.setVisible(enabled and not self.simulate)
        if self.worker:
            self.worker.preview = enabled
        self.save_settings()

    def edit_settings(self):
        if self.calibrating:
            self.cancel_calibration()
        self.settings_open = True
        self.reset_gestures()
        dialog = SettingsDialog(replace(self.s), self)
        if dialog.exec():
            camera_changed = self.s.camera != dialog.result_settings.camera
            self.s = dialog.result_settings
            self.feedback.s = self.s
            self.feedback.stop()
            self.save_settings()
            self.preview_check.setChecked(self.s.preview)
            self.rebuild_control()
            if camera_changed and not self.simulate:
                self.profile = None
                self.rebuild_control()
                self.instruction.setText('Camera changed. Calibrate before eye typing.')
                # Do not reuse calibration from the previous camera on next launch.
                from .settings import DATA
                try:
                    (DATA / 'calibration.json').unlink(missing_ok=True)
                except OSError:
                    self.confirmation.setText('Old calibration could not be removed. Recalibrate before the next launch.')
                self.restart_camera()
        self.settings_open = False
        self.reset_gestures()
        self.paint_focus()

    def render_board(self):
        while self.board_layout.count():
            item = self.board_layout.takeAt(0)
            row_widget = item.widget()
            if row_widget:
                row_widget.hide()
                row_widget.deleteLater()
        self.buttons = []
        for r, row in enumerate(self.keyboard.rows):
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            buttons = []
            for c, key in enumerate(row):
                button = QPushButton(self.keyboard.label(key))
                button.setProperty('key', True)
                button.setMinimumHeight(54)
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                button.setAccessibleName(self.keyboard.label(key))
                button.clicked.connect(lambda checked=False, rr=r, cc=c: self.mouse_select(rr, cc))
                layout.addWidget(button, 1)
                buttons.append(button)
            self.buttons.append(buttons)
            self.board_layout.addWidget(widget, 1)
        self.board.setMinimumHeight(len(self.buttons) * 54 + max(0, len(self.buttons) - 1) * 8)
        self.paint_focus()

    def paint_focus(self):
        for r, row in enumerate(self.buttons):
            for c, button in enumerate(row):
                button.setProperty('gaze', (r, c) == (self.keyboard.row, self.keyboard.col))
                button.setProperty('selected', self.confirmed_key == self.keyboard.rows[r][c] and time.monotonic() < self.confirmed_until)
                button.style().unpolish(button)
                button.style().polish(button)
                button.update()
        mode = {'double': 'Double blink', 'single': 'Single blink', 'dwell': 'Dwell'}[self.s.mode]
        self.focus_label.setText(f'Focused: {self.keyboard.label(self.keyboard.target)}    ·    Selection: {mode}')

    def mouse_select(self, row, col):
        if self.calibrating or self.settings_open:
            return
        self.keyboard.row, self.keyboard.col = row, col
        self.reset_gestures()
        self.select()

    def move(self, direction, feedback=True):
        if self.calibrating or self.settings_open:
            return
        if self.keyboard.move(direction):
            self.blink.reset()
            self.dwell.update(self.keyboard.target, time.monotonic(), valid=False)
            self.progress.setValue(0)
            if feedback and time.monotonic() - self.last_nav_sound > .7:
                self.feedback.play('navigate')
                self.last_nav_sound = time.monotonic()
            self.paint_focus()

    def toggle_pause(self):
        if self.settings_open:
            return
        if self.calibrating:
            self.cancel_calibration()
        self.keyboard.paused = not self.keyboard.paused
        self.keyboard.confirm_clear = False
        self.keyboard.home()
        self.pause_button.setText('Resume' if self.keyboard.paused else 'Pause')
        self.reset_gestures()
        self.guard_dwell_layout()
        self.render_board()
        message = 'Paused. Look to highlight Resume or Calibrate, then use your selection gesture.'
        if self.s.mode == 'dwell':
            message = 'Paused. To resume, look to Calibrate, then back to Resume and dwell. This keeps a steady gaze from resuming automatically.'
        self.instruction.setText(message if self.keyboard.paused else 'Look to move. Use your selection gesture when the intended key is highlighted.')

    def select(self):
        if self.calibrating or self.settings_open:
            return
        key = self.keyboard.target
        self.confirmed_key, self.confirmed_until = key, time.monotonic() + .45
        self.confirmation.setText(f'Selected: {self.keyboard.label(key)}')
        self.feedback.play('select', key)
        if key in ('Pause', 'Resume'):
            self.toggle_pause()
        elif key == 'Calibrate':
            self.start_calibration()
        elif key == 'Case':
            self.keyboard.upper = not self.keyboard.upper
            self.render_board()
        elif key == '123 / ABC':
            self.keyboard.symbols = not self.keyboard.symbols
            self.render_board()
        elif key == 'Clear':
            self.keyboard.confirm_clear = True
            self.keyboard.home()  # Safe default is Cancel, gaze navigation reaches Confirm.
            self.reset_gestures()
            self.guard_dwell_layout()
            self.instruction.setText('Clear all text? Highlight Confirm Clear to erase, or Cancel Clear to keep it.')
            self.render_board()
        elif key in ('Confirm Clear', 'Cancel Clear'):
            if key == 'Confirm Clear':
                self.text.clear()
            self.keyboard.confirm_clear = False
            self.keyboard.home()
            self.reset_gestures()
            self.guard_dwell_layout()
            self.instruction.setText('Look to move. Use your selection gesture on the focused key.')
            self.render_board()
        elif key == 'Copy':
            QApplication.clipboard().setText(self.text.toPlainText())
            self.confirmation.setText('Copied all text to the clipboard.')
        elif key == 'Backspace':
            cursor = self.text.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            else:
                cursor.deletePreviousChar()
            self.text.setTextCursor(cursor)
        else:
            value = {'Space': ' ', 'New Line': '\n'}.get(key, self.keyboard.label(key))
            cursor = self.text.textCursor()
            cursor.insertText(value)
            self.text.setTextCursor(cursor)
            self.text.ensureCursorVisible()
        self.paint_focus()

    def start_calibration(self):
        if self.settings_open:
            return
        self.reset_gestures()
        self.calibrating = True
        self.board.hide()
        self.cal_failed_at = None
        self.cal_step = 0
        self.samples = {s: [] for s in STEPS}
        self.cal_started = time.monotonic()
        self.cancel_cal.show()
        self.confirmation.setText('Calibration advances automatically. No selection gesture is needed.')
        self.update_calibration(self.cal_started)

    def cancel_calibration(self):
        self.calibrating = False
        self.board.show()
        self.cal_failed_at = None
        self.cancel_cal.hide()
        self.reset_gestures()
        self.instruction.setText('Calibrate before eye typing.' if self.profile is None else 'Look to move. Use your selection gesture on the focused key.')

    def update_calibration(self, now):
        if self.cal_failed_at is not None:
            if self.profile is None and now - self.cal_failed_at >= 10:
                self.start_calibration()
            return
        step = STEPS[self.cal_step]
        elapsed = now - self.cal_started
        duration = 5 if step == 'blink' else 3
        if elapsed >= 2 + duration:
            if self.cal_step < len(STEPS) - 1:
                self.cal_step += 1
                self.cal_started = now
                return self.update_calibration(now)
            try:
                profile = build_profile(self.samples)
                self.profile = profile
                if not self.simulate:
                    try:
                        profile.save()
                    except OSError:
                        self.confirmation.setText('Calibration ready for this session; local saving was unavailable.')
                self.rebuild_control()
                self.cancel_calibration()
                self.guard_dwell_layout()
                self.confirmation.setText('Calibration complete. Recalibrate if your camera, seat, or lighting changes.')
            except ValueError as error:
                self.cal_failed_at = now
                self.instruction.setText(f'Calibration needs a retry: {error}\nUse Calibrate / Retry. With no prior profile, retry starts automatically in 10 seconds; Cancel stops it.')
            return
        prompts = {'neutral': 'Look straight ahead with eyes open. Keep your head still.',
                   'left': 'Look LEFT with your eyes; keep your head still.',
                   'right': 'Look RIGHT with your eyes; keep your head still.',
                   'up': 'Look UP with your eyes; keep your head still.',
                   'down': 'Look DOWN with your eyes; keep your head still.',
                   'blink': 'Look ahead and make several brief deliberate blinks. Reopen between each blink.'}
        stage = f'Get ready: {max(1, int(2 - elapsed + .99))} s' if elapsed < 2 else f'Sampling: {max(1, int(2 + duration - elapsed + .99))} s · {len(self.samples[step])} samples'
        self.instruction.setText(f'Calibration {self.cal_step + 1}/6 · {step.upper()}\n{prompts[step]}  {stage}')
        self.progress.setValue(int(min(1, max(0, (elapsed - 2) / duration)) * 1000))

    def process(self, m, t, status='Ready'):
        now = time.monotonic()
        self.last_packet = t
        self.last_status = status
        valid = m is not None and m.valid() and 0 <= now - t <= .35
        if not valid:
            self.reset_gestures()
            if status.startswith('Camera unavailable') and not self.calibrating:
                self.instruction.setText(status[:240])
            if status == 'Ready':
                self.last_status = 'Tracking lost'
            elif status == 'Looking for face' and self.seen_face:
                self.last_status = 'Tracking lost'
            return
        self.seen_face = True
        if self.settings_open:
            return
        if self.calibrating:
            if self.cal_failed_at is None:
                step = STEPS[self.cal_step]
                elapsed = now - self.cal_started
                if 2 <= elapsed <= 2 + (5 if step == 'blink' else 3):
                    self.samples[step].append(m)
            return
        if self.profile is None:
            return
        threshold = min(self.profile.open_baseline * .8,
                        max(self.profile.open_baseline * self.s.blink_ratio,
                            self.profile.closed_baseline * 1.2))
        # Require bilateral closure to select. Any partly closed eye suppresses movement.
        closed = max(m.left_open, m.right_open) < threshold
        eyes_open = min(m.left_open, m.right_open) > threshold * 1.12
        click = self.blink.update(closed, t, self.keyboard.target, valid=True) if self.s.mode != 'dwell' else False
        if click:
            self.select()
        if not eyes_open or self.blink.busy or click:
            self.nav.reset()
            self.dwell.reset()
            self.progress.setValue(0)
            return
        previous_direction = self.nav.direction
        direction = self.nav.update(m.gaze, t)
        if direction:
            self.move(direction, feedback=direction != previous_direction)
        if self.s.mode == 'dwell':
            if self.dwell.update(self.keyboard.target, t, valid=eyes_open):
                self.select()
            self.progress.setValue(int(self.dwell.progress * 1000))

    def tick(self):
        now = time.monotonic()
        if self.closing:
            return
        if self.simulate:
            direction = self.sim_gaze.currentText()
            point = {'neutral': [.5, 0], 'left': [.35, 0], 'right': [.65, 0], 'up': [.5, -.05], 'down': [.5, .05]}[direction]
            openness = .04 if self.sim_closed.isChecked() else .25
            m = None if self.sim_lost.isChecked() else Measurement(*point, openness, openness)
            self.process(m, now, 'Looking for face' if m is None else 'Ready')
        if self.last_packet is not None and now - self.last_packet > .4:
            self.reset_gestures()
            if not self.last_status.startswith('Camera unavailable'):
                self.last_status = 'Tracking lost'
        if self.calibrating:
            self.update_calibration(now)
        status = 'Camera unavailable' if self.last_status.startswith('Camera unavailable') else self.last_status
        if self.calibrating:
            status = 'Calibrating' if self.cal_failed_at is None else 'Calibration retry needed'
        elif self.keyboard.paused:
            status = 'Paused · eye controls active' if self.last_status == 'Ready' else f'Paused · {status}'
        elif status == 'Ready' and self.profile is None:
            status = 'Ready · calibration required'
        if self.simulate:
            status = 'SIMULATION · ' + status
        self.status.setText(status)
        if self.confirmed_key and now >= self.confirmed_until:
            self.confirmed_key = None
            self.paint_focus()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.timer.stop()
            self.feedback.stop()
            self.worker.requestInterruption()
            self.status.setText('Closing camera…')
            self.setEnabled(False)
            event.ignore()  # The finished signal closes again after release, no forced termination.
            return
        QApplication.instance().removeEventFilter(self)
        self.feedback.stop()
        event.accept()
