from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math
import os

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('LOCALAPPDATA', str(ROOT / '.local'))) / 'GazeKeyboardV2'


@dataclass
class Settings:
    camera: int = 0
    sensitivity: float = 1.0
    initial_repeat: float = 0.65
    repeat_interval: float = 0.35
    mode: str = 'double'
    blink_ratio: float = 0.55
    blink_min: float = 0.08
    blink_max: float = 0.5
    double_interval: float = 0.65
    cooldown: float = 0.8
    dwell_duration: float = 1.5
    sound: bool = True
    volume: float = 0.25
    navigation_sound: bool = False
    speech: bool = False
    preview: bool = False

    def validate(self):
        ranges = {'camera': (0, 20), 'sensitivity': (0.5, 2),
                  'initial_repeat': (0.3, 2), 'repeat_interval': (0.15, 1.5),
                  'blink_ratio': (0.3, 0.75), 'blink_min': (0.04, 0.3),
                  'blink_max': (0.3, 1), 'double_interval': (0.25, 1.5),
                  'cooldown': (0.3, 2), 'dwell_duration': (0.6, 5), 'volume': (0, 1)}
        for name, (lo, hi) in ranges.items():
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError(f'{name} must be between {lo} and {hi}')
        if not isinstance(self.camera, int):
            raise ValueError('Camera must be an integer')
        if self.mode not in ('double', 'single', 'dwell') or self.blink_min >= self.blink_max:
            raise ValueError('Invalid selection mode or blink duration bounds')
        for name in ('sound', 'navigation_sound', 'speech', 'preview'):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f'{name} must be on or off')
        return self

    @classmethod
    def load(cls, path=None):
        try:
            return cls(**json.loads((path or DATA / 'settings.json').read_text())).validate()
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self, path=None):
        self.validate()
        atomic_json(path or DATA / 'settings.json', asdict(self))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2), encoding='utf-8')
    tmp.replace(path)
