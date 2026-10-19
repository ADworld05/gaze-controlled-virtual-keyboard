import unittest
from dataclasses import replace
import numpy as np
from app.settings import Settings
from app.tracking import normalize, Measurement
from app.calibration import demo_profile, build_profile
from app.control import GazeNavigator, BlinkDetector, DwellDetector
from app.keyboard import Keyboard


def stream(detector, events, target='a'):
    return [detector.update(closed, t, target) for t, closed in events]


def frames(start, end, step=.03):
    return np.arange(start, end + .001, step)


class GeometryTests(unittest.TestCase):
    def landmarks(self):
        p = np.zeros((478, 3))
        for a, b, top, bottom, ring in ((33, 133, 159, 145, range(469, 473)), (362, 263, 386, 374, range(474, 478))):
            p[a, :2] = [.2, .5]
            p[b, :2] = [.4, .5]
            p[top, :2] = [.3, .475]
            p[bottom, :2] = [.3, .525]
            p[list(ring), :2] = [.3, .51]
        return p

    def test_normalization(self):
        m = normalize(self.landmarks(), 100, 100)
        np.testing.assert_allclose([m.x, m.y, m.openness], [.5, .05, .25])

    def test_aspect_ratio(self):
        m = normalize(self.landmarks(), 200, 100)
        np.testing.assert_allclose([m.x, m.y, m.openness], [.5, .025, .125])

    def test_scale_translation_invariance(self):
        p = self.landmarks()
        np.testing.assert_allclose(normalize(p).gaze, normalize(p * 2 + .1).gaze)

    def test_invalid_geometry(self):
        self.assertIsNone(normalize(np.zeros((478, 3))))
        self.assertIsNone(normalize(np.zeros((10, 3))))
        p = self.landmarks()
        p[10, 0] = np.nan
        self.assertIsNone(normalize(p))
        self.assertIsNone(normalize(self.landmarks(), 0, 1))

    def test_closure_preserves_gaze_geometry(self):
        p = self.landmarks()
        p[[159, 145, 386, 374], 1] = .5
        m = normalize(p)
        self.assertEqual(m.openness, 0)
        self.assertAlmostEqual(m.y, .05)

    def test_rotated_eye(self):
        p = self.landmarks()
        theta = .3
        rotation = [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]]
        p[:, :2] = p[:, :2] @ np.array(rotation).T
        np.testing.assert_allclose(normalize(p).gaze, [.5, .05], atol=1e-6)


class CalibrationTests(unittest.TestCase):
    def samples(self):
        p = demo_profile()
        samples = {name: [Measurement(*getattr(p, name), .25, .25) for _ in range(35)] for name in ('neutral', 'left', 'right', 'up', 'down')}
        samples['blink'] = [Measurement(.5, 0, .04, .04) for _ in range(10)] + [Measurement(.5, 0, .25, .25) for _ in range(25)]
        return samples

    def test_valid_and_robust(self):
        data = self.samples()
        data['neutral'].append(Measurement(.9, .4, .25, .25))
        p = build_profile(data)
        np.testing.assert_allclose(p.neutral, [.5, 0])

    def test_insufficient(self):
        data = self.samples()
        data['left'] = data['left'][:3]
        with self.assertRaisesRegex(ValueError, 'Not enough'):
            build_profile(data)

    def test_similar_directions(self):
        p = demo_profile()
        p.left = p.right = [.5, 0]
        with self.assertRaisesRegex(ValueError, 'too similar'):
            p.validate()

    def test_bad_neutral(self):
        p = demo_profile()
        p.neutral = [.9, 0]
        with self.assertRaisesRegex(ValueError, 'Neutral'):
            p.validate()

    def test_no_closed_samples(self):
        data = self.samples()
        data['blink'] = data['neutral']
        with self.assertRaisesRegex(ValueError, 'closed-eye'):
            build_profile(data)

    def test_unstable_samples(self):
        data = self.samples()
        data['left'] = [Measurement(.1 if i % 2 else .6, 0, .25, .25) for i in range(40)]
        with self.assertRaisesRegex(ValueError, 'unstable'):
            build_profile(data)

    def test_mirror_and_opposing_mapping(self):
        p = demo_profile()
        for name, expected in [('left', [-1, 0]), ('right', [1, 0]), ('up', [0, -1]), ('down', [0, 1])]:
            np.testing.assert_allclose(p.coordinates(np.array(getattr(p, name))), expected)
        for name in ('neutral', 'left', 'right', 'up', 'down'):
            getattr(p, name)[0] = 1 - getattr(p, name)[0]
        p.validate()
        np.testing.assert_allclose(p.coordinates(np.array(p.left)), [-1, 0])

    def test_overlapping_axes(self):
        p = demo_profile()
        p.up, p.down = p.left, p.right
        with self.assertRaisesRegex(ValueError, 'overlap'):
            p.validate()


