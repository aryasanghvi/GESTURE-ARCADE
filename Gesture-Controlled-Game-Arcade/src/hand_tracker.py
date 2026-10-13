"""Single-instance webcam hand tracking; supports MediaPipe Solutions API."""
import cv2
import numpy as np

class HandTracker:
    def __init__(self, camera_index=0, smoothing=0.35):
        self.camera_index = camera_index
        self.smoothing = smoothing
        self.cap = None
        self.hands = None
        self.last_x = self.last_y = None
        self._gesture_candidate = "none"
        self._gesture_candidate_frames = 0
        self._stable_gesture = "none"
        # Independent smoothing for the left/right screen halves used by 2-player Pong.
        self._side_last = {"left": None, "right": None}
        self.status = "Not initialized"
        self._init_tracker()

    def _init_tracker(self):
        try:
            import mediapipe as mp
            # This project pins mediapipe 0.10.21, which provides solutions.hands.
            solutions = getattr(mp, "solutions", None)
            if solutions is None or not hasattr(solutions, "hands"):
                self.status = "MediaPipe Hands API unavailable (check requirements)"
                return
            self.hands = solutions.hands.Hands(
                static_image_mode=False, max_num_hands=2,
                model_complexity=0, min_detection_confidence=0.55,
                min_tracking_confidence=0.5
            )
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.cap.release()
                self.cap = None
                self.status = "Webcam unavailable"
            else:
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.status = "Connected - show your hand"
        except Exception as exc:
            self.status = f"Tracker init failed: {type(exc).__name__}"

    def update(self):
        # The legacy fields (present/x/y/gesture) are deliberately retained so
        # existing games and menu navigation keep their established interface.
        result = {"present": False, "x": 0.5, "y": 0.5, "index": None,
                  "palm": None, "gesture": "none", "frame": None, "hands": []}
        if self.cap is None or self.hands is None:
            return result
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.status = "Webcam frame unavailable"
            return result
        # Flip once so the camera behaves like a mirror and x coordinates match
        # the positions the players see on screen.
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        try:
            processed = self.hands.process(rgb)
        except Exception:
            self.status = "Hand tracking failed"
            return result
        result["frame"] = frame
        all_landmarks = getattr(processed, "multi_hand_landmarks", None) or []
        if not all_landmarks:
            self.status = "Connected - no hand detected"
            self.last_x = self.last_y = None
            self._side_last = {"left": None, "right": None}
            self._gesture_candidate = self._stable_gesture = "none"
            self._gesture_candidate_frames = 0
            return result

        # Build independent records for up to two hands. Side assignment is based
        # on the palm's horizontal location, not MediaPipe's handedness label;
        # this makes the left/right controls match the mirrored camera preview.
        seen_sides = set()
        records = []
        for landmarks in all_landmarks:
            points = landmarks.landmark
            index_tip, palm = points[8], points[9]
            side = "left" if float(palm.x) < 0.5 else "right"
            seen_sides.add(side)
            old = self._side_last.get(side)
            values = (float(index_tip.x), float(index_tip.y), float(palm.x), float(palm.y))
            if old is not None:
                values = tuple(self.smoothing * current + (1.0 - self.smoothing) * previous
                               for current, previous in zip(values, old))
            self._side_last[side] = values
            ix, iy, px, py = values
            records.append({
                "side": side,
                "x": max(0.0, min(1.0, ix)),
                "y": max(0.0, min(1.0, iy)),
                "index": (max(0.0, min(1.0, ix)), max(0.0, min(1.0, iy))),
                "palm": (max(0.0, min(1.0, px)), max(0.0, min(1.0, py))),
                "palm_x": max(0.0, min(1.0, px)),
                "palm_y": max(0.0, min(1.0, py)),
                "gesture": self._classify_gesture(points),
            })
        # Clear smoothing history for a side that disappeared. The game itself
        # keeps that paddle at its last position briefly, avoiding sudden jumps.
        for side in ("left", "right"):
            if side not in seen_sides:
                self._side_last[side] = None
        records.sort(key=lambda hand: hand["palm_x"])
        result["hands"] = records[:2]

        # Preserve the original single-hand gesture/controller interface. In
        # normal one-player use, this behaves as before; Pong PvP reads `hands`.
        landmarks = all_landmarks[0].landmark
        index, palm = landmarks[8], landmarks[9]
        x, y = float(index.x), float(index.y)
        if self.last_x is not None:
            x = self.smoothing * x + (1.0 - self.smoothing) * self.last_x
            y = self.smoothing * y + (1.0 - self.smoothing) * self.last_y
        self.last_x, self.last_y = x, y
        result.update(present=True, x=max(0.0, min(1.0, x)), y=max(0.0, min(1.0, y)),
                      index=(max(0.0, min(1.0, x)), max(0.0, min(1.0, y))),
                      palm=(float(palm.x), float(palm.y)))
        detected = self._classify_gesture(landmarks)
        if detected == self._gesture_candidate:
            self._gesture_candidate_frames += 1
        else:
            self._gesture_candidate = detected
            self._gesture_candidate_frames = 1
        if self._gesture_candidate_frames >= 2:
            self._stable_gesture = detected
        result["gesture"] = self._stable_gesture
        self.status = "Tracking 2 hands" if len(records) >= 2 else "Hand detected"
        return result

    @staticmethod
    def _classify_gesture(landmarks):
        """Classify poses using finger-joint angles and scale-aware distances.

        Pinch retains its existing threshold because it already works reliably.
        Joint angles are less sensitive to hand tilt than fingertip y-coordinates
        or a single wrist-distance ratio.
        """
        def xyz(i):
            p = landmarks[i]
            return np.array([p.x, p.y, p.z], dtype=float)

        def distance(a, b):
            return float(np.linalg.norm(xyz(a) - xyz(b)))

        def joint_angle(a, joint, c):
            va = xyz(a) - xyz(joint)
            vc = xyz(c) - xyz(joint)
            denom = float(np.linalg.norm(va) * np.linalg.norm(vc))
            if denom < 1e-8:
                return 0.0
            cosine = float(np.clip(np.dot(va, vc) / denom, -1.0, 1.0))
            return float(np.degrees(np.arccos(cosine)))

        # Straight fingers are near 180 degrees at the PIP joint.
        finger_joints = ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20))
        extended = [joint_angle(a, b, c) > 145 for a, b, c in finger_joints]

        # Keep the known-good pinch threshold unchanged.
        index_tip, thumb_tip = landmarks[8], landmarks[4]
        if np.hypot(index_tip.x - thumb_tip.x, index_tip.y - thumb_tip.y) < 0.055:
            return "pinch"

        count = sum(extended)
        if count >= 3:
            return "open_palm"
        if extended[0] and extended[1] and not extended[2] and not extended[3]:
            return "two_finger"
        if extended[0] and not any(extended[1:]):
            return "point"

        # Fist means all four fingers are curled and the thumb is not extended
        # away from its base/palm, preventing a pointing pose from triggering Back.
        thumb_angle = joint_angle(2, 3, 4)
        thumb_near_palm = distance(4, 5) < distance(0, 5) * 0.85
        if count == 0 and (thumb_angle < 145 or thumb_near_palm):
            return "fist"
        return "other"

    def reopen(self):
        self.close()
        self.last_x = self.last_y = None
        self._side_last = {"left": None, "right": None}
        self._gesture_candidate = self._stable_gesture = "none"
        self._gesture_candidate_frames = 0
        self._init_tracker()

    def close(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.hands is not None:
            try: self.hands.close()
            except Exception: pass
            self.hands = None
        cv2.destroyAllWindows()
