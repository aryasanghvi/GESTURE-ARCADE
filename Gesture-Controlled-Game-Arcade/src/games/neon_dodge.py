import random, pygame
from .base_game import BaseGame
from ..settings import CYAN, MAGENTA, PURPLE, WHITE, GREEN
from ..ui_components import draw_text

class NeonDodge(BaseGame):
    title="NEON DODGE"
    def __init__(self,w,h):
        super().__init__(w,h); self.player=pygame.Rect(w//2-17,h-110,34,44);self.obstacles=[];self.spawn=0;self.shield=0
    def update(self,dt,g,frame_data):
        super().update(dt,g,frame_data)
        if self.game_over or self.paused:return
        if g.get("present"): self.player.centerx=int(g["x"]*self.w)
        self.player.clamp_ip(pygame.Rect(0,0,self.w,self.h)); self.shield=max(0,self.shield-dt)
        self.spawn-=dt
        if self.spawn<=0:
            ww=random.randint(25,75); self.obstacles.append(pygame.Rect(random.randint(0,self.w-ww),-50,ww,random.randint(20,45)))
            self.spawn=max(.18,.72-self.elapsed*.008)
        for o in self.obstacles:o.y+=(230+self.elapsed*5)*dt
        for o in self.obstacles[:]:
            if o.top>self.h:self.obstacles.remove(o);self.score+=1
            elif o.colliderect(self.player):
                self.obstacles.remove(o)
                if self.shield<=0:self.lives-=1;self.effects.burst(self.player.centerx,self.player.centery,20,MAGENTA)
        if self.lives<=0:self.game_over=True
        if int(self.elapsed)%15==0 and self.elapsed>0:self.shield=max(self.shield,.3)
    def draw(self,screen):
        self.draw_background(screen)
        for o in self.obstacles:
            pygame.draw.rect(screen,PURPLE,o,border_radius=7)
            pygame.draw.rect(screen,CYAN,o,1,border_radius=7)
        color=GREEN if self.shield>0 else CYAN
        pygame.draw.rect(screen,color,self.player,border_radius=9)
        pygame.draw.line(screen,WHITE,(self.player.centerx,self.player.top+8),(self.player.centerx,self.player.bottom-8),3)
        self.hud(screen)
        draw_text(screen,f"SURVIVED {int(self.elapsed)}s",(self.w//2-50,48),18,WHITE)
