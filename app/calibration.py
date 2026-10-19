from dataclasses import dataclass, asdict
import json
import numpy as np
from .settings import DATA, atomic_json

STEPS = ('neutral', 'left', 'right', 'up', 'down', 'blink')


@dataclass
class Profile:
    neutral: list
    left: list
    right: list
    up: list
    down: list
    open_baseline: float
    closed_baseline: float

    def validate(self):
        points = np.asarray([self.neutral, self.left, self.right, self.up, self.down], dtype=float)
        if points.shape != (5, 2) or not np.isfinite(points).all():
            raise ValueError('Invalid calibration coordinates')
        h, v = (points[2] - points[1]) / 2, (points[4] - points[3]) / 2
        if np.linalg.norm(h) < .025 or np.linalg.norm(v) < .008:
            raise ValueError('Directional samples are too similar. Keep your head still and look further in each direction.')
        basis = np.column_stack([h, v])
        if np.linalg.cond(basis) > 12:
            raise ValueError('Horizontal and vertical samples overlap. Retry with distinct left/right and up/down looks.')
        coords = (np.linalg.inv(basis) @ (points[1:] - points[0]).T).T
        if not (coords[0, 0] < -.25 and coords[1, 0] > .25 and coords[2, 1] < -.25 and coords[3, 1] > .25):
            raise ValueError('Neutral must lie between the opposing directions. Retry the calibration.')
        if not (np.isfinite([self.open_baseline, self.closed_baseline]).all()
                and .06 < self.open_baseline < .7 and 0 <= self.closed_baseline < self.open_baseline * .65):
            raise ValueError('No clear blink baseline. Open your eyes for gaze steps, then make several brief deliberate blinks.')
        return self

    def coordinates(self, gaze):
        p = np.asarray([self.neutral, self.left, self.right, self.up, self.down])
        basis = np.column_stack([(p[2] - p[1]) / 2, (p[4] - p[3]) / 2])
        inv = np.linalg.inv(basis)
        value = inv @ (gaze - p[0])
        ends = (inv @ (p[1:] - p[0]).T).T
        value[0] /= abs(ends[1 if value[0] >= 0 else 0, 0])
        value[1] /= abs(ends[3 if value[1] >= 0 else 2, 1])
        return value

    def save(self):
        self.validate()
        atomic_json(DATA / 'calibration.json', asdict(self))

    @classmethod
    def load(cls):
        try:
            return cls(**json.loads((DATA / 'calibration.json').read_text())).validate()
        except (OSError, ValueError, TypeError, np.linalg.LinAlgError):
            return None


def build_profile(samples):
    medians = {}
    opens = []
    for step in STEPS:
        valid = [m for m in samples.get(step, []) if m is not None and m.valid()]
        if len(valid) < 20:
            raise ValueError(f'Not enough valid samples for {step}. Improve lighting, keep your face visible, then retry.')
        if step != 'blink':
            baseline = np.median([m.openness for m in valid])
            valid = [m for m in valid if min(m.left_open, m.right_open) > baseline * .75]
            if len(valid) < 20:
                raise ValueError(f'Keep eyes open during {step}. Retry this calibration.')
            data = np.asarray([m.gaze for m in valid])
            medians[step] = np.median(data, axis=0).tolist()
            if np.max(np.median(np.abs(data - medians[step]), axis=0)) > .035:
                raise ValueError(f'{step.capitalize()} samples were unstable. Hold a steady gaze and retry.')
            opens.extend(m.openness for m in valid)
        else:
            blink_values = [max(m.left_open, m.right_open) for m in valid]
    baseline = float(np.median(opens))
    closed = float(np.percentile(blink_values, 10))
    if sum(v < baseline * .65 for v in blink_values) < 5:
        raise ValueError('Too few closed-eye samples. Make several brief intentional blinks during the blink step.')
    return Profile(**medians, open_baseline=baseline, closed_baseline=closed).validate()


def demo_profile():
    return Profile([.5, 0], [.35, 0], [.65, 0], [.5, -.05], [.5, .05], .25, .04)
