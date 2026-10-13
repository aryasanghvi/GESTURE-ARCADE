"""Main menu for the Gesture-Controlled Game Arcade."""
import pygame
from .ui_components import draw_text
from .settings import CYAN, PURPLE, MAGENTA, WHITE, PANEL, MUTED

SELFIE_COLOR = (42, 220, 255)
CANVAS_COLOR = (91, 244, 232)


class ArcadeMenu:
    GAMES = [
        ("NEON DODGE", "Move left/right • dodge the neon storm", PURPLE),
        ("GESTURE PONG", "AI challenge or 2-player hand battle", (90, 255, 180)),
    ]

    def __init__(self):
        self.buttons = []

    def handle_event(self, event, size):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, name in self.buttons:
                if rect.collidepoint(event.pos):
                    return name
        return None

    def _draw_card(self, surface, rect, name, desc, accent, number=None, action_label="POINT + PINCH"):
        pygame.draw.rect(surface, (15, 21, 47), rect, border_radius=18)
        pygame.draw.rect(surface, accent, rect, 2, border_radius=18)
        pygame.draw.circle(surface, accent, (rect.x+32, rect.y+34), 6)
        if number is not None:
            draw_text(surface, f"{number:02d}", (rect.x+20, rect.y+57), 18, accent)
            title_x = rect.x+58
        else:
            title_x = rect.x+24
        draw_text(surface, name, (title_x, rect.y+22), 21, WHITE)
        draw_text(surface, desc, (rect.x+22, rect.y+68), 14, MUTED)
        draw_text(surface, action_label, (rect.x+22, rect.bottom-27), 12, accent)

    def draw(self, surface, size, frame_data=None):
        w, h = size
        draw_text(surface, "GESTURE", (w//2, 42), 24, PURPLE, center=True)
        draw_text(surface, "ARCADE", (w//2, 78), 45, CYAN, center=True)
        draw_text(surface, "PLAY WITH YOUR HANDS  •  NO CONTROLLER REQUIRED",
                  (w//2, 116), 14, MUTED, center=True)
        self.buttons = []
        card_w = min(430, (w-70)//2)
        card_h = 124
        gap_x = 22
        start_x = (w-(card_w*2+gap_x))//2
        row1_y = 145
        for i, (name, desc, color) in enumerate(self.GAMES):
            x = start_x+i*(card_w+gap_x)
            rect = pygame.Rect(x, row1_y, card_w, card_h)
            self._draw_card(surface, rect, name, desc, color, i+1, "PINCH + HOLD TO OPEN")
            self.buttons.append((rect, name))

        # Creative experience: a matching card in row two, beside the Selfie Booth.
        row2_y = row1_y + card_h + 15
        living_rect = pygame.Rect(start_x, row2_y, card_w, card_h)
        self._draw_card(surface, living_rect, "LIVING CANVAS", "Explore a glowing underwater world", CANVAS_COLOR, 3,
                        "POINT + PINCH TO OPEN")
        # Small fish glyph makes this tile visually distinct.
        fish_x, fish_y = living_rect.right-45, living_rect.y+43
        pygame.draw.ellipse(surface, (18, 92, 115), pygame.Rect(fish_x-19, fish_y-9, 28, 18))
        pygame.draw.polygon(surface, CANVAS_COLOR, [(fish_x-19,fish_y),(fish_x-29,fish_y-8),(fish_x-29,fish_y+8)])
        pygame.draw.circle(surface, WHITE, (fish_x+2, fish_y-2), 2)
        self.buttons.append((living_rect, "LIVING CANVAS"))

        selfie_rect = pygame.Rect(start_x+card_w+gap_x, row2_y, card_w, card_h)
        pygame.draw.rect(surface, (12, 20, 50), selfie_rect, border_radius=18)
        pygame.draw.rect(surface, SELFIE_COLOR, selfie_rect, 2, border_radius=18)
        icon_x, icon_y = selfie_rect.x+42, selfie_rect.y+43
        pygame.draw.circle(surface, SELFIE_COLOR, (icon_x, icon_y), 17, 2)
        pygame.draw.circle(surface, SELFIE_COLOR, (icon_x, icon_y), 8, 2)
        pygame.draw.rect(surface, SELFIE_COLOR, pygame.Rect(icon_x+10, selfie_rect.y+24, 10, 6), border_radius=3)
        draw_text(surface, "SELFIE BOOTH", (selfie_rect.x+72, selfie_rect.y+22), 21, WHITE)
        draw_text(surface, "Filters • Frames • Photo Strip", (selfie_rect.x+22, selfie_rect.y+68), 14, MUTED)
        draw_text(surface, "POINT + PINCH TO OPEN", (selfie_rect.x+22, selfie_rect.bottom-27), 12, SELFIE_COLOR)
        self.buttons.append((selfie_rect, "SELFIE BOOTH"))

        bottom_y = h-48
        footer_buttons = [
            (w//2-250, "instructions", "INSTRUCTIONS", PURPLE),
            (w//2-75, "scores", "HIGH SCORES", CYAN),
            (w//2+100, "settings", "SETTINGS", MAGENTA),
            (w//2+260, "quit", "QUIT", WHITE),
        ]
        for x, name, label, color in footer_buttons:
            rect = pygame.Rect(x-60, bottom_y-15, 120, 34)
            pygame.draw.rect(surface, (16, 22, 45), rect, border_radius=8)
            pygame.draw.rect(surface, color, rect, 1, border_radius=8)
            draw_text(surface, label, rect.center, 14, WHITE, center=True)
            self.buttons.append((rect, name))

        if frame_data and frame_data.get("present"):
            px, py = int(frame_data.get("x", .5)*w), int(frame_data.get("y", .5)*h)
            pygame.draw.circle(surface, MAGENTA, (px, py), 15, 2)
            pygame.draw.circle(surface, CYAN, (px, py), 4)
            draw_text(surface, f"GESTURE: {frame_data.get('gesture', 'none').replace('_',' ').upper()}",
                      (w-175, 18), 13, CYAN, center=True)
