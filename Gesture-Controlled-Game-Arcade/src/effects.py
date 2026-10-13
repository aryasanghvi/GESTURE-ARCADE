import random
import pygame
from .settings import CYAN, PURPLE, MAGENTA

class Starfield:
    def __init__(self, w, h, count=90):
        self.w, self.h = w, h
        self.stars = [[random.randrange(w), random.randrange(h), random.uniform(18, 90)] for _ in range(count)]
    def update(self, dt):
        for star in self.stars:
            star[1] += star[2] * dt
            if star[1] > self.h:
                star[0], star[1] = random.randrange(self.w), 0
    def draw(self, surface):
        for x, y, speed in self.stars:
            shade = min(255, int(100 + speed * 1.5))
            pygame.draw.circle(surface, (shade//2, shade//1, min(255, shade+25)), (int(x), int(y)), 1 if speed < 50 else 2)

class Particle:
    def __init__(self, x, y, color=None):
        self.x, self.y = float(x), float(y)
        self.vx, self.vy = random.uniform(-180,180), random.uniform(-220,100)
        self.life = self.max_life = random.uniform(.25,.7)
        self.color = color or random.choice([CYAN, PURPLE, MAGENTA])
        self.radius = random.randint(2,5)
    def update(self, dt):
        self.x += self.vx*dt; self.y += self.vy*dt
        self.vy += 300*dt; self.life -= dt
    def draw(self, surface):
        if self.life > 0:
            pygame.draw.circle(surface, self.color, (int(self.x),int(self.y)), max(1,int(self.radius*self.life/self.max_life)))

class ParticleSystem:
    def __init__(self, limit=450):
        self.items=[]; self.limit=limit
    def burst(self, x, y, count=18, color=None):
        for _ in range(count):
            if len(self.items) < self.limit: self.items.append(Particle(x,y,color))
    def update(self, dt):
        for p in self.items: p.update(dt)
        self.items = [p for p in self.items if p.life > 0]
    def draw(self, surface):
        for p in self.items: p.draw(surface)
