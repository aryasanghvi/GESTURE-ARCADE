"""Selfie Booth – a polished arcade photo-capture feature.

Architecture
------------
* SelfieBooth          – top-level controller; owns the webcam capture loop.
* _LiveScreen          – state: showing live preview + controls.
* _ReviewScreen        – state: captured photo with filter / frame / save UI.
* _StripScreen         – state: 3-photo strip capture & preview.
* Photo filters        – pure NumPy / OpenCV transforms, no external APIs.
* Arcade overlays      – drawn with Pygame primitives (no external assets).
"""
from __future__ import annotations

import datetime
import os
import time
from typing import Optional

import cv2
import numpy as np
import pygame

from .settings import (
    BG, CYAN, MAGENTA, MUTED, PANEL, PURPLE, WHITE,
    RED, YELLOW, GREEN,
)
from .ui_components import Button, draw_text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SELFIES_DIR = os.path.join("data", "selfies")
COUNTDOWN_SECS = 3
FLASH_DURATION = 0.18          # seconds the white flash stays visible
STRIP_GAP = 12                 # px between strip photos
STRIP_BORDER = 24              # px outer border for strip
FRAME_RATE_CAP = 30            # max camera reads per second

# Colour palette (extra)
GOLD    = (255, 215,  60)
NEON_G  = ( 57, 255,  20)
NEON_P  = (180,  50, 255)
DARK    = ( 10,  14,  35)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cv_to_pg(frame: np.ndarray) -> pygame.Surface:
    """Convert a BGR OpenCV frame to an RGB Pygame surface."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return pygame.surfarray.make_surface(rgb.swapaxes(0, 1))


def _pg_to_cv(surface: pygame.Surface) -> np.ndarray:
    """Convert a Pygame surface to a BGR OpenCV array."""
    rgb = pygame.surfarray.array3d(surface).swapaxes(0, 1)
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _scale_keep_aspect(surface: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    """Scale *surface* to fit within (max_w, max_h), preserving aspect ratio."""
    sw, sh = surface.get_size()
    ratio = min(max_w / sw, max_h / sh)
    return pygame.transform.smoothscale(surface, (int(sw * ratio), int(sh * ratio)))


# ---------------------------------------------------------------------------
# Photo Filters
# ---------------------------------------------------------------------------

class Filters:
    """Static methods; each takes a BGR ndarray and returns a BGR ndarray."""

    NAMES = [
        "Original",
        "Grayscale",
        "Vintage",
        "Warm Tone",
        "Cool Tone",
        "Cyberpunk Neon",
        "Magical Glow",
    ]

    @staticmethod
    def apply(name: str, frame: np.ndarray) -> np.ndarray:
        fn = {
            "Original":     Filters.original,
            "Grayscale":    Filters.grayscale,
            "Vintage":      Filters.vintage,
            "Warm Tone":    Filters.warm,
            "Cool Tone":    Filters.cool,
            "Cyberpunk Neon": Filters.cyberpunk,
            "Magical Glow": Filters.glow,
        }.get(name, Filters.original)
        return fn(frame)

    @staticmethod
    def original(f: np.ndarray) -> np.ndarray:
        return f.copy()

    @staticmethod
    def grayscale(f: np.ndarray) -> np.ndarray:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def vintage(f: np.ndarray) -> np.ndarray:
        out = f.astype(np.float32)
        # Sepia matrix
        sepia = np.array([[0.272, 0.534, 0.131],
                          [0.349, 0.686, 0.168],
                          [0.393, 0.769, 0.189]], dtype=np.float32)
        out = (out @ sepia.T).clip(0, 255).astype(np.uint8)
        # Add slight vignette
        h, w = out.shape[:2]
        cx, cy = w / 2, h / 2
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
        vignette = np.clip(1.0 - dist * 0.55, 0.35, 1.0).astype(np.float32)
        out = (out * vignette[:, :, None]).clip(0, 255).astype(np.uint8)
        return out

    @staticmethod
    def warm(f: np.ndarray) -> np.ndarray:
        out = f.copy().astype(np.int16)
        out[:, :, 2] = np.clip(out[:, :, 2] + 35, 0, 255)  # R↑
        out[:, :, 1] = np.clip(out[:, :, 1] + 15, 0, 255)  # G↑
        out[:, :, 0] = np.clip(out[:, :, 0] - 25, 0, 255)  # B↓
        return out.astype(np.uint8)

    @staticmethod
    def cool(f: np.ndarray) -> np.ndarray:
        out = f.copy().astype(np.int16)
        out[:, :, 0] = np.clip(out[:, :, 0] + 45, 0, 255)  # B↑
        out[:, :, 1] = np.clip(out[:, :, 1] + 10, 0, 255)  # G↑
        out[:, :, 2] = np.clip(out[:, :, 2] - 30, 0, 255)  # R↓
        return out.astype(np.uint8)

    @staticmethod
    def cyberpunk(f: np.ndarray) -> np.ndarray:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
        # Boost edges with Laplacian
        edge = cv2.Laplacian(g, cv2.CV_32F)
        edge = np.clip(np.abs(edge) * 1.5, 0, 255)
        out = np.zeros((*g.shape, 3), dtype=np.float32)
        # Cyan channel = original blue + edges
        out[:, :, 0] = np.clip(f[:, :, 0].astype(np.float32) * 0.6 + edge * 0.8, 0, 255)
        # Green channel = original + mild edge
        out[:, :, 1] = np.clip(g * 0.35 + edge * 1.1, 0, 255)
        # Red/Magenta channel = edge only
        out[:, :, 2] = np.clip(edge * 1.3, 0, 255)
        # Boost saturation of original
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 2.2, 0, 255)
        boosted = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
        # Blend
        result = np.clip(out * 0.55 + boosted * 0.55, 0, 255).astype(np.uint8)
        return result

    @staticmethod
    def glow(f: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(f, (0, 0), 8)
        glow = cv2.addWeighted(f, 1.0, blurred, 0.65, 0)
        # Shift hue slightly toward magenta
        hsv = cv2.cvtColor(glow, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 0] = (hsv[:, :, 0] + 12) % 180
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.4, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.15, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


# ---------------------------------------------------------------------------
# Arcade Frames / Overlays  (drawn with Pygame primitives)
# ---------------------------------------------------------------------------

class Overlays:
    """Each method receives a *surface* and draws decorative elements on it."""

    NAMES = [
        "No Frame",
        "Neon Arcade",
        "Futuristic Purple",
        "Stars & Sparkles",
        "Crown Sticker",
        "Arcade Champion",
    ]

    @staticmethod
    def apply(name: str, surface: pygame.Surface) -> None:
        fn = {
            "No Frame":          lambda s: None,
            "Neon Arcade":       Overlays.neon_arcade,
            "Futuristic Purple": Overlays.futuristic_purple,
            "Stars & Sparkles":  Overlays.stars_sparkles,
            "Crown Sticker":     Overlays.crown,
            "Arcade Champion":   Overlays.arcade_champion,
        }.get(name, lambda s: None)
        fn(surface)

    # -- Frame helpers -------------------------------------------------------

    @staticmethod
    def _draw_rounded_border(surface, color, thickness=6, radius=18):
        w, h = surface.get_size()
        for i in range(thickness):
            pygame.draw.rect(surface, color,
                             pygame.Rect(i, i, w - 2*i, h - 2*i),
                             1, border_radius=max(2, radius - i))

    @staticmethod
    def neon_arcade(surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        # Outer cyan glow border
        for i, alpha in enumerate([80, 140, 200, 255]):
            c = (*CYAN[:3], alpha)
            # We cannot use per-pixel alpha on an opaque surface directly;
            # simulate by drawing thicker borders with diminishing colour.
            colour = tuple(int(v * alpha / 255) for v in CYAN)
            pygame.draw.rect(surface, colour,
                             pygame.Rect(i * 2, i * 2, w - i*4, h - i*4),
                             2, border_radius=16)
        # Corner decorations
        sz = 22
        corners = [(0, 0), (w - sz, 0), (0, h - sz), (w - sz, h - sz)]
        for cx, cy in corners:
            pygame.draw.rect(surface, CYAN, pygame.Rect(cx, cy, sz, sz), 3, border_radius=6)
        # Bottom label
        font = pygame.font.Font(None, 26)
        lbl = font.render("ARCADE", True, CYAN)
        surface.blit(lbl, (w // 2 - lbl.get_width() // 2, h - 22))

    @staticmethod
    def futuristic_purple(surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        colours = [(PURPLE, 8), (MAGENTA, 4), ((130, 40, 200), 2)]
        for col, thick in colours:
            pygame.draw.rect(surface, col,
                             pygame.Rect(0, 0, w, h), thick, border_radius=14)
        # Diagonal corner lines
        for cx, cy, dx, dy in [(0, 0, 1, 1), (w, 0, -1, 1),
                                (0, h, 1, -1), (w, h, -1, -1)]:
            for step in range(35):
                pygame.draw.line(surface, PURPLE,
                                 (cx, cy), (cx + dx*step*2, cy + dy*step*2), 1)
        font = pygame.font.Font(None, 22)
        lbl = font.render("✦ FUTURISTIC ✦", True, MAGENTA)
        surface.blit(lbl, (w // 2 - lbl.get_width() // 2, 5))

    @staticmethod
    def stars_sparkles(surface: pygame.Surface) -> None:
        rng = np.random.default_rng(42)
        w, h = surface.get_size()
        # Generate each axis independently; a 2x2 low/high array is not a
        # valid broadcast range for a (28, 2) output in NumPy.
        positions_x = rng.integers(0, max(1, w), size=28)
        positions_y = rng.integers(0, max(1, h), size=28)
        for px, py in zip(positions_x, positions_y):
            px, py = int(px), int(py)
            size = int(rng.integers(4, 12))
            palette = [CYAN, GOLD, WHITE, MAGENTA]
            col = palette[int(rng.integers(0, len(palette)))]
            # 4-point star
            pts = [
                (px, py - size), (px + 2, py - 2),
                (px + size, py), (px + 2, py + 2),
                (px, py + size), (px - 2, py + 2),
                (px - size, py), (px - 2, py - 2),
            ]
            pygame.draw.polygon(surface, col, pts)
        # Thin outer border
        pygame.draw.rect(surface, GOLD, pygame.Rect(0, 0, w, h), 3, border_radius=8)

    @staticmethod
    def crown(surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        cx = w // 2
        crown_h = max(40, h // 8)
        top_y = 6
        base_y = top_y + crown_h
        # Crown shape: 5 points
        pts = [
            (cx - crown_h, base_y),
            (cx - crown_h // 2, top_y + crown_h // 3),
            (cx, top_y),
            (cx + crown_h // 2, top_y + crown_h // 3),
            (cx + crown_h, base_y),
        ]
        pygame.draw.polygon(surface, GOLD, pts)
        pygame.draw.polygon(surface, (200, 160, 0), pts, 3)
        # Jewels
        for jx, jy in [(cx - crown_h + 10, base_y - 8), (cx, top_y + 5), (cx + crown_h - 10, base_y - 8)]:
            pygame.draw.circle(surface, MAGENTA, (jx, jy), 6)
            pygame.draw.circle(surface, WHITE, (jx, jy), 3)

    @staticmethod
    def arcade_champion(surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        # Banner ribbon at bottom
        banner_h = 36
        banner_y = h - banner_h - 4
        pygame.draw.rect(surface, PURPLE,
                         pygame.Rect(0, banner_y, w, banner_h + 4))
        pygame.draw.rect(surface, CYAN,
                         pygame.Rect(0, banner_y, w, banner_h + 4), 2)
        font = pygame.font.Font(None, 30)
        txt = font.render("★  ARCADE CHAMPION  ★", True, GOLD)
        surface.blit(txt, (w // 2 - txt.get_width() // 2, banner_y + 6))
        # Thin top border
        pygame.draw.rect(surface, CYAN, pygame.Rect(0, 0, w, h), 4, border_radius=10)


# ---------------------------------------------------------------------------
# Camera wrapper  (own capture; separate from HandTracker)
# ---------------------------------------------------------------------------

class _Camera:
    """Light OpenCV capture wrapper used exclusively by SelfieBooth."""

    def __init__(self, index: int = 0, external: bool = False):
        self.cap: Optional[cv2.VideoCapture] = None
        self.status = "Using shared webcam feed" if external else "Initializing…"
        self._external = external
        self._external_frame: Optional[np.ndarray] = None
        if not external:
            self._open(index)

    def set_external_frame(self, frame: Optional[np.ndarray]) -> None:
        self._external_frame = None if frame is None else frame.copy()

    def _open(self, index: int) -> None:
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                cap.release()
                self.status = "Webcam unavailable"
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, FRAME_RATE_CAP)
            self.cap = cap
            self.status = "Ready"
        except Exception as exc:
            self.status = f"Camera error: {exc}"

    def read(self) -> Optional[np.ndarray]:
        if self._external:
            if self._external_frame is None:
                self.status = "Waiting for shared webcam frame"
                return None
            self.status = "Live preview (shared webcam)"
            return self._external_frame.copy()
        if self.cap is None:
            return None
        try:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.status = "Camera connected but no frames received"
                return None
            self.status = "Live preview"
            return cv2.flip(frame, 1)   # mirror for selfie view
        except Exception as exc:
            self.status = f"Camera read error: {type(exc).__name__}"
            return None

    def release(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.status = "Released"

    @property
    def available(self) -> bool:
        return self._external or self.cap is not None


# ---------------------------------------------------------------------------
# Live Preview Screen
# ---------------------------------------------------------------------------

class _LiveScreen:
    """Shows live webcam feed + Take Selfie / Strip mode / Back buttons."""

    STRIP_COLOR = (90, 255, 180)

    def __init__(self, camera: _Camera):
        self._cam = camera
        self._last_frame: Optional[np.ndarray] = None
        self._countdown_end: Optional[float] = None
        self._capture_flag = False
        self._strip_mode = False
        self._flash_end: float = 0.0
        # Buttons (positions set in draw)
        self._btn_selfie = Button((0, 0, 160, 44), "📷  TAKE SELFIE", CYAN)
        self._btn_strip   = Button((0, 0, 160, 44), "🎞  STRIP MODE",  self.STRIP_COLOR)
        self._btn_back    = Button((0, 0, 140, 40), "◀  BACK",        PURPLE)

    # ------------------------------------------------------------------ draw

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        preview_w = int(w * 0.64)
        preview_h = int(h * 0.66)
        preview_x = (w - preview_w) // 2
        preview_y = 88

        # Live camera frame
        frame = self._cam.read()
        if frame is not None:
            self._last_frame = frame
        if self._last_frame is not None:
            pg_surf = _scale_keep_aspect(_cv_to_pg(self._last_frame), preview_w, preview_h)
            draw_x = preview_x + (preview_w - pg_surf.get_width()) // 2
            draw_y = preview_y + (preview_h - pg_surf.get_height()) // 2
            surface.blit(pg_surf, (draw_x, draw_y))
            pygame.draw.rect(surface, CYAN,
                             pygame.Rect(preview_x, preview_y, preview_w, preview_h),
                             3, border_radius=10)
        else:
            # No camera – grey placeholder
            pygame.draw.rect(surface, (30, 40, 80),
                             pygame.Rect(preview_x, preview_y, preview_w, preview_h),
                             border_radius=10)
            draw_text(surface, "CAMERA PREVIEW UNAVAILABLE",
                      (preview_x + preview_w // 2, preview_y + preview_h // 2 - 12),
                      24, MUTED, center=True)
            draw_text(surface, self._cam.status,
                      (preview_x + preview_w // 2, preview_y + preview_h // 2 + 20),
                      16, YELLOW, center=True)

        # Status bar
        draw_text(surface, f"Camera: {self._cam.status}", (w // 2, 68), 18, MUTED, center=True)

        # Countdown overlay
        now = time.monotonic()
        if self._countdown_end is not None:
            remaining = self._countdown_end - now
            if remaining > 0:
                digit = str(int(remaining) + 1)
                font_big = pygame.font.Font(None, 200)
                txt = font_big.render(digit, True, CYAN)
                cx = preview_x + preview_w // 2 - txt.get_width() // 2
                cy = preview_y + preview_h // 2 - txt.get_height() // 2
                shadow = font_big.render(digit, True, (0, 80, 100))
                surface.blit(shadow, (cx + 3, cy + 3))
                surface.blit(txt, (cx, cy))
            else:
                self._capture_flag = True
                self._countdown_end = None

        # Flash
        if now < self._flash_end:
            alpha = int(255 * (self._flash_end - now) / FLASH_DURATION)
            flash = pygame.Surface((w, h), pygame.SRCALPHA)
            flash.fill((255, 255, 255, min(alpha, 220)))
            surface.blit(flash, (0, 0))

        # Buttons – bottom row
        btn_y = preview_y + preview_h + 20
        bw = 180
        gap = 22
        total = bw * 2 + gap
        bx = (w - total) // 2
        self._btn_selfie.rect = pygame.Rect(bx, btn_y, bw, 46)
        self._btn_strip.rect   = pygame.Rect(bx + bw + gap, btn_y, bw, 46)
        self._btn_back.rect    = pygame.Rect(30, h - 58, 140, 42)

        mx, my = pygame.mouse.get_pos()
        for btn in (self._btn_selfie, self._btn_strip, self._btn_back):
            btn.draw(surface, btn.rect.collidepoint(mx, my))

        # Strip mode indicator
        if self._strip_mode:
            draw_text(surface, "STRIP MODE ACTIVE – capturing 3 photos",
                      (w // 2, btn_y + 58), 17, self.STRIP_COLOR, center=True)

        # Title
        draw_text(surface, "📸  SELFIE BOOTH", (w // 2, 32), 34, CYAN, center=True)
        draw_text(surface, "Move index to point  •  Pinch and hold to select  •  Fist to go back",
                  (w // 2, h - 12), 15, MUTED, center=True)

    # ---------------------------------------------------------- event handling

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Return action string or None."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self._btn_back.hit(pos):
                return "back"
            if self._btn_selfie.hit(pos):
                self._strip_mode = False
                self._start_countdown()
            if self._btn_strip.hit(pos):
                self._strip_mode = True
                return "start_strip"
        return None

    def _start_countdown(self) -> None:
        self._countdown_end = time.monotonic() + COUNTDOWN_SECS
        self._capture_flag = False

    def check_capture(self) -> Optional[np.ndarray]:
        """Call each frame; returns the captured frame when ready."""
        if self._capture_flag:
            self._capture_flag = False
            self._flash_end = time.monotonic() + FLASH_DURATION
            return self._last_frame
        return None

    def reset(self) -> None:
        self._countdown_end = None
        self._capture_flag = False
        self._strip_mode = False


# ---------------------------------------------------------------------------
# Review Screen
# ---------------------------------------------------------------------------

class _ReviewScreen:
    """Shows a captured photo with filter + frame controls and save option."""

    def __init__(self, raw_frame: np.ndarray):
        self._raw = raw_frame.copy()
        self._filter_idx = 0
        self._overlay_idx = 0
        self._message: str = ""
        self._msg_end: float = 0.0
        # Pre-build button list (positions filled in draw)
        self._btn_retake  = Button((0, 0, 1, 1), "◀  RETAKE",    PURPLE)
        self._btn_live    = Button((0, 0, 1, 1), "📷  LIVE CAM", CYAN)
        self._btn_save    = Button((0, 0, 1, 1), "💾  SAVE",      GREEN)
        self._btns_filter: list[Button] = []
        self._btns_frame:  list[Button] = []

    # ------------------------------------------------------------------ draw

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        # Title
        draw_text(surface, "📸  CAPTURED PHOTO", (w // 2, 28), 30, CYAN, center=True)

        # Compose filtered + overlaid image
        filtered = Filters.apply(Filters.NAMES[self._filter_idx], self._raw)
        pg_photo = _cv_to_pg(filtered)

        # Photo panel: left 60 %
        panel_w = int(w * 0.56)
        panel_h = int(h * 0.62)
        panel_x = 28
        panel_y = 68
        photo_surf = _scale_keep_aspect(pg_photo, panel_w, panel_h)
        # Apply overlay to a copy of the photo surface
        overlay_surf = photo_surf.copy()
        Overlays.apply(Overlays.NAMES[self._overlay_idx], overlay_surf)
        px = panel_x + (panel_w - overlay_surf.get_width()) // 2
        py = panel_y + (panel_h - overlay_surf.get_height()) // 2
        pygame.draw.rect(surface, PANEL,
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h),
                         border_radius=12)
        surface.blit(overlay_surf, (px, py))
        pygame.draw.rect(surface, CYAN,
                         pygame.Rect(panel_x, panel_y, panel_w, panel_h),
                         2, border_radius=12)

        # Right panel: filters + frames
        rp_x = panel_x + panel_w + 22
        rp_w = w - rp_x - 16

        draw_text(surface, "FILTERS", (rp_x, panel_y), 18, MUTED)
        self._btns_filter = []
        for fi, fname in enumerate(Filters.NAMES):
            by = panel_y + 24 + fi * 38
            col = CYAN if fi == self._filter_idx else MUTED
            rect = pygame.Rect(rp_x, by, rp_w, 34)
            pygame.draw.rect(surface, (18, 24, 52) if fi == self._filter_idx else PANEL,
                             rect, border_radius=8)
            pygame.draw.rect(surface, col, rect, 1, border_radius=8)
            draw_text(surface, fname, rect.center, 18, col, center=True)
            self._btns_filter.append(Button(rect, fname, col))

        frame_y_start = panel_y + 24 + len(Filters.NAMES) * 38 + 14
        draw_text(surface, "FRAMES", (rp_x, frame_y_start), 18, MUTED)
        self._btns_frame = []
        for oi, oname in enumerate(Overlays.NAMES):
            by = frame_y_start + 24 + oi * 34
            if by + 34 > h - 10:
                break
            col = MAGENTA if oi == self._overlay_idx else MUTED
            rect = pygame.Rect(rp_x, by, rp_w, 30)
            pygame.draw.rect(surface, (28, 14, 52) if oi == self._overlay_idx else PANEL,
                             rect, border_radius=8)
            pygame.draw.rect(surface, col, rect, 1, border_radius=8)
            draw_text(surface, oname, rect.center, 16, col, center=True)
            self._btns_frame.append(Button(rect, oname, col))

        # Bottom action buttons
        bh = 44
        by = h - bh - 16
        third = (panel_w + panel_x - 28) // 3 - 8
        self._btn_retake.rect = pygame.Rect(28, by, third, bh)
        self._btn_live.rect   = pygame.Rect(28 + third + 10, by, third, bh)
        self._btn_save.rect   = pygame.Rect(28 + (third + 10) * 2, by, third, bh)

        mx, my = pygame.mouse.get_pos()
        for btn in (self._btn_retake, self._btn_live, self._btn_save):
            btn.draw(surface, btn.rect.collidepoint(mx, my))

        # Message toast
        if self._message and time.monotonic() < self._msg_end:
            draw_text(surface, self._message, (w // 2, by - 30), 20, GOLD, center=True)
        draw_text(surface, "Point at a filter/frame, then pinch to select",
                  (w - 18, h - 12), 14, MUTED, center=False)

    # ---------------------------------------------------------- event handling

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        pos = event.pos
        if self._btn_retake.hit(pos):
            return "retake"
        if self._btn_live.hit(pos):
            return "live"
        if self._btn_save.hit(pos):
            self._save_photo()
            return None
        for fi, btn in enumerate(self._btns_filter):
            if btn.hit(pos):
                self._filter_idx = fi
                return None
        for oi, btn in enumerate(self._btns_frame):
            if btn.hit(pos):
                self._overlay_idx = oi
                return None
        return None

    # ------------------------------------------------------------------ save

    def _save_photo(self) -> None:
        try:
            os.makedirs(SELFIES_DIR, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SELFIES_DIR, f"selfie_{ts}.png")
            # Compose final image via Pygame then convert back to OpenCV for saving
            filtered = Filters.apply(Filters.NAMES[self._filter_idx], self._raw)
            pg_photo = _cv_to_pg(filtered)
            Overlays.apply(Overlays.NAMES[self._overlay_idx], pg_photo)
            final_bgr = _pg_to_cv(pg_photo)
            cv2.imwrite(path, final_bgr)
            self._message = f"✅  Saved: {os.path.basename(path)}"
            self._msg_end = time.monotonic() + 3.5
        except Exception as exc:
            self._message = f"❌  Save failed: {exc}"
            self._msg_end = time.monotonic() + 4.0

    def get_composed_frame(self) -> np.ndarray:
        """Return current filter+overlay composited BGR frame."""
        filtered = Filters.apply(Filters.NAMES[self._filter_idx], self._raw)
        pg_photo = _cv_to_pg(filtered)
        Overlays.apply(Overlays.NAMES[self._overlay_idx], pg_photo)
        return _pg_to_cv(pg_photo)


# ---------------------------------------------------------------------------
# Three-Photo Strip Screen
# ---------------------------------------------------------------------------

class _StripScreen:
    """Captures 3 photos, composes a vertical strip, lets user save."""

    MAX_PHOTOS = 3
    STRIP_TITLE = "🎮  ARCADE PHOTO STRIP  🎮"

    def __init__(self, camera: _Camera):
        self._cam = camera
        self._photos: list[np.ndarray] = []
        self._last_frame: Optional[np.ndarray] = None
        self._countdown_end: Optional[float] = None
        self._capture_flag = False
        self._flash_end: float = 0.0
        self._strip_surf: Optional[pygame.Surface] = None
        self._message: str = ""
        self._msg_end: float = 0.0
        self._done = False
        self._btn_save   = Button((0, 0, 1, 1), "💾  SAVE STRIP", GREEN)
        self._btn_retake = Button((0, 0, 1, 1), "🔄  RETAKE",     PURPLE)
        self._btn_back   = Button((0, 0, 1, 1), "◀  BACK",        MUTED)
        # Start first countdown automatically
        self._start_countdown()

    def _start_countdown(self) -> None:
        self._countdown_end = time.monotonic() + COUNTDOWN_SECS
        self._capture_flag = False

    def draw(self, surface: pygame.Surface) -> None:
        w, h = surface.get_size()
        draw_text(surface, self.STRIP_TITLE, (w // 2, 28), 28, CYAN, center=True)

        if not self._done:
            # Live preview
            frame = self._cam.read()
            if frame is not None:
                self._last_frame = frame
            preview_w = int(w * 0.56)
            preview_h = int(h * 0.60)
            px = (w - preview_w) // 2
            py = 68
            if self._last_frame is not None:
                pg_surf = pygame.transform.smoothscale(_cv_to_pg(self._last_frame),
                                                       (preview_w, preview_h))
                surface.blit(pg_surf, (px, py))
                pygame.draw.rect(surface, CYAN,
                                 pygame.Rect(px, py, preview_w, preview_h),
                                 3, border_radius=10)
            progress_y = py + preview_h + 14
            for i in range(self.MAX_PHOTOS):
                cx = w // 2 + (i - 1) * 50
                col = GREEN if i < len(self._photos) else (50, 60, 90)
                pygame.draw.circle(surface, col, (cx, progress_y), 14)
                draw_text(surface, str(i + 1), (cx, progress_y), 18, WHITE, center=True)
            draw_text(surface, f"Photo {len(self._photos)+1} of {self.MAX_PHOTOS}",
                      (w // 2, progress_y + 28), 18, MUTED, center=True)

            # Countdown overlay
            now = time.monotonic()
            if self._countdown_end is not None:
                remaining = self._countdown_end - now
                if remaining > 0:
                    digit = str(int(remaining) + 1)
                    font_big = pygame.font.Font(None, 180)
                    txt = font_big.render(digit, True, CYAN)
                    surface.blit(txt, (px + preview_w // 2 - txt.get_width() // 2,
                                      py + preview_h // 2 - txt.get_height() // 2))
                else:
                    self._capture_flag = True
                    self._countdown_end = None

            # Flash
            if now < self._flash_end:
                alpha = int(255 * (self._flash_end - now) / FLASH_DURATION)
                flash = pygame.Surface((w, h), pygame.SRCALPHA)
                flash.fill((255, 255, 255, min(alpha, 220)))
                surface.blit(flash, (0, 0))
        else:
            # Show strip
            if self._strip_surf is not None:
                scaled = _scale_keep_aspect(self._strip_surf, int(w * 0.42), int(h * 0.82))
                sx = (w // 2) - scaled.get_width() // 2 - 60
                sy = 64
                surface.blit(scaled, (sx, sy))
                pygame.draw.rect(surface, CYAN,
                                 pygame.Rect(sx, sy, scaled.get_width(), scaled.get_height()),
                                 2, border_radius=6)

            # Action buttons
            bh, bw = 44, 190
            by = h - bh - 20
            bx_save   = w // 2 + 20
            bx_retake = w // 2 - bw - 20
            bx_back   = 20
            self._btn_save.rect   = pygame.Rect(bx_save,   by, bw, bh)
            self._btn_retake.rect = pygame.Rect(bx_retake, by, bw, bh)
            self._btn_back.rect   = pygame.Rect(bx_back,   by, 130, bh)
            mx, my = pygame.mouse.get_pos()
            for btn in (self._btn_save, self._btn_retake, self._btn_back):
                btn.draw(surface, btn.rect.collidepoint(mx, my))

        # Toast
        if self._message and time.monotonic() < self._msg_end:
            draw_text(surface, self._message, (w // 2, h - 80), 20, GOLD, center=True)
        draw_text(surface, "Pinch to save / retake  •  Fist to go back",
                  (w // 2, h - 8), 14, MUTED, center=True)

    def update(self) -> None:
        """Call every frame to check capture trigger."""
        if self._capture_flag and self._last_frame is not None:
            self._capture_flag = False
            self._flash_end = time.monotonic() + FLASH_DURATION
            self._photos.append(self._last_frame.copy())
            if len(self._photos) < self.MAX_PHOTOS:
                self._start_countdown()
            else:
                self._strip_surf = self._build_strip()
                self._done = True

    def _build_strip(self) -> pygame.Surface:
        ph, pw = self._photos[0].shape[:2]
        strip_w = pw + STRIP_BORDER * 2
        strip_h = ph * self.MAX_PHOTOS + STRIP_GAP * (self.MAX_PHOTOS - 1) + STRIP_BORDER * 2 + 55
        strip = pygame.Surface((strip_w, strip_h))
        strip.fill(DARK)
        pygame.draw.rect(strip, PURPLE, pygame.Rect(0, 0, strip_w, strip_h), 6, border_radius=14)
        # Title
        font = pygame.font.Font(None, 28)
        title = font.render("✦  ARCADE PHOTO STRIP  ✦", True, CYAN)
        strip.blit(title, (strip_w // 2 - title.get_width() // 2, 8))
        for i, photo in enumerate(self._photos):
            pg_surf = _cv_to_pg(photo)
            y = STRIP_BORDER + 45 + i * (ph + STRIP_GAP)
            strip.blit(pg_surf, (STRIP_BORDER, y))
        return strip

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return None
        if not self._done:
            return None
        pos = event.pos
        if self._btn_back.hit(pos):
            return "back"
        if self._btn_retake.hit(pos):
            return "retake"
        if self._btn_save.hit(pos):
            self._save_strip()
        return None

    def _save_strip(self) -> None:
        try:
            os.makedirs(SELFIES_DIR, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SELFIES_DIR, f"strip_{ts}.png")
            cv_img = _pg_to_cv(self._strip_surf)
            cv2.imwrite(path, cv_img)
            self._message = f"✅  Strip saved: {os.path.basename(path)}"
            self._msg_end = time.monotonic() + 3.5
        except Exception as exc:
            self._message = f"❌  Save failed: {exc}"
            self._msg_end = time.monotonic() + 4.0

    def reset(self) -> None:
        self._photos.clear()
        self._strip_surf = None
        self._done = False
        self._countdown_end = None
        self._capture_flag = False
        self._start_countdown()


# ---------------------------------------------------------------------------
# SelfieBooth – top-level controller
# ---------------------------------------------------------------------------

class SelfieBooth:
    """Manages SelfieBooth states: live → review / strip.

    Usage from main loop::

        booth = SelfieBooth()            # created when entering selfie booth
        # Each frame:
        booth.handle_event(event)
        action = booth.update()
        if action == "back":
            ...                          # return to arcade menu
        booth.draw(screen)
        # On exit:
        booth.close()
    """

    _STATE_LIVE    = "live"
    _STATE_REVIEW  = "review"
    _STATE_STRIP   = "strip"

    def __init__(self, camera_index: int = 0, external_camera: bool = False):
        self._cam = _Camera(camera_index, external=external_camera)
        self._live = _LiveScreen(self._cam)
        self._review: Optional[_ReviewScreen] = None
        self._strip: Optional[_StripScreen]   = None
        self._state = self._STATE_LIVE

    # ------------------------------------------------------------------ API

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._state == self._STATE_LIVE:
            action = self._live.handle_event(event)
            if action == "back":
                self._pending_back = True
            elif action == "start_strip":
                self._strip = _StripScreen(self._cam)
                self._state = self._STATE_STRIP
        elif self._state == self._STATE_REVIEW and self._review:
            action = self._review.handle_event(event)
            if action == "retake":
                self._live.reset()
                self._state = self._STATE_LIVE
            elif action == "live":
                self._live.reset()
                self._state = self._STATE_LIVE
        elif self._state == self._STATE_STRIP and self._strip:
            action = self._strip.handle_event(event)
            if action == "back":
                self._live.reset()
                self._state = self._STATE_LIVE
            elif action == "retake":
                self._strip.reset()

    def update(self) -> Optional[str]:
        """Returns 'back' when user wants to exit the booth."""
        if hasattr(self, "_pending_back") and self._pending_back:
            self._pending_back = False
            return "back"
        if self._state == self._STATE_LIVE:
            captured = self._live.check_capture()
            if captured is not None:
                self._review = _ReviewScreen(captured)
                self._state = self._STATE_REVIEW
        elif self._state == self._STATE_STRIP and self._strip:
            self._strip.update()
        return None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG)
        if self._state == self._STATE_LIVE:
            self._live.draw(surface)
        elif self._state == self._STATE_REVIEW and self._review:
            self._review.draw(surface)
        elif self._state == self._STATE_STRIP and self._strip:
            self._strip.draw(surface)

    def set_camera_frame(self, frame: Optional[np.ndarray]) -> None:
        """Use the shared hand-tracker frame to avoid opening the webcam twice."""
        self._cam.set_external_frame(frame)

    def close(self) -> None:
        """Release camera resources."""
        self._cam.release()
