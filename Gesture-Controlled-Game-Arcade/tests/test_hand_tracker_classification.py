from types import SimpleNamespace

from src.hand_tracker import HandTracker


def _landmarks(points):
    """Build the small MediaPipe-like landmark structure used by classifier."""
    return [SimpleNamespace(x=x, y=y, z=z) for x, y, z in points]


def _base_hand():
    # All four fingers folded; thumb folded across the palm.
    p = [(0.50, 0.80, 0.0) for _ in range(21)]
    p[0] = (0.50, 0.80, 0.0)
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        p[pip] = (0.50, 0.68, 0.0)
        p[tip] = (0.52, 0.74, 0.0)
    p[3] = (0.48, 0.72, 0.0)
    p[4] = (0.44, 0.76, 0.0)
    p[8] = (0.52, 0.74, 0.0)
    return p


def test_index_point_is_not_misclassified_as_thumbs_up():
    p = _base_hand()
    p[6] = (0.49, 0.55, 0.0)
    p[8] = (0.48, 0.28, 0.0)
    assert HandTracker._classify_gesture(_landmarks(p)) == "point"


def test_closed_fist_is_back_gesture_pose():
    assert HandTracker._classify_gesture(_landmarks(_base_hand())) == "fist"


def test_raised_thumb_is_not_classified_as_back():
    p = _base_hand()
    p[3] = (0.55, 0.63, 0.0)
    p[4] = (0.55, 0.48, 0.0)
    assert HandTracker._classify_gesture(_landmarks(p)) == "other"
