"""Deterministic timestamp-driven navigation and gestures, independent of Qt."""
import numpy as np


class GazeNavigator:
    def __init__(self, settings, profile):
        self.s, self.profile = settings, profile
        self.reset()

    def reset(self):
        self.filtered = None
        self.last_t = None
        self.direction = None
        self.candidate = None
        self.since = 0
        self.next_move = 0

    def update(self, gaze, t):
        if gaze is None or not np.isfinite(gaze).all() or (self.last_t is not None and (t <= self.last_t or t - self.last_t > .4)):
            self.reset()
            return None
        point = self.profile.coordinates(np.asarray(gaze))
        alpha = 1 if self.last_t is None else 1 - np.exp(-(t - self.last_t) / .10)
        self.filtered = point if self.filtered is None else self.filtered + alpha * (point - self.filtered)
        self.last_t = t
        x, y = self.filtered
        threshold = .6 / self.s.sensitivity
        scores = {'left': -x, 'right': x, 'up': -y, 'down': y}
        best = max(scores, key=scores.get)
        if self.direction and scores[self.direction] > threshold * .65 and scores[best] < scores[self.direction] + .25:
            best = self.direction
        elif scores[best] < threshold:
            best = None
        if best != self.candidate:
            self.candidate, self.since = best, t
        if best != self.direction:
            if best is None:
                self.direction = None
                return None
            if t - self.since < .12:
                return None
            self.direction = best
            self.next_move = t + self.s.initial_repeat
            return best
        if best and t >= self.next_move:
            self.next_move = t + self.s.repeat_interval
            return best
        return None


class BlinkDetector:
    def __init__(self, settings):
        self.s = settings
        self.last_click = -float('inf')
        self.reset()

    def reset(self):
        self.armed = False
        self.closed_at = None
        self.pending = None
        self.target = None
        self.last_t = None

    @property
    def busy(self):
        return self.closed_at is not None or self.pending is not None

    def update(self, closed, t, target, valid=True):
        if not valid or (self.last_t is not None and (t <= self.last_t or t - self.last_t > .4)):
            self.reset()
            return False
        self.last_t = t
        if self.target is not None and target != self.target:
            self.reset()
            self.last_t = t
        if self.pending is not None and self.closed_at is None and t - self.pending > self.s.double_interval:
            self.pending = None
            self.target = None
        if closed:
            if self.armed and self.closed_at is None:
                self.closed_at = t
                self.target = target
            if self.closed_at is not None and t - self.closed_at > self.s.blink_max:
                # Long rest closure cannot turn into repeated clicks.
                self.pending = None
                self.armed = False
            return False
        self.armed = True
        if self.closed_at is None:
            return False
        start, self.closed_at = self.closed_at, None
        duration = t - start
        if not self.s.blink_min <= duration <= self.s.blink_max:
            self.pending = None
            self.target = None
            return False
        if t - self.last_click < self.s.cooldown:
            self.pending = None
            self.target = None
            return False
        click = self.s.mode == 'single'
        if self.s.mode == 'double':
            click = self.pending is not None and 0 < start - self.pending <= self.s.double_interval
            if not click:
                self.pending = t
                return False
        if click:
            self.last_click = t
            self.pending = None
            self.target = None
            return True
        return False


class DwellDetector:
    def __init__(self, duration):
        self.duration = duration
        self.target = None
        self.start = None
        self.fired = False
        self.last_t = None
        self.progress = 0

    def reset(self):
        # Same-key latch survives tracking loss / closure / pause.
        self.start = None
        self.last_t = None
        self.progress = 0

    def update(self, target, t, valid=True):
        if target != self.target:
            self.target, self.fired, self.start = target, False, None
        if not valid or (self.last_t is not None and (t <= self.last_t or t - self.last_t > .4)):
            self.reset()
            return False
        self.last_t = t
        if self.fired:
            self.progress = 0
            return False
        if self.start is None:
            self.start = t
        self.progress = min(1, (t - self.start) / self.duration)
        if self.progress >= 1:
            self.fired = True
            return True
        return False
