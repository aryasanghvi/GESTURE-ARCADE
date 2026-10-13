from src.gesture_controller import GestureController

def test_missing_hand_returns_safe_defaults():
    c=GestureController()
    result=c.update({"present":False})
    assert result["present"] is False
    assert result["gesture"] == "none"

def test_hand_coordinates_are_forwarded():
    c=GestureController()
    result=c.update({"present":True,"x":0.25,"y":0.75,"gesture":"open_palm"})
    assert result["x"] == 0.25
    assert result["y"] == 0.75
    assert result["fire"] is True

def test_swipe_detected_from_large_motion():
    c=GestureController(swipe_threshold=0.1)
    c.update({"present":True,"x":0.1,"y":0.1,"gesture":"point"})
    result=c.update({"present":True,"x":0.5,"y":0.1,"gesture":"point"})
    assert result["swipe"] is not None


def test_pinch_selects_only_after_one_second_and_needs_release():
    c = GestureController()
    c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=0.0)
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=.99)["action"] is None
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=1.01)["action"] == "select"
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=1.5)["action"] is None

def test_tracking_loss_resets_hold():
    c = GestureController()
    c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=0.0)
    c.update({"present": False}, now=.8)
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "pinch"}, now=1.2)["action"] is None


def test_closed_fist_goes_back_after_quick_hold():
    c = GestureController()
    c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=0.0)
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=.89)["action"] is None
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=.91)["action"] == "back"


def test_thumbs_up_does_not_trigger_back():
    c = GestureController()
    result = c.update({"present": True, "x": .5, "y": .5, "gesture": "thumbs_up"}, now=0.0)
    result = c.update({"present": True, "x": .5, "y": .5, "gesture": "thumbs_up"}, now=3.0)
    assert result["action"] is None


def test_fist_action_requires_release_before_repeating():
    c = GestureController()
    c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=0.0)
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=2.1)["action"] == "back"
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "fist"}, now=4.5)["action"] is None


def test_two_finger_restart_is_faster_but_still_requires_deliberate_hold():
    c = GestureController()
    c.update({"present": True, "x": .5, "y": .5, "gesture": "two_finger"}, now=0.0)
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "two_finger"}, now=1.20)["action"] is None
    assert c.update({"present": True, "x": .5, "y": .5, "gesture": "two_finger"}, now=1.26)["action"] == "restart"
