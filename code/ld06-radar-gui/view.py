"""Geometry for a readable scan: measured contours, auto range, directions."""
import math
from scan import xy

RADII = (0.2, 0.3, 0.5, 1, 2, 3, 6, 8, 12)


def distance_text(meters):
    if meters is None:
        return "无回波"
    if meters < 1:
        return f"{meters * 100:.0f} cm"
    return f"{meters:.2f} m"


def fitted_radius(samples):
    """Fit the 95th percentile so a few remote returns do not shrink the scene."""
    distances = sorted(s.point.distance_mm / 1000 for s in samples)
    if not distances:
        return 1.0
    target = distances[min(len(distances) - 1, int((len(distances) - 1) * 0.95))] * 1.2
    return next((radius for radius in RADII if radius >= target), RADII[-1])


def connected(a, b, rotation=0):
    """Only connect close, angularly adjacent returns; never bridge a gap."""
    angular_gap = (b.point.angle_deg - a.point.angle_deg) % 360
    if angular_gap > 3:
        return False
    ax, ay = xy(a.point, rotation)
    bx, by = xy(b.point, rotation)
    spatial_gap = math.hypot(bx - ax, by - ay)
    threshold = max(0.035, min(a.point.distance_mm, b.point.distance_mm) / 1000 * 0.12)
    return spatial_gap <= threshold


def contours(samples, rotation=0):
    """Return separate runs, joining the 359°/0° seam when truly adjacent."""
    ordered = sorted(samples, key=lambda s: s.point.angle_deg)
    groups = []
    for sample in ordered:
        if groups and connected(groups[-1][-1], sample, rotation):
            groups[-1].append(sample)
        else:
            groups.append([sample])
    if len(groups) > 1 and connected(groups[-1][-1], groups[0][0], rotation):
        groups[0] = groups.pop() + groups[0]
    return groups


def directional_distances(samples, rotation=0):
    """Closest supported echo in each 60° sector; suppress singleton outliers."""
    supported = [sample for group in contours(samples, rotation) if len(group) >= 3 for sample in group]
    distances = {}
    for title, center in (("前方", 0), ("右侧", 90), ("后方", 180), ("左侧", 270)):
        sector = [s.point.distance_mm / 1000 for s in supported
                  if abs(((s.point.angle_deg + rotation - center + 180) % 360) - 180) <= 30]
        distances[title] = min(sector) if sector else None
    return distances
