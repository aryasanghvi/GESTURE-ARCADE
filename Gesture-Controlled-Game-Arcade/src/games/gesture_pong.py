"""Gesture Pong with AI and two-human webcam modes."""
import random
import pygame

from .base_game import BaseGame
from ..settings import CYAN, MAGENTA, WHITE, PURPLE, MUTED
from ..ui_components import draw_text


class GesturePong(BaseGame):
    title = "GESTURE PONG"
    WIN_SCORE = 7

    def __init__(self, w, h, mode="ai"):
        super().__init__(w, h)
        self.paddle = pygame.Rect(30, h // 2 - 55, 15, 110)
        self.ai = pygame.Rect(w - 45, h // 2 - 55, 15, 110)
        self.ball = pygame.Rect(w // 2 - 9, h // 2 - 9, 18, 18)
        self.player_score = 0
        self.ai_score = 0
        self.mode = "pvp" if mode == "pvp" else "ai"
        self._serve_timer = 1.25
        self._missing_left = 0.0
        self._missing_right = 0.0
        self._last_left_y = self.paddle.centery
        self._last_right_y = self.ai.centery
        self._serve(1, initial=True)

    def set_mode(self, mode):
        """Select AI or human-vs-human play and reset the match."""
        self.mode = "pvp" if mode == "pvp" else "ai"
        self.player_score = 0
        self.ai_score = 0
        self.score = 0
        self.game_over = False
        self.paused = False
        self.elapsed = 0.0
        self._missing_left = self._missing_right = 0.0
        self._last_left_y = self.paddle.centery
        self._last_right_y = self.ai.centery
        self._serve(1, initial=True)

    @staticmethod
    def _side_hands(frame_data):
        """Return at most one hand per screen side, robust to detector ordering."""
        selected = {}
        for hand in frame_data.get("hands", []) if frame_data else []:
            side = hand.get("side")
            if side not in ("left", "right"):
                continue
            # If both detected hands briefly land in one half, keep the hand
            # closest to that player's natural center rather than driving both paddles.
            target_x = 0.25 if side == "left" else 0.75
            distance = abs(float(hand.get("palm_x", hand.get("x", target_x))) - target_x)
            previous = selected.get(side)
            if previous is None or distance < previous[0]:
                selected[side] = (distance, hand)
        return {side: value[1] for side, value in selected.items()}

    def update(self, dt, g, frame_data):
        super().update(dt, g, frame_data)
        if self.game_over or self.paused:
            return

        if self.mode == "pvp":
            hands = self._side_hands(frame_data)
            left_hand = hands.get("left")
            right_hand = hands.get("right")
            if left_hand is not None:
                self.paddle.centery = int(float(left_hand.get("palm_y", left_hand.get("y", 0.5))) * self.h)
                self._last_left_y = self.paddle.centery
                self._missing_left = 0.0
            else:
                self._missing_left += dt
            if right_hand is not None:
                self.ai.centery = int(float(right_hand.get("palm_y", right_hand.get("y", 0.5))) * self.h)
                self._last_right_y = self.ai.centery
                self._missing_right = 0.0
            else:
                self._missing_right += dt
            # Keep each paddle at its last reliable position if a hand vanishes.
            # No keyboard/AI fallback is used in PvP, so players never fight an AI.
        else:
            if g.get("present"):
                self.paddle.centery = int(g["y"] * self.h)
            else:
                keys = pygame.key.get_pressed()
                if keys[pygame.K_UP]:
                    self.paddle.y -= int(350 * dt)
                if keys[pygame.K_DOWN]:
                    self.paddle.y += int(350 * dt)
            self.ai.centery += max(-260 * dt, min(260 * dt, self.ball.centery - self.ai.centery))

        bounds = pygame.Rect(0, 0, self.w, self.h)
        self.paddle.clamp_ip(bounds)
        self.ai.clamp_ip(bounds)

        if self._serve_timer > 0:
            self._serve_timer = max(0.0, self._serve_timer - dt)
            return

        self.ball.x += int(self.vx * dt)
        self.ball.y += int(self.vy * dt)
        if self.ball.top <= 0:
            self.ball.top = 0
            self.vy = abs(self.vy)
        elif self.ball.bottom >= self.h:
            self.ball.bottom = self.h
            self.vy = -abs(self.vy)

        if self.ball.colliderect(self.paddle) and self.vx < 0:
            self.ball.left = self.paddle.right
            self.vx = min(abs(self.vx) * 1.04, 620)
            self.vy += (self.ball.centery - self.paddle.centery) * 2
        if self.ball.colliderect(self.ai) and self.vx > 0:
            self.ball.right = self.ai.left
            self.vx = -min(abs(self.vx) * 1.04, 620)
            self.vy += (self.ball.centery - self.ai.centery) * 2

        # A miss on the left scores for the right player/AI, and vice versa.
        if self.ball.right < 0:
            self.ai_score += 1
            self._serve(1)
        elif self.ball.left > self.w:
            self.player_score += 1
            self._serve(-1)
        self.score = self.player_score
        if self.player_score >= self.WIN_SCORE or self.ai_score >= self.WIN_SCORE:
            self.game_over = True

    def _serve(self, direction, initial=False):
        self.ball.center = (self.w // 2, self.h // 2)
        speed = 300 if initial else min(300 + (self.player_score + self.ai_score) * 8, 420)
        self.vx = speed * direction
        self.vy = random.choice([-190, 190])
        self._serve_timer = 1.25 if initial else 0.65

    def draw(self, screen):
        self.draw_background(screen)
        for y in range(0, self.h, 28):
            pygame.draw.rect(screen, (45, 55, 90), (self.w // 2 - 1, y, 2, 14))

        # Subtle player-side glow helps each player identify their paddle.
        left_glow = pygame.Surface((80, self.h), pygame.SRCALPHA)
        pygame.draw.rect(left_glow, (20, 210, 255, 18), (0, 0, 80, self.h))
        screen.blit(left_glow, (0, 0))
        right_glow = pygame.Surface((80, self.h), pygame.SRCALPHA)
        pygame.draw.rect(right_glow, (255, 50, 190, 18), (0, 0, 80, self.h))
        screen.blit(right_glow, (self.w - 80, 0))

        pygame.draw.rect(screen, CYAN, self.paddle, border_radius=7)
        pygame.draw.rect(screen, MAGENTA, self.ai, border_radius=7)
        pygame.draw.ellipse(screen, WHITE, self.ball)
        pygame.draw.circle(screen, (70, 220, 255), self.ball.center, 14, 1)

        draw_text(screen, "PLAYER 1", (self.w * 0.25, 22), 16, CYAN, center=True)
        opponent_label = "PLAYER 2" if self.mode == "pvp" else "ARCADE AI"
        draw_text(screen, opponent_label, (self.w * 0.75, 22), 16, MAGENTA, center=True)
        draw_text(screen, str(self.player_score), (self.w * 0.25, 52), 34, CYAN, center=True)
        draw_text(screen, str(self.ai_score), (self.w * 0.75, 52), 34, MAGENTA, center=True)

        if self.mode == "pvp":
            draw_text(screen, "LEFT HAND CONTROLS PLAYER 1", (self.w * 0.25, self.h - 30), 14, CYAN, center=True)
            draw_text(screen, "RIGHT HAND CONTROLS PLAYER 2", (self.w * 0.75, self.h - 30), 14, MAGENTA, center=True)
            if self._missing_left > 0.8 or self._missing_right > 0.8:
                missing = []
                if self._missing_left > 0.8:
                    missing.append("left")
                if self._missing_right > 0.8:
                    missing.append("right")
                draw_text(screen, f"SHOW YOUR HAND: {' + '.join(missing)} PLAYER", (self.w // 2, self.h - 58), 16, WHITE, center=True)
        else:
            draw_text(screen, "MOVE YOUR HAND UP / DOWN", (self.w // 2, self.h - 30), 16, WHITE, center=True)

        if self._serve_timer > 0 and not self.game_over:
            label = "GET READY" if self._serve_timer > 0.65 else "GO!"
            draw_text(screen, label, (self.w // 2, self.h // 2 - 48), 28, PURPLE, center=True)
        if self.game_over:
            winner = "PLAYER 1 WINS!" if self.player_score >= self.WIN_SCORE else ("PLAYER 2 WINS!" if self.mode == "pvp" else "ARCADE AI WINS!")
            draw_text(screen, winner, (self.w // 2, self.h // 2 + 58), 30, CYAN if self.player_score >= self.WIN_SCORE else MAGENTA, center=True)
