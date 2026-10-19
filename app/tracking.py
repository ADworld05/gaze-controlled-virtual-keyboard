"""Geometry only: no Qt or camera required. Subject left/right, unmirrored input."""
from dataclasses import dataclass
import numpy as np

# Verified against Google's eye / iris connection definitions (docs/model.md).
# Corners in image-x order, upper/lower lids, iris ring.
EYES = ((33, 133, 159, 145, (469, 470, 471, 472)),
        (362, 263, 386, 374, (474, 475, 476, 477)))
DEBUG_INDICES = tuple(sorted({i for a, b, t, d, ring in EYES for i in (a, b, t, d, *ring)}))


@dataclass(frozen=True)
class Measurement:
    x: float
    y: float
    left_open: float
    right_open: float

    @property
    def gaze(self):
        return np.array([self.x, self.y])

    @property
    def openness(self):
        return (self.left_open + self.right_open) / 2

    def valid(self):
        return bool(np.isfinite([self.x, self.y, self.left_open, self.right_open]).all()
                    and -0.5 <= self.x <= 1.5 and abs(self.y) < 1
                    and 0 <= self.left_open < 1 and 0 <= self.right_open < 1)


def normalize(landmarks, width=1, height=1):
    """Eye-local iris projections divided by corner distance; preserve aspect ratio.

    Vertical gaze uses eye WIDTH, avoiding unstable division by closing eyelids.
    Eye openness uses lid distance / width. Invalid geometry is rejected.
    """
    try:
        if width <= 0 or height <= 0 or len(landmarks) < 478:
            return None
        p = np.asarray(landmarks, dtype=float)[:, :2] * [width, height]
        if not np.isfinite(p).all():
            return None
        values = []
        for a, b, top, bottom, iris in EYES:
            axis = p[b] - p[a]
            span = np.linalg.norm(axis)
            if span < 1e-6:
                return None
            axis /= span
            if axis[0] < 0:
                axis = -axis
                a, b = b, a
            vertical = np.array([-axis[1], axis[0]])
            center = p[list(iris)].mean(axis=0)
            mid = (p[a] + p[b]) / 2
            values.append((np.dot(center - p[a], axis) / span,
                           np.dot(center - mid, vertical) / span,
                           np.linalg.norm(p[bottom] - p[top]) / span))
        m = Measurement(float(np.mean([v[0] for v in values])),
                        float(np.mean([v[1] for v in values])), values[1][2], values[0][2])
        return m if m.valid() else None
    except (ValueError, TypeError, IndexError):
        return None
