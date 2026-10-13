"""Living Canvas: a hand-controlled, stylized underwater aquarium.

All artwork is drawn with Pygame primitives, so the feature works offline and
needs no downloaded assets. It deliberately uses 2D layered art rather than
trying to simulate realistic water or 3D creatures.
"""
from __future__ import annotations

import math
import random
import pygame

from .settings import CYAN, PURPLE, MAGENTA, WHITE, MUTED, PANEL
from .ui_components import draw_text


NAVY = (5, 13, 38)
DEEP_BLUE = (5, 34, 66)
TEAL = (29, 191, 190)
AQUA = (91, 244, 232)
CORAL = (255, 104, 150)
GOLD = (255, 209, 105)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _glow_circle(surface, color, center, radius, strength=80):
    """Draw a soft, inexpensive multi-layer glow and a crisp center."""
    x, y = int(center[0]), int(center[1])
    radius = max(1, int(radius))
    glow = pygame.Surface((radius * 6 + 4, radius * 6 + 4), pygame.SRCALPHA)
    cx = cy = glow.get_width() // 2
    for scale, alpha in ((2.8, strength // 7), (2.1, strength // 5), (1.55, strength // 3)):
        pygame.draw.circle(glow, (*color, max(1, alpha)), (cx, cy), int(radius * scale))
    pygame.draw.circle(glow, (*color, 235), (cx, cy), radius)
    surface.blit(glow, (x - cx, y - cy))


class _Fish:
    def __init__(self, w, h, index, rng):
        self.rng = rng
        self.x = rng.uniform(0, w)
        self.y = rng.uniform(h * 0.18, h * 0.82)
        self.depth = rng.uniform(0.55, 1.15)
        self.size = rng.uniform(15, 30) * self.depth
        self.speed = rng.uniform(22, 60) * (1.15 - self.depth * 0.25)
        self.phase = rng.uniform(0, math.tau)
        self.direction = rng.choice((-1, 1))
        self.color = rng.choice([(57, 221, 235), (119, 135, 255), (255, 126, 179),
                                 (255, 202, 103), (94, 236, 185), (184, 130, 255)])
        self.rare = index < 5
        if self.rare:
            self.color = [(255, 214, 112), (255, 117, 174), (104, 244, 228),
                          (177, 143, 255), (255, 146, 99)][index]
            self.size *= 1.18
        # Rare fish can briefly shimmer when the player spots them. This is a
        # visual reaction only; there is no collection inventory or journal.
        self.spotlight_until = 0.0
        self.last_spotted_time = -100.0
        self.hover_time = 0.0
        self.flee_timer = 0.0
        self.flee_dx = 0.0
        self.flee_dy = 0.0

    def update(self, dt, w, h, cursor, feeding, t, discovery=False, cursor_speed=0.0):
        cx, cy = cursor if cursor else (-1000, -1000)
        dx, dy = self.x - cx, self.y - cy
        dist = math.hypot(dx, dy)

        if feeding and cursor and dist < 255:
            # Fish gather around the feeding zone without piling onto the cursor.
            target_x = cx + math.cos(self.phase) * (28 + self.size * 0.7)
            target_y = cy + math.sin(self.phase) * (20 + self.size * 0.45)
            ease = min(1.0, dt * 1.45)
            self.x += (target_x - self.x) * ease
            self.y += (target_y - self.y) * ease
        elif discovery and self.rare and cursor and dist < 150:
            # Rare fish become calm and easy to point at in Discovery Mode.
            # They hover around the cursor instead of fleeing from it.
            target_x = cx + math.cos(self.phase) * 34
            target_y = cy + math.sin(self.phase) * 23
            ease = min(1.0, dt * 1.15)
            self.x += (target_x - self.x) * ease
            self.y += (target_y - self.y) * ease
        elif cursor and dist < 155 and cursor_speed > 950:
            # Fast hand sweeps can still create a playful scatter reaction.
            length = max(1.0, dist)
            self.flee_dx, self.flee_dy = dx / length, dy / length
            self.flee_timer = 0.58
            self.x += self.flee_dx * self.speed * dt * 2.2
            self.y += self.flee_dy * self.speed * dt * 1.8
        elif self.flee_timer > 0:
            self.flee_timer = max(0.0, self.flee_timer - dt)
            self.x += self.flee_dx * self.speed * dt * 1.55
            self.y += self.flee_dy * self.speed * dt * 1.25
        elif cursor and dist < 165:
            # Slow pointer motion gently guides fish into a loose orbit.
            target_x = cx + math.cos(self.phase + t * 0.55) * (42 + self.size * 0.55)
            target_y = cy + math.sin(self.phase + t * 0.55) * (27 + self.size * 0.35)
            ease = min(1.0, dt * 0.82)
            self.x += (target_x - self.x) * ease
            self.y += (target_y - self.y) * ease
        else:
            self.x += self.direction * self.speed * dt
            self.y += math.sin(t * 1.3 + self.phase) * 9 * dt

        if self.x < -70:
            self.x = w + 60
        elif self.x > w + 70:
            self.x = -60
        self.y = _clamp(self.y, h * 0.16, h * 0.84)

    def draw(self, surface, t):
        x, y = int(self.x), int(self.y + math.sin(t * 2.2 + self.phase) * 2.5)
        s = self.size
        direction = self.direction
        body = [(x - direction*s, y), (x - direction*s*.48, y - s*.48),
                (x + direction*s*.5, y - s*.34), (x + direction*s, y),
                (x + direction*s*.5, y + s*.34), (x - direction*s*.48, y + s*.48)]
        # Rare fish have a soft baseline glow; spotted fish get a temporary halo.
        if self.rare:
            _glow_circle(surface, self.color, (x, y), int(s*.55), 70 if self.spotlight_until > 0 else 48)
        if self.spotlight_until > 0:
            pygame.draw.circle(surface, GOLD, (x, y), max(5, int(s * 1.02)), 2)
        tail = [(x - direction*s*.7, y), (x - direction*s*1.35, y - s*.38),
                (x - direction*s*1.3, y + s*.38)]
        pygame.draw.polygon(surface, tuple(int(c*.72) for c in self.color), tail)
        pygame.draw.polygon(surface, self.color, body)
        pygame.draw.ellipse(surface, tuple(min(255, c+30) for c in self.color),
                            pygame.Rect(int(x-direction*s*.24), int(y-s*.19), max(2,int(s*.38)), max(2,int(s*.38))))
        eye_x = int(x + direction*s*.53)
        pygame.draw.circle(surface, (6, 19, 43), (eye_x, y-int(s*.07)), max(1, int(s*.075)))
        pygame.draw.circle(surface, WHITE, (eye_x, y-int(s*.09)), max(1, int(s*.035)))


class _Jellyfish:
    def __init__(self, w, h, rng, index):
        self.x = rng.uniform(w*.08, w*.92)
        self.y = rng.uniform(h*.13, h*.65)
        self.size = rng.uniform(18, 31)
        self.phase = rng.uniform(0, math.tau)
        self.color = rng.choice([(94, 202, 255), (188, 122, 255), (255, 125, 205)])
        self.speed = rng.uniform(7, 15)

    def update(self, dt, w, h, t):
        self.y -= self.speed * dt
        self.x += math.sin(t*.45 + self.phase) * 7 * dt
        if self.y < -50:
            self.y = h + 35
            self.x = random.uniform(w*.08, w*.92)

    def draw(self, surface, t):
        x, y, r = int(self.x), int(self.y + math.sin(t*2+self.phase)*3), int(self.size)
        glow = pygame.Surface((r*5, r*5), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*self.color, 20), (r, r, r*3, r*2))
        pygame.draw.ellipse(glow, (*self.color, 38), (int(r*1.35), int(r*1.3), int(r*2.3), int(r*1.35)))
        surface.blit(glow, (x-glow.get_width()//2, y-r))
        # Draw the jellyfish on its own alpha layer; alpha on the display surface
        # itself would be ignored by Pygame and make the dome look like a solid blob.
        art = pygame.Surface((r*4, r*4), pygame.SRCALPHA)
        cx, cy = art.get_width()//2, r
        dome = pygame.Rect(cx-r, cy-r//2, r*2, int(r*1.5))
        pygame.draw.ellipse(art, (*self.color, 105), dome)
        pygame.draw.arc(art, (*self.color, 235), dome, math.pi, math.tau, 2)
        for i in range(4):
            tx = cx - r*.58 + i*r*.38
            sway = math.sin(t*2.0+self.phase+i)*4
            pygame.draw.lines(art, (*self.color, 175), False,
                              [(int(tx), cy+int(r*.25)), (int(tx+sway), cy+int(r*.8)),
                               (int(tx-sway*.45), cy+int(r*1.35))], 2)
        surface.blit(art, (x-cx, y-cy))


class LivingCanvas:
    """A no-assets-required aquarium with gesture and mouse fallback controls."""
    MODES = ("RELAX MODE", "DISCOVERY MODE")

    def __init__(self, width=1100, height=700, seed=None):
        self.width, self.height = width, height
        self.rng = random.Random(seed)
        self.time = 0.0
        self.mode = None
        self.view = "mode_menu"
        self.cursor = None
        self.hand_present = False
        self.feeding = False
        self.feeding_timer = 0.0
        self.bubbles = []
        self.particles = []
        self._last_cursor = None
        self._cursor_speed = 0.0
        self._bubble_emit_timer = 0.0
        self.fish = [_Fish(width, height, i, self.rng) for i in range(18)]
        self.jellies = [_Jellyfish(width, height, self.rng, i) for i in range(6)]
        self._background = None
        self._background_size = None
        self.mode_cards = []
        self.mode_button = pygame.Rect(0, 0, 0, 0)
        self.back_button = pygame.Rect(0, 0, 0, 0)
        self._hover_rare = None
        self._hover_rare_time = 0.0
        self._discovery_message = "Spot a rare fish to make it shimmer"
        self._discovery_message_time = 0.0

    def resize(self, width, height):
        if (width, height) != (self.width, self.height):
            self.width, self.height = width, height
            self._background = None
            self._background_size = None
            # Keep creatures on screen after a window resize.
            for fish in self.fish:
                fish.x = _clamp(fish.x, 0, width)
                fish.y = _clamp(fish.y, height*.16, height*.84)

    def _build_background(self):
        w, h = self.width, self.height
        bg = pygame.Surface((w, h))
        for y in range(h):
            p = y / max(1, h-1)
            col = tuple(int(NAVY[i]*(1-p) + DEEP_BLUE[i]*p) for i in range(3))
            pygame.draw.line(bg, col, (0, y), (w, y))
        # Soft shafts of light, drawn to an alpha layer.
        shafts = pygame.Surface((w, h), pygame.SRCALPHA)
        for i in range(7):
            x = int((i+.5)*w/7)
            points = [(x-20, 0), (x+15, 0), (x+int(w*.08), int(h*.75)), (x-int(w*.02), int(h*.75))]
            pygame.draw.polygon(shafts, (68, 219, 231, 10 if i%2 else 17), points)
        bg.blit(shafts, (0, 0))
        # Distant reef silhouette.
        reef = pygame.Surface((w, h), pygame.SRCALPHA)
        baseline = int(h*.89)
        points = [(0, h), (0, baseline)]
        for x in range(0, w+30, 30):
            y = baseline - int(22 + 15*math.sin(x*.024) + 9*math.sin(x*.071))
            points.append((x, y))
        points.extend([(w, h), (0, h)])
        pygame.draw.polygon(reef, (7, 48, 72, 245), points)
        # Coral branches in the foreground.
        for x, base, color, scale in [(int(w*.08),h,(29,111,129,220),1.0),
                                      (int(w*.25),h,(33,84,125,220),.8),
                                      (int(w*.78),h,(32,111,120,220),.95),
                                      (int(w*.94),h,(77,80,143,220),.75)]:
            self._draw_coral(reef, x, base, color, scale)
        # Sea grass silhouettes.
        for x in range(12, w, 48):
            height = 28 + (x*17 % 62)
            color = (15, 89, 103, 175)
            pygame.draw.lines(reef, color, False,
                             [(x, h), (x-9, h-height*.45), (x+5, h-height*.72), (x+1, h-height)], 3)
        bg.blit(reef, (0, 0))
        self._background = bg
        self._background_size = (w, h)

    @staticmethod
    def _draw_coral(surface, x, base, color, scale=1.0):
        branches = [((0,0),(-8,-34),(-19,-53)), ((0,-7),(10,-39),(8,-69)),
                    ((0,-17),(-25,-39),(-31,-66)), ((3,-27),(25,-50),(29,-82)),
                    ((0,-4),(2,-29),(-3,-48))]
        for a,b,c in branches:
            pts = [(int(x+a[0]*scale), int(base+a[1]*scale)),
                   (int(x+b[0]*scale), int(base+b[1]*scale)),
                   (int(x+c[0]*scale), int(base+c[1]*scale))]
            pygame.draw.lines(surface, color, False, pts, max(2,int(7*scale)))
            pygame.draw.circle(surface, color, pts[-1], max(2,int(4*scale)))

    def start_mode(self, mode):
        self.mode = mode
        self.view = "aquarium"
        self._hover_rare = None
        self._hover_rare_time = 0.0
        self._bubble_emit_timer = 0.0

    def handle_back(self):
        """Return to mode picker; return True when caller should exit to arcade."""
        if self.view == "aquarium":
            self.view = "mode_menu"
            self.mode = None
            self.feeding = False
            return False
        return True

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
            pos = event.pos
            if self.view == "mode_menu":
                for rect, mode in self.mode_cards:
                    if rect.collidepoint(pos):
                        self.start_mode(mode)
                        return "mode_selected"
            else:
                if self.mode_button.collidepoint(pos):
                    self.view = "mode_menu"
                    self.mode = None
                    self.feeding = False
                    return "mode_menu"
                # Mouse clicks and the controller's pinch-select event create a
                # satisfying burst. Holding a pinch also emits a continuous stream.
                self._spawn_bubbles(*pos, count=18)
        return None

    def _spawn_bubbles(self, x, y, count=16):
        for _ in range(count):
            if len(self.bubbles) >= 230:
                break
            radius = self.rng.choices([self.rng.uniform(2.5, 4.0), self.rng.uniform(4.0, 6.0),
                                       self.rng.uniform(6.0, 9.0)], weights=[5, 3, 1])[0]
            self.bubbles.append({
                "x": float(x + self.rng.uniform(-30, 30)),
                "y": float(y + self.rng.uniform(-18, 18)),
                "r": radius,
                "speed": self.rng.uniform(32, 86) * (1.2 - radius * 0.025),
                "drift": self.rng.uniform(-22, 22),
                "phase": self.rng.uniform(0, math.tau),
                "life": self.rng.uniform(2.4, 5.5), "max_life": 5.5,
            })

    def update(self, dt, gesture=None, frame_data=None):
        dt = min(max(float(dt), 0.0), .05)
        gesture = gesture or {}
        frame_data = frame_data or {}
        self.time += dt
        self.hand_present = bool(frame_data.get("present") or gesture.get("present"))
        previous_cursor = self.cursor
        if self.hand_present:
            self.cursor = (int(_clamp(float(gesture.get("x", frame_data.get("x", .5))), 0.0, 1.0) * self.width),
                           int(_clamp(float(gesture.get("y", frame_data.get("y", .5))), 0.0, 1.0) * self.height))
        else:
            self.cursor = None

        self._cursor_speed = 0.0
        if self.cursor and previous_cursor and dt > 0:
            dx = self.cursor[0] - previous_cursor[0]
            dy = self.cursor[1] - previous_cursor[1]
            distance = math.hypot(dx, dy)
            self._cursor_speed = distance / dt
            # A short-lived ribbon of bioluminescent particles follows moving hands.
            if distance > 2.5 and self.view == "aquarium":
                steps = min(6, max(1, int(distance / 13)))
                trail_colors = [(91, 244, 232), (81, 203, 229), (165, 132, 255), (255, 126, 202)]
                for i in range(steps):
                    if len(self.particles) >= 480:
                        break
                    ratio = (i + 1) / steps
                    self.particles.append({
                        "x": previous_cursor[0] + dx * ratio,
                        "y": previous_cursor[1] + dy * ratio,
                        "vx": self.rng.uniform(-13, 13), "vy": self.rng.uniform(-12, 12),
                        "life": self.rng.uniform(.35, .72), "max_life": .72,
                        "color": self.rng.choice(trail_colors), "r": self.rng.uniform(2, 4),
                        "trail": True,
                    })
        self._last_cursor = self.cursor

        gesture_name = gesture.get("gesture", "none")
        self.feeding = self.view == "aquarium" and gesture_name == "open_palm"
        if self.view == "aquarium" and gesture_name == "pinch" and self.cursor:
            # Continuous emission while pinching: roughly 12-18 bubbles per second.
            self._bubble_emit_timer += dt
            while self._bubble_emit_timer >= .075:
                self._bubble_emit_timer -= .075
                px, py = self.cursor
                self._spawn_bubbles(px, py, count=2)
        else:
            self._bubble_emit_timer = 0.0

        if self.feeding:
            self.feeding_timer += dt
            if self.rng.random() < dt * 10:
                px, py = self.cursor or (self.width // 2, self.height // 2)
                self._spawn_bubbles(px, py, count=3)
                # A few tiny glints make the feeding zone feel alive.
                if len(self.particles) < 480:
                    self.particles.append({"x": px + self.rng.uniform(-24, 24),
                                           "y": py + self.rng.uniform(-24, 24),
                                           "vx": self.rng.uniform(-12, 12), "vy": self.rng.uniform(-18, 3),
                                           "life": .45, "max_life": .45, "color": GOLD,
                                           "r": self.rng.uniform(1.5, 3)})
        else:
            self.feeding_timer = 0.0

        for fish in self.fish:
            fish.update(dt, self.width, self.height,
                        self.cursor if self.view == "aquarium" else None,
                        self.feeding, self.time, discovery=self.mode == "DISCOVERY MODE",
                        cursor_speed=self._cursor_speed)
            if fish.spotlight_until and self.time >= fish.spotlight_until:
                fish.spotlight_until = 0.0
        for jelly in self.jellies:
            jelly.update(dt, self.width, self.height, self.time)

        for b in self.bubbles:
            b["y"] -= b["speed"] * dt
            b["x"] += math.sin(self.time * 1.8 + b["phase"]) * b["drift"] * dt
            b["life"] -= dt
        self.bubbles = [b for b in self.bubbles if b["life"] > 0 and b["y"] > -20]

        for particle in self.particles:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]
        if self._discovery_message_time > 0:
            self._discovery_message_time = max(0, self._discovery_message_time - dt)
        if self.view == "aquarium" and self.mode == "DISCOVERY MODE" and self.cursor:
            self._update_discovery(dt)
        elif not self.cursor:
            self._hover_rare = None
            self._hover_rare_time = 0.0

    def _update_discovery(self, dt):
        """Temporarily spotlight rare fish under the cursor; never collect them."""
        nearest, nearest_dist = None, 62
        for fish in self.fish:
            if not fish.rare or self.time - fish.last_spotted_time < 2.8:
                fish.hover_time = 0.0
                continue
            distance = math.hypot(fish.x - self.cursor[0], fish.y - self.cursor[1])
            if distance < nearest_dist:
                nearest, nearest_dist = fish, distance
        if nearest is None:
            self._hover_rare = None
            self._hover_rare_time = 0.0
            return
        if nearest is not self._hover_rare:
            self._hover_rare = nearest
            self._hover_rare_time = 0.0
        self._hover_rare_time += dt
        nearest.hover_time = self._hover_rare_time
        if self._hover_rare_time >= .82:
            nearest.last_spotted_time = self.time
            nearest.spotlight_until = self.time + 2.1
            self._discovery_message = "Rare fish spotted!"
            self._discovery_message_time = 1.5
            for _ in range(30):
                if len(self.particles) >= 480:
                    break
                angle = self.rng.uniform(0, math.tau)
                speed = self.rng.uniform(22, 90)
                self.particles.append({
                    "x": nearest.x, "y": nearest.y,
                    "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                    "life": self.rng.uniform(.45, 1.05), "max_life": 1.05,
                    "color": nearest.color, "r": self.rng.uniform(2, 4.2),
                })
            self._hover_rare = None
            self._hover_rare_time = 0.0

    def _draw_bubbles(self, surface):
        for bubble in self.bubbles:
            fade = _clamp(bubble["life"] / .55, 0.0, 1.0)
            x, y = int(bubble["x"]), int(bubble["y"])
            radius = max(2, int(bubble["r"]))
            glow = (int(27 * fade), int(105 * fade), int(145 * fade))
            edge = (int(82 * fade + 35), int(190 * fade + 35), int(220 * fade + 35))
            pygame.draw.circle(surface, glow, (x, y), radius + 3, 1)
            pygame.draw.circle(surface, edge, (x, y), radius, 1)
            pygame.draw.arc(surface, (min(255, int(210 * fade + 35)),
                                      min(255, int(245 * fade + 10)), 255),
                            pygame.Rect(x-radius+1, y-radius+1, max(2, radius*2-2), max(2, radius*2-2)),
                            3.7, 5.2, 1)
            pygame.draw.circle(surface, (185, 249, 255),
                               (x - max(1, radius // 3), y - max(1, radius // 3)), 1)

    def _draw_particles(self, surface):
        for particle in self.particles:
            ratio = _clamp(particle["life"] / particle.get("max_life", 1.0), 0, 1)
            color = particle.get("color", AQUA)
            radius = max(1, int(particle.get("r", 3) * (.35 + .65 * ratio)))
            x, y = int(particle["x"]), int(particle["y"])
            # Two dimmed layers give particles a soft glow without expensive
            # per-particle image assets or full-screen blur operations.
            halo = tuple(int(channel * (.14 + .16 * ratio)) for channel in color)
            core = tuple(int(channel * (.45 + .55 * ratio)) for channel in color)
            pygame.draw.circle(surface, halo, (x, y), radius + 3)
            pygame.draw.circle(surface, core, (x, y), radius)

    def draw(self, surface):
        self.resize(*surface.get_size())
        w, h = self.width, self.height
        if self._background is None or self._background_size != (w,h):
            self._build_background()
        surface.blit(self._background, (0,0))
        # Distant drifting specks add depth without filling the screen with noise.
        for i in range(38):
            x = int((i*173 + math.sin(self.time*.23+i)*35) % w)
            y = int((i*97 + self.time*(7+i%4)*3) % h)
            pygame.draw.circle(surface, (35, 119, 155), (x,y), 1)
        for jelly in self.jellies:
            jelly.draw(surface, self.time)
        for fish in sorted(self.fish, key=lambda f: f.depth):
            fish.draw(surface, self.time)
        self._draw_bubbles(surface)
        self._draw_particles(surface)
        if self.view == "mode_menu":
            self._draw_mode_menu(surface)
        else:
            self._draw_hud(surface)
        if self.cursor and self.view == "aquarium":
            x, y = self.cursor
            col = GOLD if self.feeding else AQUA
            pulse = 16 + int(2 * math.sin(self.time * 4.0))
            _glow_circle(surface, col, (x, y), 4, 38)
            pygame.draw.circle(surface, col, (x, y), pulse, 1)
            pygame.draw.circle(surface, WHITE, (x, y), 3)
            if self.feeding:
                radius = int(30 + 10 * math.sin(self.time * 5))
                pygame.draw.circle(surface, col, (x, y), radius, 2)
                pygame.draw.circle(surface, (*col,), (x, y), radius + 9, 1)

    def _draw_mode_menu(self, surface):
        w, h = self.width, self.height
        shade = pygame.Surface((w,h), pygame.SRCALPHA)
        shade.fill((2, 8, 28, 125))
        surface.blit(shade, (0,0))
        draw_text(surface, "LIVING CANVAS", (w//2, int(h*.18)), 46, WHITE, center=True)
        draw_text(surface, "A living underwater world, controlled with your hands", (w//2, int(h*.18)+42), 19, AQUA, center=True)
        card_w, card_h = min(360, int(w*.38)), 210
        gap = 28
        left = (w - (card_w*2+gap))//2
        top = int(h*.32)
        self.mode_cards = []
        for i, mode in enumerate(self.MODES):
            rect = pygame.Rect(left+i*(card_w+gap), top, card_w, card_h)
            self.mode_cards.append((rect, mode))
            accent = AQUA if i == 0 else (255, 202, 105)
            hovered = bool(self.cursor and rect.collidepoint(self.cursor))
            pygame.draw.rect(surface, (7, 25, 58), rect, border_radius=22)
            if hovered:
                pygame.draw.rect(surface, accent, rect.inflate(8, 8), 1, border_radius=25)
            pygame.draw.rect(surface, (*accent,), rect, 3 if hovered else 2, border_radius=22)
            # Mini aquarium vignette.
            inner = pygame.Rect(rect.x+15, rect.y+15, rect.w-30, 88)
            pygame.draw.rect(surface, (5, 43, 73), inner, border_radius=14)
            for j in range(7):
                bx = inner.x+25+j*max(1,(inner.w-50)//6)
                by = inner.y+22+(j*17)%47
                pygame.draw.circle(surface, (*accent,), (bx,by), 2+(j%2))
            pygame.draw.ellipse(surface, accent, pygame.Rect(inner.x+inner.w//2-19,inner.y+28,38,20), 2)
            pygame.draw.polygon(surface, accent, [(inner.x+inner.w//2-19,inner.y+38),(inner.x+inner.w//2-30,inner.y+29),(inner.x+inner.w//2-30,inner.y+47)])
            title = "Relax Mode" if i == 0 else "Discovery Mode"
            desc = "Guide fish, bubbles, glowing trails" if i == 0 else "Spot rare fish and reveal their glow"
            draw_text(surface, title, (rect.centerx, rect.y+126), 25, WHITE, center=True)
            draw_text(surface, desc, (rect.centerx, rect.y+158), 15, MUTED, center=True)
            draw_text(surface, "POINT + PINCH TO SELECT", (rect.centerx, rect.y+187), 13, accent, center=True)
        draw_text(surface, "POINT to aim  •  PINCH to select  •  FIST to go back", (w//2, int(h*.78)), 18, WHITE, center=True)
        draw_text(surface, "Move your hand to explore the world", (w//2, int(h*.78)+28), 15, MUTED, center=True)

    def _draw_hud(self, surface):
        w, h = self.width, self.height
        mode_label = "RELAX MODE" if self.mode == "RELAX MODE" else "DISCOVERY MODE"
        draw_text(surface, "LIVING CANVAS", (24, 20), 23, WHITE)
        draw_text(surface, mode_label, (25, 49), 13, AQUA if self.mode == "RELAX MODE" else GOLD)
        # The mode icon is a deliberate point-and-pinch target, avoiding another gesture.
        self.mode_button = pygame.Rect(w-202, 18, 178, 43)
        hovering_mode = bool(self.cursor and self.mode_button.collidepoint(self.cursor))
        pygame.draw.rect(surface, (7, 25, 58), self.mode_button, border_radius=12)
        pygame.draw.rect(surface, AQUA, self.mode_button, 3 if hovering_mode else 1, border_radius=12)
        draw_text(surface, "CHANGE MODE", self.mode_button.center, 15, WHITE, center=True)
        self.back_button = pygame.Rect(24, h-61, 190, 36)
        pygame.draw.rect(surface, (7, 25, 58), self.back_button, border_radius=10)
        pygame.draw.rect(surface, (89, 133, 173), self.back_button, 1, border_radius=10)
        draw_text(surface, "FIST: BACK TO MODES", self.back_button.center, 13, WHITE, center=True)
        if self.mode == "RELAX MODE":
            hint = "POINT: gently guide fish   •   PINCH: bubble stream   •   OPEN PALM: feeding zone"
            draw_text(surface, hint, (w//2, h-30), 15, WHITE, center=True)
        else:
            draw_text(surface, "Hold over a rare fish to reveal a temporary glow", (w//2, h-32), 14, WHITE, center=True)
            if self._hover_rare and self._hover_rare_time > 0:
                fish = self._hover_rare
                bar = pygame.Rect(int(fish.x - fish.size), int(fish.y - fish.size - 16),
                                  max(18, int(fish.size * 2)), 5)
                pygame.draw.rect(surface, (24, 42, 68), bar, border_radius=3)
                pygame.draw.rect(surface, GOLD,
                                 pygame.Rect(bar.x, bar.y,
                                             int(bar.w * _clamp(self._hover_rare_time / .82, 0, 1)), bar.h),
                                 border_radius=3)
        if self._discovery_message_time > 0:
            draw_text(surface, self._discovery_message, (w//2, 95), 22, GOLD, center=True)
