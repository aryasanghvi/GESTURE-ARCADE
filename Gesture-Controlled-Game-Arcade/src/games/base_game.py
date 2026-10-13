import pygame
from ..settings import BG, CYAN, WHITE, MUTED
from ..ui_components import draw_text
from ..effects import ParticleSystem

class BaseGame:
    title = "ARCADE GAME"
    def __init__(self, w, h):
        self.w,self.h=w,h
        self.score=0
        self.lives=3
        self.elapsed=0.0
        self.game_over=False
        self.paused=False
        self.effects=ParticleSystem()
        self.font=pygame.font.Font(None,24)
    def update(self, dt, gesture, frame_data):
        self.elapsed += dt
        self.effects.update(dt)
    def draw_background(self, screen):
        screen.fill(BG)
        self.effects.draw(screen)
    def hud(self, screen):
        draw_text(screen,self.title,(20,16),24,CYAN)
        draw_text(screen,f"SCORE {self.score}",(20,48),20,WHITE)
        draw_text(screen,f"LIVES {self.lives}",(self.w-135,18),20,WHITE)
        draw_text(screen,"ESC: pause/menu",(self.w-170,self.h-28),15,MUTED)
    def draw(self, screen):
        self.draw_background(screen); self.hud(screen)
