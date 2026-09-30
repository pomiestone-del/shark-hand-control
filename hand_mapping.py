"""Scale/rotation-independent finger bend estimate, without time smoothing."""
import math


def finger_extension(landmarks):
    """Mean PIP joint angle in degrees; use MediaPipe world landmarks if available."""
    angles = []
    for mcp, pip, dip in ((5, 6, 7), (9, 10, 11), (13, 14, 15), (17, 18, 19)):
        a, b, c = landmarks[mcp], landmarks[pip], landmarks[dip]
        u = (a.x - b.x, a.y - b.y, a.z - b.z)
        v = (c.x - b.x, c.y - b.y, c.z - b.z)
        denominator = math.sqrt(sum(t*t for t in u) * sum(t*t for t in v))
        if denominator < 1e-12:
            return None
        cosine = max(-1.0, min(1.0, sum(x*y for x, y in zip(u, v)) / denominator))
        angles.append(math.degrees(math.acos(cosine)))
    return sum(angles) / len(angles)


def mouth_openness(extension, closed=70.0, opened=165.0):
    if opened - closed < 20:
        raise ValueError('Open and closed calibration must differ by at least 20 degrees')
    return max(0.0, min(1.0, (extension - closed) / (opened - closed)))
