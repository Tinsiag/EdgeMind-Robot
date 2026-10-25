"""Encoder position outer loop; FPGA retains each wheel's speed PI inner loop.

All distances are wheel travel, not externally measured vehicle displacement.
Deceleration values are initial tuning values, not measured stopping guarantees.
"""
import math


def signed_delta(current, start):
    return (current - start + 2**31) % 2**32 - 2**31


class SynchronizedMove:
    TOLERANCE_MM = 5.0
    SYNC_GAIN = 1.0  # mm/s correction per mm of normalized progress mismatch
    SYNC_DAMPING = 0.2  # reduce correction as the lagging side catches up
    MAX_CORRECTION_RATIO = 0.20
    CORRECTION_SLEW = 80.0  # mm/s change per second, independently of base decel
    DECEL_MM_S2 = 250.0
    COAST_DECEL_MM_S2 = 800.0
    LATENCY_S = 0.06
    SETTLE_SECONDS = 0.15
    SETTLE_TIMEOUT = 3.0

    def __init__(self, targets, origins, max_speed):
        self.targets = targets
        self.origins = origins
        self.signs = tuple(1 if n >= 0 else -1 for n in targets)
        self.mm_per_count = tuple(math.pi * 66.3 / c for c in (1469, 1471))
        self.lengths = tuple(abs(n) * scale for n, scale in zip(targets, self.mm_per_count))
        if min(self.lengths) <= 0:
            raise ValueError('Synchronized move requires two nonzero wheel targets')
        self.max_speed = max_speed
        self.phase = 'run'
        self.settle_started = None
        self.stable_since = None
        self.previous_counts = None
        self.errors_mm = None
        self.correction = 0.0
        self.last_update = None

    def step(self, status, now):
        """Return signed body-frame wheel speeds, or None after settled arrival."""
        counts = (status.left_count, status.right_count)
        speeds = (status.left_speed, status.right_speed)
        progress = tuple(signed_delta(c, o) * sign * scale
                         for c, o, sign, scale in zip(counts, self.origins, self.signs, self.mm_per_count))
        if min(progress) < -3.0:
            raise RuntimeError('编码器方向与运动目标相反，请检查驱动与反馈极性')
        remaining = tuple(goal - p for goal, p in zip(self.lengths, progress))
        self.errors_mm = remaining
        if self.phase == 'settle':
            quiet_counts = self.previous_counts is not None and all(
                abs(signed_delta(c, p)) <= 2 for c, p in zip(counts, self.previous_counts))
            if max(abs(v) for v in speeds) < 20 and quiet_counts:
                if self.stable_since is None:
                    self.stable_since = now
            else:
                self.stable_since = None
            self.previous_counts = counts
            if self.stable_since is not None and now - self.stable_since >= self.SETTLE_SECONDS:
                if max(abs(e) for e in remaining) <= self.TOLERANCE_MM:
                    self.phase = 'done'
                    return None
                # A real A723 run stopped 3.5/5.1 mm short. The old automatic
                # 40 mm/s one-wheel trim could not overcome static friction and
                # triggered the FPGA no-feedback fault. Never restart a settled
                # move automatically, and do not widen the tolerance to hide it.
                raise RuntimeError(f'已停止，行程误差超出±5mm：左{remaining[0]:.1f}/右{remaining[1]:.1f}mm；未自动补进，请标定减速参数')
            elif now - self.settle_started >= self.SETTLE_TIMEOUT:
                raise RuntimeError('撤输出后未确认两轮低速稳定，请检查车轮/编码器')
            else:
                return (0, 0)

        # Slow both wheels from the same leading-wheel distance. Add a bounded
        # correction based on NORMALIZED travel so different CPRs do not bias it.
        braking = tuple(2.0 + abs(v) * self.LATENCY_S + v*v / (2*self.COAST_DECEL_MM_S2)
                        for v in speeds)
        if all(e <= b for e, b in zip(remaining, braking)):
            self.phase = 'settle'
            self.settle_started = now
            self.previous_counts = counts
            return (0, 0)
        limit = self.max_speed
        common = min(limit, max(40, math.sqrt(2*self.DECEL_MM_S2 * max(0, min(remaining)))))
        mean_length = sum(self.lengths) / 2
        gap = (progress[0]/self.lengths[0] - progress[1]/self.lengths[1]) * mean_length
        progress_speeds = tuple(v * sign for v, sign in zip(speeds, self.signs))
        desired = gap*self.SYNC_GAIN + (progress_speeds[0]-progress_speeds[1])*self.SYNC_DAMPING
        cap = common*self.MAX_CORRECTION_RATIO
        desired = max(-cap, min(cap, desired))
        dt = 0.04 if self.last_update is None else max(0, min(0.1, now-self.last_update))
        self.last_update = now
        change = self.CORRECTION_SLEW*dt
        self.correction += max(-change, min(change, desired-self.correction))
        self.correction = max(-cap, min(cap, self.correction))
        # Only slow the leading side; do not over-speed the other wheel. Never
        # clear a moving wheel's PI merely because it leads by a few mm: the
        # ground test oscillated when the old 8mm gate repeatedly commanded zero.
        magnitudes = [max(40, common-max(0, self.correction)),
                      max(40, common-max(0, -self.correction))]
        for i in range(2):
            if remaining[i] <= 2.0:
                magnitudes[i] = 0
        return tuple(sign * round(v) for sign, v in zip(self.signs, magnitudes))
