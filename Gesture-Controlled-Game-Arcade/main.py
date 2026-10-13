"""Gesture-Controlled Game Arcade entry point."""
import os
import json
import time
import pygame
from src.settings import WIDTH, HEIGHT, FPS, BG, CYAN, PURPLE, WHITE, MAGENTA
from src.hand_tracker import HandTracker
from src.gesture_controller import GestureController
from src.arcade_menu import ArcadeMenu
from src.games.neon_dodge import NeonDodge
from src.games.gesture_pong import GesturePong
from src.ui_components import draw_text, Button
from src.effects import Starfield
from src.selfie_booth import SelfieBooth
from src.living_canvas import LivingCanvas

GAMES = {
    "NEON DODGE": NeonDodge,
    "GESTURE PONG": GesturePong,
}


def _pong_mode_rects(w, h):
    card_w = min(340, (w - 70) // 2)
    card_h = 168
    gap = 24
    start_x = (w - (card_w * 2 + gap)) // 2
    y = max(150, h // 2 - card_h // 2)
    return {
        "ai": pygame.Rect(start_x, y, card_w, card_h),
        "pvp": pygame.Rect(start_x + card_w + gap, y, card_w, card_h),
    }


def main():
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        pass
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Gesture-Controlled Game Arcade")
    clock = pygame.time.Clock()
    tracker = HandTracker()
    controller = GestureController()
    menu = ArcadeMenu()
    stars = Starfield(WIDTH, HEIGHT, 100)
    state, current_game, selected_name = "menu", None, None
    selfie_booth: SelfieBooth | None = None
    living_canvas: LivingCanvas | None = None
    restart_armed = False
    pvp_command_candidate = None
    pvp_command_since = None
    pvp_command_fired = False
    scores_path = "data/high_scores.json"
    os.makedirs("data", exist_ok=True)
    try:
        with open(scores_path, encoding="utf-8") as f:
            high_scores = json.load(f)
    except (OSError, json.JSONDecodeError):
        high_scores = {}
    running = True
    camera_message = "Camera not started"
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        w, h = screen.get_size()
        frame_data = tracker.update()
        gesture = controller.update(frame_data)
        # In two-player Pong, open palms and fists are normal hand poses, not
        # global pause/back commands. Keep those controls available everywhere else.
        pvp_active = (state == "playing" and selected_name == "GESTURE PONG"
                      and current_game is not None and getattr(current_game, "mode", "ai") == "pvp")

        # Two-player Pong commands require BOTH hands to hold the same pose.
        # This keeps either player's normal paddle pose from pausing or exiting
        # the match on its own. A command fires once, then must be released.
        pvp_command = None
        if pvp_active:
            hands_by_side = {hand.get("side"): hand for hand in frame_data.get("hands", [])
                             if hand.get("side") in ("left", "right")}
            left_hand = hands_by_side.get("left")
            right_hand = hands_by_side.get("right")
            command_gestures = {
                "open_palm": "pause",
                "fist": "back",
                "two_finger": "restart",
            }
            left_pose = left_hand.get("gesture") if left_hand else None
            right_pose = right_hand.get("gesture") if right_hand else None
            shared_pose = left_pose if left_pose == right_pose else None
            if left_hand and right_hand and shared_pose in command_gestures:
                now = time.monotonic()
                if shared_pose != pvp_command_candidate:
                    pvp_command_candidate = shared_pose
                    pvp_command_since = now
                    pvp_command_fired = False
                elif (not pvp_command_fired and pvp_command_since is not None
                      and now - pvp_command_since >= 0.9):
                    pvp_command = command_gestures[shared_pose]
                    pvp_command_fired = True
            else:
                pvp_command_candidate = None
                pvp_command_since = None
                pvp_command_fired = False
        else:
            pvp_command_candidate = None
            pvp_command_since = None
            pvp_command_fired = False

        if pvp_command == "pause" and current_game is not None:
            current_game.paused = not current_game.paused
        elif pvp_command == "restart" and current_game is not None:
            current_game = GesturePong(w, h, mode="pvp")
        elif pvp_command == "back":
            state = "pong_mode_select"
            current_game = GesturePong(w, h)
            selected_name = "GESTURE PONG"

        injected = []
        if not pvp_active:
            # Gesture-driven navigation uses the same hit targets as mouse navigation.
            if gesture.get("action") == "select":
                injected.append(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (int(gesture["x"]*w), int(gesture["y"]*h)), "button": 1}))
            elif gesture.get("action") == "back":
                if state == "selfie":
                    if selfie_booth: selfie_booth.close(); selfie_booth = None
                    state = "menu"
                elif state == "living_canvas" and living_canvas:
                    if living_canvas.handle_back():
                        living_canvas = None
                        state = "menu"
                elif state == "pong_mode_select":
                    state = "menu"
                    current_game = None
                    selected_name = None
                elif state in ("playing", "paused", "instructions", "scores", "settings"):
                    state = "menu"
            elif gesture.get("action") == "pause" and state in ("playing", "paused"):
                state = "paused" if state == "playing" else "playing"
            elif gesture.get("action") == "restart" and state in ("playing", "paused"):
                if restart_armed and selected_name in GAMES:
                    if selected_name == "GESTURE PONG":
                        current_game = GesturePong(w, h, mode=getattr(current_game, "mode", "ai"))
                    else:
                        current_game = GAMES[selected_name](w, h)
                    state = "playing"
                    restart_armed = False
                else:
                    restart_armed = True
        events = injected + pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                # In two-player Pong, both hands are dedicated to paddle movement.
                # Use explicit keyboard commands so gestures never conflict with play.
                if (state == "playing" and pvp_active and current_game is not None
                        and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE)):
                    state = "pong_mode_select"
                    current_game = GesturePong(w, h)
                    selected_name = "GESTURE PONG"
                elif (state == "playing" and pvp_active and current_game is not None
                      and event.key in (pygame.K_p, pygame.K_SPACE)):
                    current_game.paused = not current_game.paused
                elif (state == "playing" and pvp_active and current_game is not None
                      and event.key == pygame.K_r):
                    current_game = GesturePong(w, h, mode="pvp")
                elif event.key == pygame.K_ESCAPE:
                    if state == "playing":
                        state = "paused"
                    elif state == "selfie":
                        if selfie_booth:
                            selfie_booth.close()
                            selfie_booth = None
                        state = "menu"
                    elif state == "living_canvas" and living_canvas:
                        if living_canvas.handle_back():
                            living_canvas = None
                            state = "menu"
                    elif state == "pong_mode_select":
                        state = "menu"
                        current_game = None
                        selected_name = None
                    elif state in ("paused", "instructions", "scores", "settings"):
                        state = "menu"
                    else:
                        running = False
                elif event.key == pygame.K_SPACE and state == "paused":
                    state = "playing"
                elif event.key == pygame.K_F11:
                    flags = 0 if screen.get_flags() & pygame.FULLSCREEN else pygame.FULLSCREEN
                    screen = pygame.display.set_mode((w, h), flags)
            if state == "menu":
                action = menu.handle_event(event, (w, h))
                if action == "quit":
                    running = False
                elif action == "settings":
                    state = "settings"
                elif action == "scores":
                    state = "scores"
                elif action == "instructions":
                    state = "instructions"
                elif action == "SELFIE BOOTH":
                    # Reuse the shared webcam frame; opening a second capture handle
                    # is a common cause of an unavailable Selfie Booth preview.
                    selfie_booth = SelfieBooth(external_camera=True)
                    state = "selfie"
                elif action == "LIVING CANVAS":
                    living_canvas = LivingCanvas(w, h)
                    state = "living_canvas"
                elif action == "GESTURE PONG":
                    selected_name = action
                    current_game = GesturePong(w, h)
                    state = "pong_mode_select"
                elif action in GAMES:
                    selected_name = action
                    current_game = GAMES[action](w, h)
                    state = "playing"
            elif state == "pong_mode_select":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for mode_name, rect in _pong_mode_rects(w, h).items():
                        if rect.collidepoint(event.pos):
                            current_game.set_mode(mode_name)
                            state = "playing"
                            break
            elif state == "selfie" and selfie_booth:
                selfie_booth.handle_event(event)
            elif state == "living_canvas" and living_canvas:
                living_canvas.handle_event(event)

        # ------------------------------------------------------------------
        # Update
        # ------------------------------------------------------------------
        if state == "selfie" and selfie_booth:
            selfie_booth.set_camera_frame(frame_data.get("frame"))
            result = selfie_booth.update()
            if result == "back":
                selfie_booth.close()
                selfie_booth = None
                state = "menu"
        elif state == "living_canvas" and living_canvas:
            living_canvas.update(dt, gesture, frame_data)

        # ------------------------------------------------------------------
        # Draw
        # ------------------------------------------------------------------
        screen.fill(BG)
        stars.update(dt)
        stars.draw(screen)
        if state == "menu":
            menu.draw(screen, (w, h), frame_data)
            camera_message = tracker.status
        elif state == "selfie" and selfie_booth:
            selfie_booth.draw(screen)
        elif state == "pong_mode_select":
            draw_text(screen, "GESTURE PONG", (w//2, max(65, h//5)), 40, CYAN, center=True)
            draw_text(screen, "CHOOSE YOUR MATCH", (w//2, max(105, h//5 + 44)), 20, WHITE, center=True)
            rects = _pong_mode_rects(w, h)
            options = [
                ("ai", "PLAYER VS AI", "Play against the arcade opponent", CYAN),
                ("pvp", "2-PLAYER BATTLE", "Two people • one webcam", MAGENTA),
            ]
            for mode_name, title, description, accent in options:
                rect = rects[mode_name]
                pygame.draw.rect(screen, (14, 22, 48), rect, border_radius=18)
                pygame.draw.rect(screen, accent, rect, 2, border_radius=18)
                draw_text(screen, title, (rect.centerx, rect.y+38), 22, accent, center=True)
                draw_text(screen, description, (rect.centerx, rect.y+80), 15, WHITE, center=True)
                draw_text(screen, "POINT + PINCH OR CLICK", (rect.centerx, rect.bottom-28), 13, PURPLE, center=True)
            draw_text(screen, "In 2-player mode, stand side by side and keep one hand visible each.",
                      (w//2, min(h-75, rects["pvp"].bottom+42)), 16, WHITE, center=True)
            draw_text(screen, "THUMBS-UP / ESC: BACK", (w//2, h-35), 14, PURPLE, center=True)
        elif state == "living_canvas" and living_canvas:
            living_canvas.draw(screen)
        elif state == "playing" and current_game:
            current_game.update(dt, gesture, frame_data)
            current_game.draw(screen)
            if current_game.game_over:
                is_pvp_match = (selected_name == "GESTURE PONG" and getattr(current_game, "mode", "ai") == "pvp")
                if not is_pvp_match:
                    high_scores[selected_name] = max(high_scores.get(selected_name, 0), current_game.score)
                    try:
                        with open(scores_path, "w", encoding="utf-8") as f:
                            json.dump(high_scores, f, indent=2)
                    except OSError:
                        pass
                draw_text(screen, "MATCH OVER" if is_pvp_match else "GAME OVER", (w//2, h//2-25), 42, CYAN, center=True)
                if is_pvp_match:
                    draw_text(screen, f"PLAYER 1: {current_game.player_score}   |   PLAYER 2: {current_game.ai_score}",
                              (w//2, h//2+20), 22, WHITE, center=True)
                else:
                    draw_text(screen, f"Score: {current_game.score}   |   Best: {high_scores.get(selected_name, 0)}", (w//2, h//2+20), 22, WHITE, center=True)
                if is_pvp_match:
                    draw_text(screen, "BOTH TWO-FINGER: REMATCH  |  BOTH FISTS: BACK TO MODES", (w//2, h//2+60), 15, PURPLE, center=True)
                else:
                    draw_text(screen, "Press R to restart  |  ESC for menu", (w//2, h//2+60), 18, PURPLE, center=True)
                keys = pygame.key.get_pressed()
                if keys[pygame.K_r]:
                    if selected_name == "GESTURE PONG":
                        current_game = GesturePong(w, h, mode=getattr(current_game, "mode", "ai"))
                    else:
                        current_game = GAMES[selected_name](w, h)
            elif current_game.paused:
                draw_text(screen, "PAUSED", (w//2, h//2), 44, CYAN, center=True)
                if selected_name == "GESTURE PONG" and getattr(current_game, "mode", "ai") == "pvp":
                    draw_text(screen, "BOTH OPEN PALMS: RESUME  |  BOTH TWO-FINGER: RESTART  |  BOTH FISTS: BACK",
                              (w//2, h//2+45), 15, WHITE, center=True)
                else:
                    draw_text(screen, "SPACE to resume  |  ESC for menu", (w//2, h//2+45), 18, WHITE, center=True)
            if selected_name == "GESTURE PONG" and getattr(current_game, "mode", "ai") == "pvp" and not current_game.game_over:
                draw_text(screen, "BOTH OPEN PALMS: PAUSE  |  BOTH TWO-FINGER: RESTART  |  BOTH FISTS: BACK TO MODES",
                          (w//2, 88), 13, WHITE, center=True)
        elif state == "settings":
            draw_text(screen, "SETTINGS", (w//2, 100), 42, CYAN, center=True)
            draw_text(screen, "F11: Toggle fullscreen", (w//2, 190), 24, WHITE, center=True)
            draw_text(screen, "ESC: Return to menu", (w//2, 235), 22, PURPLE, center=True)
            draw_text(screen, f"Webcam: {tracker.status}", (w//2, 300), 18, WHITE, center=True)
        elif state == "scores":
            draw_text(screen, "HIGH SCORES", (w//2, 90), 42, CYAN, center=True)
            for i, name in enumerate(GAMES):
                draw_text(screen, f"{name}: {high_scores.get(name, 0)}", (w//2, 165+i*48), 23, WHITE, center=True)
            draw_text(screen, "ESC: Return to menu", (w//2, h-65), 18, PURPLE, center=True)
        elif state == "instructions":
            draw_text(screen, "HOW TO PLAY", (w//2, 75), 40, CYAN, center=True)
            lines = [
                "Move your hand horizontally to steer players or paddles.",
                "SPACE / mouse remains available as a menu fallback.",
                "Pinch and hold for 1 second to select a menu item.",
                "Neon Dodge: move left/right to avoid incoming obstacles.",
                "Gesture Pong: move your hand up/down to control the paddle.",
                "Open palm (hold 2s) pauses/resumes; closed fist (2s) goes back.",
            ]
            for i, line in enumerate(lines):
                draw_text(screen, line, (w//2, 150+i*38), 18, WHITE, center=True)
            draw_text(screen, "ESC: Return to menu", (w//2, h-50), 18, PURPLE, center=True)
        if state != "living_canvas":
            draw_text(screen, f"CAMERA: {tracker.status}", (12, h-24), 14, (150, 175, 205))

        # Hand-operated cursor and gesture HUD. Pinch clicks use these same
        # normalized coordinates, allowing Selfie Booth controls to be selected
        # without a physical mouse or keyboard.
        if gesture.get("present"):
            pointer_x = max(0, min(w - 1, int(gesture["x"] * w)))
            pointer_y = max(0, min(h - 1, int(gesture["y"] * h)))
            pulse = 11 + int(3 * abs(pygame.time.get_ticks() % 500 - 250) / 250)
            pygame.draw.circle(screen, (8, 10, 28), (pointer_x, pointer_y), pulse + 4)
            pygame.draw.circle(screen, CYAN, (pointer_x, pointer_y), pulse, 2)
            pygame.draw.circle(screen, WHITE, (pointer_x, pointer_y), 3)
            if state == "living_canvas":
                gesture_label = {
                    "point": "POINT · GUIDE FISH",
                    "pinch": "PINCH · HOLD TO SELECT / BUBBLES",
                    "two_finger": "TWO FINGERS · UNUSED HERE",
                    "fist": "FIST · HOLD TO GO BACK",
                    "open_palm": "OPEN PALM · ATTRACT FISH",
                    "other": "HAND DETECTED",
                    "none": "SHOW YOUR HAND",
                }.get(gesture.get("gesture", "none"), "HAND DETECTED")
            else:
                gesture_label = {
                    "point": "POINTER",
                    "pinch": "PINCH · HOLD TO SELECT",
                    "two_finger": "TWO FINGERS · HOLD TO RESTART",
                    "fist": "FIST · HOLD TO GO BACK",
                    "open_palm": "OPEN PALM · HOLD TO PAUSE",
                    "other": "HAND DETECTED",
                    "none": "SHOW YOUR HAND",
                }.get(gesture.get("gesture", "none"), "HAND DETECTED")
            hud_w = min(320 if state == "living_canvas" else 420, w - 24)
            # Keep the hold-progress HUD visible without covering Living Canvas's
            # title or mode button. Other screens retain the established top-left HUD.
            hud_x = max(12, w - hud_w - 12) if state == "living_canvas" else 12
            hud_y = 72 if state == "living_canvas" else 12
            hud = pygame.Surface((hud_w, 58), pygame.SRCALPHA)
            hud.fill((10, 14, 35, 220))
            screen.blit(hud, (hud_x, hud_y))
            draw_text(screen, gesture_label, (hud_x + 12, hud_y + 8), 17, CYAN)
            progress = float(gesture.get("progress", 0.0))
            bar_w = min(390, w - 48, hud_w - 24)
            pygame.draw.rect(screen, (50, 60, 90), pygame.Rect(hud_x + 12, hud_y + 31, bar_w, 5), border_radius=3)
            pygame.draw.rect(screen, MAGENTA, pygame.Rect(hud_x + 12, hud_y + 31, int(bar_w * progress), 5), border_radius=3)
            feedback = gesture.get("feedback", "")
            if feedback and gesture.get("action") and state != "living_canvas":
                draw_text(screen, feedback, (w // 2, 78), 18, WHITE, center=True)
        pygame.display.flip()
    if selfie_booth:
        selfie_booth.close()
    tracker.close()
    pygame.quit()

if __name__ == "__main__":
    main()