class NavigationTests(unittest.TestCase):
    def nav(self, **kwargs):
        return GazeNavigator(replace(Settings(), **kwargs), demo_profile())

    def test_dead_zone(self):
        nav = self.nav()
        self.assertTrue(all(nav.update([.53, .005], t) is None for t in frames(0, 1)))

    def test_initial_stability_and_repeat(self):
        nav = self.nav(initial_repeat=.6, repeat_interval=.3)
        times = [t for t in frames(0, 1.1) if nav.update([.65, 0], t)]
        self.assertEqual(len(times), 3)
        self.assertGreaterEqual(times[0], .12)
        self.assertGreaterEqual(times[1] - times[0], .6 - 1e-9)
        self.assertGreaterEqual(times[2] - times[1], .3 - 1e-9)

    def test_short_noise_rejected(self):
        nav = self.nav()
        self.assertIsNone(nav.update([.65, 0], 0))
        self.assertIsNone(nav.update([.5, 0], .04))
        self.assertIsNone(nav.update([.5, 0], .08))

    def test_hysteresis(self):
        nav = self.nav()
        for t in frames(0, .3):
            nav.update([.65, 0], t)
        for t in frames(.33, .5):
            nav.update([.59, 0], t)
        self.assertEqual(nav.direction, 'right')

    def test_sensitivity_order(self):
        high, low = self.nav(sensitivity=2), self.nav(sensitivity=.5)
        high_moves, low_moves = [], []
        for t in frames(0, .5):
            high_moves.append(high.update([.575, 0], t))
            low_moves.append(low.update([.575, 0], t))
        self.assertIn('right', high_moves)
        self.assertNotIn('right', low_moves)

    def test_invalid_and_stale(self):
        nav = self.nav()
        nav.update([.65, 0], 0)
        self.assertIsNone(nav.update([.65, 0], 1))
        self.assertIsNone(nav.update([np.nan, 0], 1.1))
        self.assertIsNone(nav.direction)

    def test_all_directions(self):
        p = demo_profile()
        for direction in ('left', 'right', 'up', 'down'):
            nav = self.nav()
            result = [nav.update(getattr(p, direction), t) for t in frames(0, .3)]
            self.assertIn(direction, result)


class BlinkTests(unittest.TestCase):
    def detector(self, **kwargs):
        return BlinkDetector(replace(Settings(), **kwargs))

    def test_complete_single(self):
        d = self.detector(mode='single')
        self.assertEqual(stream(d, [(0, False), (.1, True), (.2, True), (.3, False)]), [False, False, False, True])
        self.assertFalse(d.update(False, .4, 'a'))

    def test_complete_double(self):
        d = self.detector()
        self.assertEqual(sum(stream(d, [(0, False), (.1, True), (.25, False), (.4, True), (.55, False)])), 1)

    def test_normal_single_in_double_mode(self):
        d = self.detector()
        result = stream(d, [(0, False), (.1, True), (.2, False), (.5, False), (.8, False), (1, False)])
        self.assertFalse(any(result))
        self.assertFalse(d.busy)

    def test_prolonged_closure(self):
        d = self.detector(mode='single')
        events = [(0, False)] + [(t, True) for t in frames(.1, 2)] + [(2.2, False)]
        self.assertFalse(any(stream(d, events)))

    def test_reopening_required(self):
        d = self.detector()
        self.assertFalse(any(stream(d, [(0, False), (.1, True), (.2, True), (.3, True), (.4, False)])))

    def test_cooldown(self):
        d = self.detector(mode='single')
        result = stream(d, [(0, False), (.1, True), (.2, False), (.3, True), (.4, False), (.7, False), (1, False), (1.1, True), (1.2, False)])
        self.assertEqual(sum(result), 2)

    def test_tracking_loss(self):
        d = self.detector()
        stream(d, [(0, False), (.1, True), (.2, False)])
        d.update(False, .3, 'a', valid=False)
        self.assertFalse(any(stream(d, [(.4, False), (.5, True), (.65, False)])))

    def test_highlight_change(self):
        d = self.detector()
        stream(d, [(0, False), (.1, True), (.2, False)])
        self.assertFalse(d.update(False, .3, 'b'))
        self.assertFalse(any(stream(d, [(.4, True), (.55, False)], target='b')))

    def test_starts_closed(self):
        d = self.detector(mode='single')
        self.assertFalse(any(stream(d, [(0, True), (.1, True), (.2, False)])))

    def test_too_short(self):
        d = self.detector(mode='single')
        self.assertFalse(any(stream(d, [(0, False), (.1, True), (.12, False)])))

    def test_interval_expired(self):
        d = self.detector()
        events = [(0, False), (.1, True), (.2, False), (.5, False), (.8, False), (1.0, True), (1.2, False)]
        self.assertFalse(any(stream(d, events)))

    def test_pause_reset_and_cooldown_preserved(self):
        d = self.detector(mode='single')
        stream(d, [(0, False), (.1, True), (.2, False)])
        d.reset()
        self.assertFalse(any(stream(d, [(.3, False), (.4, True), (.5, False)])))

    def test_gap_and_nonmonotonic(self):
        d = self.detector(mode='single')
        self.assertFalse(any(stream(d, [(0, False), (.1, True), (1, False)])))
        self.assertFalse(d.update(False, .9, 'a'))


