# Gesture-Controlled Game Arcade

A Pygame arcade with webcam-based hand input, Neon Dodge, Gesture Pong, and a Selfie Booth with filters, decorative frames, stickers and three-photo strips. The camera and image-processing features use OpenCV and MediaPipe; photos are saved locally under `data/selfies/`.

## Setup (Windows PowerShell)

Use Python 3.11 or 3.12 for the pinned MediaPipe build.

```powershell
cd Gesture-Controlled-Game-Arcade
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Command Prompt activation alternative: `.venv\Scripts\activate.bat`.

## Controls

- **Menu:** point with your index finger; pinch and hold for 1 second to select. Mouse remains available as a fallback.
- **Back:** thumbs-up held for 2 seconds.
- **Pause/resume:** open palm held for 2 seconds.
- **Restart:** two-finger pose held for 2.5 seconds; release to re-arm before another deliberate hold.
- **Neon Dodge:** move index finger left/right.
- **Gesture Pong:** move index finger up/down to control the paddle.
- **Keyboard fallback:** Escape, Space, R after game over, and F11 for fullscreen.
- **Selfie Booth:** use the on-screen capture, retake, filter, frame, save and strip controls. Camera preview is mirrored and photos are saved locally.

## Tests

```powershell
python -m pytest -q
python -m compileall -q main.py src tests
```

## Troubleshooting

- Close other apps using the webcam. The arcade releases the hand-tracking camera before opening the Selfie Booth camera, then reopens tracking on exit; this avoids common single-camera-handle conflicts on Windows.
- Check Windows Settings → Privacy & security → Camera and allow desktop apps to access the camera.
- If `mediapipe.solutions` is missing, confirm the project venv is active and install with Python 3.11/3.12 using `requirements.txt`.
- The app remains navigable by mouse/keyboard if a camera cannot be opened. Webcam and gesture behavior must be verified on the target machine with an actual camera.

## Project layout

- `main.py`: application loop and state transitions
- `src/hand_tracker.py`: shared webcam hand tracking
- `src/gesture_controller.py`: smoothing, hold gestures and one-shot action gating
- `src/arcade_menu.py`: main menu
- `src/games/`: Neon Dodge, Gesture Pong and shared base game
- `src/selfie_booth.py`: camera, filters, frames, review and strip capture
- `src/effects.py`: starfield and particles
- `data/high_scores.json`: local score persistence
- `data/selfies/`: locally saved captures (created on save)
