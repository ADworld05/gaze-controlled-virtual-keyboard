from dataclasses import asdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .settings import Settings


SETTINGS_STYLE = '''
QDialog { background: #f3f6fb; color: #192c43; }
QLabel#settingsTitle { color: #182d40; font-size: 22px; font-weight: 750; }
QLabel#settingsHint { color: #625b50; background: #f9f4e8; border: 1px solid #dfceb0;
    border-radius: 3px; padding: 7px 10px; }
QWidget#section { background: #fffdf8; border: 1px solid #ded6c8; border-radius: 4px; }
QWidget#section QLabel { color: #35475a; }
QTabWidget::pane { background: transparent; border: 0; }
QTabBar::tab { background: #e8e2d5; color: #35475a; border: 1px solid #d2c8b8;
    padding: 7px 13px; margin-right: 4px; }
QTabBar::tab:selected { background: #fffdf8; color: #8f452d; border-bottom-color: #fffdf8; }
QComboBox, QSpinBox, QDoubleSpinBox { background: #fbf8f0; color: #203448;
    border: 1px solid #c7c0b2; border-radius: 3px; padding: 4px 7px; min-width: 90px; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #bd7b46; }
QCheckBox { spacing: 9px; color: #35475a; padding: 3px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { background: #fbf8f0; border: 1px solid #aaa394; border-radius: 3px; }
QCheckBox::indicator:checked { background: #d98745; border: 1px solid #8f452d; border-radius: 3px; }
QPushButton { background: #fffdf8; color: #23384a; border: 1px solid #c7c0b2;
    border-bottom: 3px solid #a8a293; border-radius: 4px; padding: 8px 13px; }
QPushButton:hover { background: #f8edda; border-color: #bd7b46; }
QPushButton:pressed { border-bottom-width: 1px; padding-top: 9px; }
QPushButton#restore { color: #87502f; }
QLabel#error { color: #8f3427; font-weight: 650; }
'''


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle('Instrument settings')
        self.setMinimumWidth(520)
        self.resize(560, 560)
        self.setStyleSheet(SETTINGS_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        title = QLabel('Tune your instrument')
        title.setObjectName('settingsTitle')
        layout.addWidget(title)
        hint = QLabel(
            'Higher sensitivity needs less eye movement. Changing the camera clears calibration; '
            'recalibrate after moving your seat. Typing pauses while these controls are open.'
        )
        hint.setObjectName('settingsHint')
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.fields = {}
        definitions = {
            'camera': ('Camera device index', 0, 20, 1),
            'sensitivity': ('Navigation sensitivity', .5, 2, .1),
            'initial_repeat': ('Hold before repeating (seconds)', .3, 2, .05),
            'repeat_interval': ('Time between repeat moves (seconds)', .15, 1.5, .05),
            'blink_ratio': ('Blink sensitivity (higher = easier)', .3, .75, .05),
            'blink_min': ('Shortest blink (seconds)', .04, .3, .01),
            'blink_max': ('Longest blink (seconds)', .3, 1, .05),
            'double_interval': ('Gap between two blinks (seconds)', .25, 1.5, .05),
            'cooldown': ('Rest after selection (seconds)', .3, 2, .05),
            'dwell_duration': ('Dwell time (seconds)', .6, 5, .1),
            'volume': ('Sound volume (0 to 1)', 0, 1, .05),
        }

        tabs = QTabWidget()
        layout.addWidget(tabs)
        for title, rows in (
            ('01  Navigation', ('camera', 'sensitivity', 'initial_repeat', 'repeat_interval')),
            ('02  Selection', ('mode', 'blink_ratio', 'blink_min', 'blink_max', 'double_interval', 'cooldown', 'dwell_duration')),
            ('03  Feedback', ('volume', 'sound', 'navigation_sound', 'speech', 'preview')),
        ):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 8, 0, 0)
            page_layout.setSpacing(0)
            self._add_section(page_layout, rows, definitions)
            page_layout.addStretch()
            tabs.addTab(page, title)

        self.error = QLabel('')
        self.error.setObjectName('error')
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

        footer = QHBoxLayout()
        defaults = QPushButton('Restore defaults')
        defaults.setObjectName('restore')
        defaults.clicked.connect(lambda: self.populate(Settings()))
        footer.addWidget(defaults)
        footer.addStretch()
        actions = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        actions.button(QDialogButtonBox.StandardButton.Save).setText('Save settings')
        actions.button(QDialogButtonBox.StandardButton.Cancel).setText('Return')
        actions.accepted.connect(self.save)
        actions.rejected.connect(self.reject)
        footer.addWidget(actions)
        layout.addLayout(footer)

        self.populate(settings)

    def _add_section(self, parent_layout, rows, definitions):
        section = QWidget()
        section.setObjectName('section')
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(11, 8, 11, 9)
        section_layout.setSpacing(5)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        section_layout.addLayout(form)

        for row in rows:
            if row == 'mode':
                field = QComboBox()
                for label, value in [
                    ('Double blink (default)', 'double'),
                    ('Single blink', 'single'),
                    ('Dwell', 'dwell'),
                ]:
                    field.addItem(label, value)
                self.fields['mode'] = field
                form.addRow('Select a key with', field)
            elif row in ('sound', 'navigation_sound', 'speech', 'preview'):
                labels = {
                    'sound': 'Sound enabled',
                    'navigation_sound': 'Tone on navigation',
                    'speech': 'Speak selected keys from local audio',
                    'preview': 'Show camera preview',
                }
                field = QCheckBox(labels[row])
                self.fields[row] = field
                form.addRow(field)
            else:
                label, low, high, step = definitions[row]
                field = QSpinBox() if row == 'camera' else QDoubleSpinBox()
                field.setRange(low, high)
                field.setSingleStep(step)
                self.fields[row] = field
                form.addRow(label, field)
        parent_layout.addWidget(section)

    def populate(self, settings):
        for name, value in asdict(settings).items():
            field = self.fields[name]
            if isinstance(field, QCheckBox):
                field.setChecked(value)
            elif isinstance(field, QComboBox):
                field.setCurrentIndex(field.findData(value))
            else:
                field.setValue(value)

    def save(self):
        values = {}
        for name, field in self.fields.items():
            values[name] = (
                field.isChecked() if isinstance(field, QCheckBox)
                else field.currentData() if isinstance(field, QComboBox)
                else field.value()
            )
        try:
            self.result_settings = Settings(**values).validate()
            self.accept()
        except ValueError as error:
            self.error.setText(str(error))