class DwellTests(unittest.TestCase):
    def test_once_per_uninterrupted_target(self):
        d = DwellDetector(.6)
        clicks = [d.update('a', t) for t in frames(0, 2)]
        self.assertEqual(sum(clicks), 1)

    def test_target_rearms(self):
        d = DwellDetector(.6)
        for t in frames(0, .9):
            d.update('a', t)
        d.update('b', .93)
        self.assertEqual(sum(d.update('a', t) for t in frames(.96, 1.8)), 1)

    def test_invalid_resets_progress(self):
        d = DwellDetector(.6)
        for t in frames(0, .45):
            d.update('a', t)
        d.update('a', .48, valid=False)
        self.assertEqual(d.progress, 0)
        self.assertFalse(any(d.update('a', t) for t in frames(.51, .9)))

    def test_pause_or_closure_does_not_rearm_same_key(self):
        d = DwellDetector(.6)
        for t in frames(0, .9):
            d.update('a', t)
        d.reset()
        self.assertFalse(any(d.update('a', t) for t in frames(.93, 2)))


class KeyboardTests(unittest.TestCase):
    def test_boundaries(self):
        k = Keyboard()
        k.home()
        self.assertFalse(k.move('left'))
        self.assertFalse(k.move('up'))
        for _ in range(20):
            k.move('right')
        self.assertEqual(k.col, 9)
        k.move('down')
        self.assertEqual(k.col, 8)
        k.move('down')
        self.assertEqual(k.col, 6)

    def test_all_keys_reachable(self):
        for symbols in (False, True):
            k = Keyboard()
            k.symbols = symbols
            seen, queue = set(), [(0, 0)]
            while queue:
                rc = queue.pop()
                if rc in seen:
                    continue
                seen.add(rc)
                for direction in ('left', 'right', 'up', 'down'):
                    k.row, k.col = rc
                    k.move(direction)
                    queue.append((k.row, k.col))
            self.assertEqual(len(seen), sum(map(len, k.rows)))

    def test_paused_and_confirmation_reachable(self):
        k = Keyboard()
        k.paused = True
        k.home()
        self.assertEqual(k.target, 'Resume')
        k.move('right')
        self.assertEqual(k.target, 'Calibrate')
        k.paused, k.confirm_clear = False, True
        k.home()
        self.assertEqual(k.target, 'Cancel Clear')
        k.move('right')
        self.assertEqual(k.target, 'Confirm Clear')


class SettingsTests(unittest.TestCase):
    def test_defaults(self):
        self.assertIsInstance(Settings().validate(), Settings)

    def test_invalid_ranges(self):
        for values in ({'sensitivity': 0}, {'camera': -1}, {'camera': .5}, {'volume': np.nan}, {'mode': 'wink'}, {'blink_min': .3, 'blink_max': .3}, {'sound': 1}, {'cooldown': True}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(Settings(), **values).validate()

    def test_save_roundtrip_and_corrupt_fallback(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'settings.json'
            replace(Settings(), sensitivity=1.5).save(path)
            self.assertEqual(Settings.load(path).sensitivity, 1.5)
            path.write_text('broken')
            self.assertEqual(Settings.load(path), Settings())


if __name__ == '__main__':
    unittest.main()
