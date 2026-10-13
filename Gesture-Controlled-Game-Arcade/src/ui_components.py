import pygame
from .settings import WHITE, CYAN, PANEL, PURPLE

def draw_text(surface, text, pos, size=22, color=WHITE, center=False, font=None):
    font = font or pygame.font.Font(None, size)
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surface.blit(image, rect)
    return rect

class Button:
    def __init__(self, rect, label, accent=CYAN):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.accent = accent
    def draw(self, surface, hover=False):
        color = self.accent if hover else (55, 70, 105)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=12)
        pygame.draw.rect(surface, color, self.rect, width=2, border_radius=12)
        draw_text(surface, self.label, self.rect.center, 22, WHITE, center=True)
    def hit(self, pos):
        return self.rect.collidepoint(pos)
