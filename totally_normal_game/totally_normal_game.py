#!/usr/bin/env python3
"""
TOTALLY NORMAL GAME
A platformer where absolutely nothing weird happens. (Everything weird happens.)

Install:  pip install pygame-ce
Run:      python totally_normal_game.py

Controls: A/D or arrows to move, W / Up / Space to jump
          ESC = pause, R = restart level (counts as a death, obviously)

Everything happens inside the game window. The real window close button always works.
"""
import array
import math
import random
import sys

import pygame as pg

# ----------------------------------------------------------------- constants
W, H = 960, 540
T = 30                      # tile size
COLS, ROWS = 32, 18
FPS = 60
SPEED, GRAV, JUMP = 260, 2000, 720
PW, PH = 22, 28             # player size
TITLE = "Totally Normal Game"

SOLID = set("#IC=")         # '#' ground, 'I' invisible block, 'C' crumble, '=' bricks
GROUNDISH = set("#XC")      # tiles drawn as ground ('X' = fake ground, not solid)

KEYS_LEFT = (pg.K_a, pg.K_LEFT)
KEYS_RIGHT = (pg.K_d, pg.K_RIGHT)
KEYS_JUMP = (pg.K_w, pg.K_UP, pg.K_SPACE)
KEYS_DOWN = (pg.K_s, pg.K_DOWN)

DEATH_LINES = [
    "Skill issue.", "Wow.", "That was on purpose, right?", "The floor sends its regards.",
    "Have you tried not dying?", "Torgrim laughs from below.", "Oof.", "Git gud.",
    "Nice try!", "You died. Again.", "Certified bruh moment.", "Was that a speedrun strat?",
    "I felt that one.", "Bold strategy.", "Mikkel is disappointed.",
]

C_SKY_TOP = (110, 180, 255)
C_SKY_BOT = (205, 236, 255)
C_DIRT = (140, 86, 46)
C_DIRT_DARK = (112, 66, 34)
C_GRASS = (88, 196, 74)
C_GRASS_HI = (140, 232, 104)
C_BRICK = (200, 96, 58)
C_MORTAR = (122, 52, 30)
C_PLAYER = (255, 210, 63)
C_INK = (25, 20, 30)
C_WHITE = (255, 255, 255)
C_YELLOW = (255, 230, 60)
C_RED = (230, 50, 50)


# ----------------------------------------------------------------- sound
class Sfx:
    """Tiny synth: every sound is generated in code, so no asset files are needed."""

    def __init__(self):
        self.ok = False
        self.snd = {}
        try:
            pg.mixer.init(22050, -16, 1, 512)
            rate, _, channels = pg.mixer.get_init()

            def tone(freq, dur, vol=0.22, wave="sq", slide=1.0):
                n = int(rate * dur)
                buf = array.array("h")
                phase = 0.0
                for i in range(n):
                    k = i / n
                    phase += freq * (slide ** k) / rate
                    if wave == "sq":
                        v = 1.0 if phase % 1 < 0.5 else -1.0
                    elif wave == "sin":
                        v = math.sin(phase * 2 * math.pi)
                    else:
                        v = random.uniform(-1, 1)
                    s = int(v * vol * (1 - k) * 32767)
                    buf.append(s)
                    if channels == 2:
                        buf.append(s)
                return pg.mixer.Sound(buffer=buf.tobytes())

            self.snd = {
                "jump": tone(420, 0.12, 0.16, "sq", 2.0),
                "die": tone(320, 0.5, 0.22, "sq", 0.2),
                "hop": tone(700, 0.16, 0.18, "sin", 1.9),
                "pop": tone(900, 0.08, 0.2, "sq", 0.5),
                "win": tone(520, 0.55, 0.18, "sq", 2.2),
                "crash": tone(80, 0.7, 0.3, "noise"),
                "bonk": tone(200, 0.1, 0.25, "sq", 0.6),
                "click": tone(1000, 0.05, 0.15, "sq"),
                "crumble": tone(150, 0.25, 0.2, "noise"),
                "warn": tone(1200, 0.1, 0.12, "sin"),
                "talk": tone(600, 0.03, 0.05, "sq"),
            }
            self.ok = True
        except Exception:
            self.ok = False

    def play(self, name):
        if self.ok and name in self.snd:
            self.snd[name].play()


# ----------------------------------------------------------------- entities
class Player:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.on = False
        self.coyote = 0.0
        self.buffer = 0.0
        self.face = 1
        self.dead = False
        self.squash = 0.0

    def rect(self):
        return pg.Rect(round(self.x), round(self.y), PW, PH)

    @property
    def cx(self):
        return self.x + PW / 2


class Flag:
    """A goal flag that can run away. spots = [(col, row, trigger)], trigger is
    'near' (hop when the player gets close), a number (hop after N seconds),
    'stay' (finally stays put) or 'fake' (the level decides what happens)."""

    def __init__(self, game, spots, msgs=()):
        self.g = game
        self.spots = spots
        self.msgs = list(msgs)
        self.i = 0
        c, r, _ = spots[0]
        self.x, self.y = c * T + T / 2, (r + 1) * T
        self.anim = None
        self.wait = 0.0

    def trigger(self):
        return self.spots[self.i][2]

    def update(self, dt, p):
        if self.anim:
            a = self.anim
            a["t"] += dt
            k = min(1.0, a["t"] / a["d"])
            self.x = a["x0"] + (a["x1"] - a["x0"]) * k
            self.y = a["y0"] + (a["y1"] - a["y0"]) * k - math.sin(k * math.pi) * a["h"]
            if k >= 1:
                self.anim = None
                self.wait = 0.0
            return
        self.wait += dt
        trig = self.trigger()
        go = False
        if trig == "near":
            go = abs(p.cx - self.x) < 110 and abs(p.y + PH - self.y) < 100
        elif isinstance(trig, (int, float)):
            go = self.wait >= trig
        if go and self.i + 1 < len(self.spots):
            self.hop()

    def hop(self):
        if self.i < len(self.msgs) and self.msgs[self.i]:
            self.g.say(self.msgs[self.i])
        self.i += 1
        c, r, _ = self.spots[self.i]
        x1, y1 = c * T + T / 2, (r + 1) * T
        dist = math.hypot(x1 - self.x, y1 - self.y)
        self.anim = {"t": 0.0, "d": 0.5 + dist / 1500, "x0": self.x, "y0": self.y,
                     "x1": x1, "y1": y1, "h": 80 + dist * 0.15}
        self.g.sfx.play("hop")

    def touching(self, p):
        return self.anim is None and p.rect().colliderect(pg.Rect(self.x - 4, self.y - 96, 30, 96))

    def draw(self, surf, t):
        x, y = int(self.x), int(self.y)
        pg.draw.rect(surf, (90, 90, 100), (x - 8, y - 6, 16, 6))
        pg.draw.line(surf, (235, 235, 240), (x, y - 6), (x, y - 96), 4)
        pg.draw.circle(surf, C_YELLOW, (x, y - 98), 5)
        wave = math.sin(t * 6) * 4
        pg.draw.polygon(surf, C_RED, [(x + 2, y - 94), (x + 36, y - 82 + wave), (x + 2, y - 68)])
        pg.draw.polygon(surf, (150, 20, 20), [(x + 2, y - 94), (x + 36, y - 82 + wave), (x + 2, y - 68)], 2)


# ----------------------------------------------------------------- levels
class Level:
    name = "?"
    intro = ""

    def __init__(self, game):
        self.g = game
        self.phase = 0
        self.deaths = 0
        self.said = set()
        self.start = (2, 14)
        self.reset()

    # --- building helpers
    def reset(self):
        self.grid = [["." for _ in range(COLS)] for _ in range(ROWS)]
        self.revealed = set()
        self.popped = {}
        self.crumble = {}
        self.debris = []
        self.falling = []
        self.flag = None
        self.t = 0.0
        self.build()

    def fill(self, c0, r0, c1, r1, ch):
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if 0 <= r < ROWS and 0 <= c < COLS:
                    self.grid[r][c] = ch

    def floor(self, c0=0, c1=COLS - 1):
        self.fill(c0, 15, c1, 17, "#")

    def once(self, key, text):
        if key not in self.said:
            self.said.add(key)
            self.g.say(text)

    def spawn(self):
        c, r = self.start
        return c * T + (T - PW) / 2, (r + 1) * T - PH

    # --- hooks for each level
    def build(self):
        pass

    def extras(self):
        """Extra solid rects (things that are not tiles)."""
        return []

    def update(self, dt, p):
        pass

    def hazard(self, p):
        return False

    def on_flag(self):
        return True

    def on_death(self):
        return None

    def draw_extra(self, surf):
        pass


class L1(Level):
    name = "The Tutorial"
    intro = "Welcome! Walk to the flag. That's literally it."

    def build(self):
        self.floor()
        self.flag = Flag(self.g, [(28, 14, "near"), (30, 14, "near"), (12, 14, "near"), (26, 14, "stay")],
                         ["Huh. Must be windy.", "Hey! Come back here!", "...the flag is a bit shy.",
                          "Okay. The flag is tired now. Go on."])


class L2(Level):
    name = "Trust the Floor"
    intro = "The floor is 100% safe. Trust me."

    def build(self):
        self.floor()
        self.fill(10, 15, 15, 17, "X")      # looks like floor, is not floor
        self.fill(9, 12, 16, 12, "=")       # the honest route
        self.fill(21, 15, 23, 15, "C")      # crumbling bridge
        self.fill(21, 16, 23, 17, ".")
        self.flag = Flag(self.g, [(28, 14, "stay")])

    def on_death(self):
        return {1: "Okay, 99% safe.", 3: "Pro tip: things above you exist."}.get(self.deaths)


class L3(Level):
    name = "Leap of Faith"
    intro = "This gap is impossible. Don't even try."

    def build(self):
        self.floor(0, 10)
        self.floor(20, 31)
        self.fill(11, 17, 19, 17, "^")
        self.fill(14, 14, 16, 14, "I")      # invisible stepping stone
        self.grid[14][25] = "h"             # hidden spike
        self.flag = Flag(self.g, [(29, 14, "stay")])

    def update(self, dt, p):
        if any(r == 14 for (c, r) in self.revealed):
            self.once("found", "...wait. How did you know about that?!")

    def on_death(self):
        return {2: "Told you. Impossible.", 4: "Sometimes you just have to believe."}.get(self.deaths)


class L4(Level):
    name = "New Controls"
    intro = "Just jump over the spikes. Normal controls. Totally normal."

    def build(self):
        self.floor()
        for c in (9, 16, 24):
            self.grid[14][c] = "^"
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.stage = 0

    def update(self, dt, p):
        if self.stage == 0 and p.cx > 12 * T:
            self.stage = 1
            self.g.ctrl = "invert"
            self.g.say("CONTROLS UPDATED for your convenience.")
            self.g.sfx.play("warn")
        elif self.stage == 1 and p.cx > 20.5 * T:
            self.stage = 2
            self.g.ctrl = "jumpdown"
            self.g.say("Fixed it! Oh, and jump is on S / Down now. You're welcome.")
            self.g.sfx.play("warn")


class L5(Level):
    name = "You Win!"
    intro = "Last level! Touch the flag to beat the whole game!"

    def build(self):
        self.floor()
        if self.phase < 2:
            self.start = (2, 14)
            self.flag = Flag(self.g, [(28, 14, "fake")])
        else:
            self.start = (27, 14)
            self.flag = Flag(self.g, [(2, 14, "stay")])
        self.drop_t = 1.2

    def on_flag(self):
        if self.phase == 0:
            self.phase = 1
            self.g.begin("fakewin")
            return False
        return self.phase == 2

    def after_fakewin(self):
        self.phase = 2
        self.g.respawn()
        self.g.say("...wait. That was the FAKE flag. The real one is back at the start. RUN!")

    def update(self, dt, p):
        if self.phase != 2:
            return
        self.drop_t -= dt
        if self.drop_t <= 0:
            self.drop_t = 0.5 + random.random() * 0.25
            aim = p.cx + p.vx * 0.35 + random.uniform(-45, 45)
            c = max(0, min(COLS - 1, int(aim // T)))
            self.falling.append({"x": c * T, "y": -T, "warn": 0.45, "vy": 0.0})
            self.g.sfx.play("warn")
        for b in self.falling:
            if b["warn"] > 0:
                b["warn"] -= dt
                continue
            b["vy"] = min(1100, b["vy"] + 2600 * dt)
            b["y"] += b["vy"] * dt
            if b["y"] + T >= 15 * T:
                b["dead"] = True
                self.g.burst(b["x"] + T / 2, 15 * T - 4, 14, [C_BRICK, C_MORTAR, (240, 200, 160)])
                self.g.sfx.play("crumble")
        self.falling = [b for b in self.falling if not b.get("dead")]

    def hazard(self, p):
        pr = p.rect().inflate(-4, -4)
        return any(b["warn"] <= 0 and pr.colliderect(pg.Rect(b["x"], b["y"], T, T)) for b in self.falling)

    def draw_extra(self, surf):
        for b in self.falling:
            if b["warn"] > 0:
                if int(b["warn"] * 20) % 2 == 0:
                    pg.draw.rect(surf, C_RED, (b["x"] + 4, 15 * T - 6, T - 8, 5))
                    self.g.text("!", 34, C_RED, (b["x"] + T / 2, 22))
            else:
                self.g.draw_brick(surf, int(b["x"]), int(b["y"]))


class L6(Level):
    name = "The Honest Level"
    intro = "No tricks this time. I promise."

    def build(self):
        self.floor()
        self.fill(8, 12, 11, 12, "=")
        self.fill(15, 10, 18, 10, "=")
        self.fill(22, 12, 25, 12, "=")
        self.flag = Flag(self.g, [(29, 14, "stay")])

    def update(self, dt, p):
        if p.cx > 9 * T:
            self.once("dots", "...")
        if p.cx > 20 * T:
            self.once("slow", "Why are you walking so carefully? There are no traps.")

    def on_flag(self):
        self.g.say("See? I don't ALWAYS lie.")
        return True

    def draw_extra(self, surf):
        # a very suspicious sign that does absolutely nothing
        x, y = 13 * T, 15 * T
        pg.draw.rect(surf, (110, 70, 40), (x + 12, y - 44, 6, 44))
        pg.draw.rect(surf, (230, 200, 140), (x - 34, y - 70, 98, 30))
        pg.draw.rect(surf, (110, 70, 40), (x - 34, y - 70, 98, 30), 2)
        self.g.text("DEFINITELY", 16, C_INK, (x + 15, y - 62))
        self.g.text("A TRAP  >", 16, C_RED, (x + 15, y - 49))
        # a '?' block that gives you nothing
        self.g.text("?", 30, C_YELLOW, (16.5 * T, 10.5 * T), shadow=True)


class L7(Level):
    name = "Loading Bridge"
    intro = "Please wait while we load the bridge."

    def build(self):
        self.floor(0, 7)
        self.floor(24, 31)
        self.fill(8, 17, 23, 17, "^")
        self.flag = Flag(self.g, [(28, 14, "stay")])
        self.progress = 0.0
        self.bstate = "load"
        self.btimer = 0.0

    def update(self, dt, p):
        if self.bstate == "load":
            self.progress = min(0.99, self.progress + dt / 5.5)
            if self.progress >= 0.99:
                self.bstate, self.btimer = "stall", 2.0
                self.once("99", "Almost there... 99%!")
        elif self.bstate == "stall":
            self.btimer -= dt
            if self.btimer <= 0:
                self.bstate = "back"
                self.once("oops", "Oops. Error 404: bridge not found. Reverting to backup.")
                self.g.sfx.play("warn")
        elif self.bstate == "back":
            self.progress -= dt / 1.3
            if self.progress <= 0.2:
                self.progress, self.bstate = 0.2, "load"
                self.once("again", "Loading again. Please be patient. Patience is a virtue.")

    def bridge(self):
        return pg.Rect(8 * T, 15 * T, int(16 * T * self.progress), 14)

    def extras(self):
        return [self.bridge()]

    def draw_extra(self, surf):
        b = self.bridge()
        pg.draw.rect(surf, (40, 40, 50), (8 * T, 15 * T, 16 * T, 14), 2)
        if b.width > 0:
            pg.draw.rect(surf, (60, 200, 90), b)
            for x in range(b.left, b.right, 16):
                pg.draw.rect(surf, (110, 235, 130), (x + 2, b.top + 3, 8, 4))
        pct = int(self.progress * 100)
        label = f"LOADING BRIDGE... {pct}%"
        if self.bstate == "back":
            label = f"UNLOADING BRIDGE... {pct}%"
        self.g.text(label, 26, C_INK, (W / 2, 15 * T - 34), shadow=False)


class L8(Level):
    name = "The Button"
    intro = "Whatever you do, do NOT press the red button."

    def build(self):
        self.floor()
        if not self.phase:
            self.fill(21, 4, 21, 14, "=")
        self.button = pg.Rect(11 * T + 3, 15 * T - 10, 24, 10)
        self.flag = Flag(self.g, [(28, 14, "stay")])
        self.lines = [(5, "The flag is right there. Just go around the wall."),
                      (11, "There is no way around. But DON'T press the button."),
                      (18, "...I can see you thinking about it."),
                      (26, "Fine. Stand there forever. See if I care.")]

    def update(self, dt, p):
        self.t += dt
        if self.phase:
            return
        for sec, line in self.lines:
            if self.t >= sec:
                self.once(line, line)
        if p.rect().colliderect(self.button):
            self.phase = 1
            self.g.sfx.play("click")
            self.g.begin("crash")

    def after_crash(self):
        for r in range(4, 15):
            self.grid[r][21] = "."
            self.g.burst(21 * T + T / 2, r * T + T / 2, 5, [C_BRICK, C_MORTAR])
        self.g.say("JUST KIDDING. You pressed it anyway. The wall is gone. Happy now?")

    def draw_extra(self, surf):
        b = self.button
        pg.draw.rect(surf, (120, 120, 130), (b.x - 4, b.bottom - 5, b.w + 8, 5))
        h = 3 if self.phase else 9
        pg.draw.ellipse(surf, C_RED, (b.x, b.bottom - 5 - h, b.w, h * 2))
        pg.draw.rect(surf, (230, 220, 200), (b.centerx - 50, b.top - 50, 100, 26))
        pg.draw.rect(surf, C_INK, (b.centerx - 50, b.top - 50, 100, 26), 2)
        self.g.text("DO NOT PRESS", 18, C_RED, (b.centerx, b.top - 37), shadow=False)


class L9(Level):
    name = "The Finale"
    intro = "Okay. This is the REAL final level. Good luck."

    def build(self):
        self.floor()
        self.fill(6, 15, 9, 17, "X")
        self.fill(5, 12, 10, 12, "=")
        self.grid[14][14] = "h"
        self.grid[12][15] = "I"
        self.fill(18, 15, 21, 17, ".")
        self.fill(18, 15, 21, 15, "C")
        self.fill(18, 17, 21, 17, "^")
        self.flag = Flag(self.g, [(25, 14, "near"), (30, 14, "near"), (28, 6, 1.8), (23, 14, "stay")],
                         ["Nope.", "Up here! Come and get me!", "Fine. FINAL flag. For real this time."])

    def on_death(self):
        return {1: "You fell for the floor thing. AGAIN?"}.get(self.deaths)


LEVELS = [L1, L2, L3, L4, L5, L6, L7, L8, L9]


# ----------------------------------------------------------------- game
class Game:
    def __init__(self):
        pg.init()
        self.sfx = Sfx()
        self.screen = pg.display.set_mode((W, H))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.fonts = {}
        self.state = "menu"
        self.state_t = 0.0
        self.deaths = 0
        self.time = 0.0
        self.t = 0.0
        self.li = 0
        self.level = None
        self.p = None
        self.ctrl = "normal"
        self.dead_t = 0.0
        self.parts = []
        self.msg, self.msg_t = "", 0.0
        self.banner, self.banner_t = "", 0.0
        self.caption_t = 0.0
        self.play_btn = pg.Rect(380, 290, 200, 56)
        self.quit_btn = pg.Rect(380, 370, 200, 50)
        self.dodges = 3
        self.menu_quip = ""
        self.quit_armed = False
        self.load_skip = False
        self.sky = self._make_sky()
        self.clouds = [[random.uniform(0, W), random.uniform(30, 250), random.uniform(0.6, 1.4)] for _ in range(7)]
        self.speck = [[(random.randrange(2, T - 4), random.randrange(10, T - 4)) for _ in range(4)] for _ in range(5)]

    # ------------------------------------------------ helpers
    def _make_sky(self):
        s = pg.Surface((W, H))
        for y in range(H):
            k = y / H
            col = [int(C_SKY_TOP[i] + (C_SKY_BOT[i] - C_SKY_TOP[i]) * k) for i in range(3)]
            pg.draw.line(s, col, (0, y), (W, y))
        return s

    def font(self, size):
        if size not in self.fonts:
            self.fonts[size] = pg.font.Font(None, size)
        return self.fonts[size]

    def text(self, txt, size, col, pos, anchor="center", shadow=True, surf=None):
        surf = surf or self.screen
        f = self.font(size)
        img = f.render(txt, True, col)
        r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        if shadow:
            sh = f.render(txt, True, (0, 0, 0))
            surf.blit(sh, r.move(2, 2))
        surf.blit(img, r)
        return r

    def say(self, text):
        self.msg, self.msg_t = text, 0.0

    def burst(self, x, y, n, cols, speed=260, life=0.7, size=4, grav=900):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = speed * random.uniform(0.3, 1.0)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 120, life, life,
                               random.choice(cols), size, grav])

    def keys(self):
        return pg.key.get_pressed()

    def jump_keys(self):
        return KEYS_DOWN if self.ctrl == "jumpdown" else KEYS_JUMP

    def begin(self, state):
        self.state, self.state_t = state, 0.0
        if state == "crash":
            self.sfx.play("crash")
            pg.display.set_caption(TITLE + " (Not Responding)")
        if state == "fakewin":
            self.sfx.play("win")

    # ------------------------------------------------ flow
    def start_game(self):
        self.deaths, self.time, self.li = 0, 0.0, 0
        self.load_level()

    def load_level(self):
        self.level = LEVELS[self.li](self)
        self.respawn()
        self.banner, self.banner_t = f"LEVEL {self.li + 1}: {self.level.name}", 2.4
        self.state, self.state_t = "play", 0.0
        if self.level.intro:
            self.say(self.level.intro)

    def respawn(self):
        self.ctrl = "normal"
        self.level.reset()
        x, y = self.level.spawn()
        self.p = Player(x, y)

    def kill(self):
        p = self.p
        if p is None or p.dead or self.state != "play":
            return
        p.dead = True
        self.dead_t = 0.9
        self.deaths += 1
        self.level.deaths += 1
        self.burst(p.cx, p.y + PH / 2, 36, [C_PLAYER, (255, 150, 40), C_WHITE, C_RED], 340, 0.9, 5)
        self.sfx.play("die")
        self.say(self.level.on_death() or random.choice(DEATH_LINES))
        if self.deaths % 10 == 0:
            pg.display.set_caption(TITLE + " (Not Responding)")
            self.caption_t = 2.5

    # ------------------------------------------------ events
    def handle(self, e):
        if e.type == pg.QUIT:
            pg.quit()
            sys.exit()
        st = self.state
        if st == "menu":
            if e.type == pg.MOUSEMOTION and self.dodges > 0 and self.play_btn.collidepoint(e.pos):
                self.dodge(e.pos)
            elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                if self.play_btn.collidepoint(e.pos):
                    self.sfx.play("click")
                    self.begin("loading")
                elif self.quit_btn.collidepoint(e.pos):
                    self.sfx.play("click")
                    if self.quit_armed:
                        pg.quit()
                        sys.exit()
                    self.quit_armed = True
            elif e.type == pg.KEYDOWN and e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_KP_ENTER):
                self.begin("loading")
        elif st == "loading":
            if e.type == pg.KEYDOWN or e.type == pg.MOUSEBUTTONDOWN:
                self.load_skip = True
        elif st == "play":
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_ESCAPE:
                    self.state = "pause"
                elif e.key == pg.K_r and not self.p.dead:
                    self.kill()
                    self.say("Restarting counts as a death. Obviously.")
                elif e.key in self.jump_keys():
                    self.p.buffer = 0.13
                elif self.ctrl == "jumpdown" and e.key in KEYS_JUMP:
                    self.level.once("wjump", "That's not jump anymore. Keep up.")
        elif st == "pause":
            if e.type == pg.KEYDOWN:
                if e.key in (pg.K_ESCAPE, pg.K_p):
                    self.state = "play"
                elif e.key == pg.K_q:
                    self.to_menu()
                elif e.key == pg.K_r:
                    self.state = "play"
                    self.kill()
        elif st in ("fakewin", "crash"):
            if (e.type == pg.KEYDOWN or e.type == pg.MOUSEBUTTONDOWN) and self.state_t > 1.2:
                self.state_t = max(self.state_t, 2.9)
        elif st == "end":
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_r:
                    self.start_game()
                elif e.key in (pg.K_ESCAPE, pg.K_RETURN):
                    self.to_menu()

    def dodge(self, mouse):
        for _ in range(50):
            x = random.randint(40, W - 240)
            y = random.randint(170, H - 90)
            r = pg.Rect(x, y, self.play_btn.w, self.play_btn.h)
            if math.hypot(r.centerx - mouse[0], r.centery - mouse[1]) > 220 and not r.colliderect(self.quit_btn.inflate(20, 20)):
                self.play_btn = r
                break
        self.dodges -= 1
        self.menu_quip = ["Fine. Click me. I'm tired.", "Almost!", "Too slow!"][self.dodges]
        self.sfx.play("hop")

    def to_menu(self):
        self.state = "menu"
        self.dodges = 3
        self.menu_quip = ""
        self.quit_armed = False
        self.play_btn = pg.Rect(380, 290, 200, 56)
        self.level = None
        self.parts = []

    # ------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        self.state_t += dt
        for c in self.clouds:
            c[0] += 12 * c[2] * dt
            if c[0] > W + 120:
                c[0] = -120
        if self.caption_t > 0:
            self.caption_t -= dt
            if self.caption_t <= 0:
                pg.display.set_caption(TITLE)
        self.msg_t += dt
        self.banner_t -= dt
        st = self.state
        if st == "loading":
            if self.state_t > 4.0 or (self.load_skip and self.state_t > 0.3):
                self.load_skip = False
                self.start_game()
        elif st == "play":
            self.time += dt
            self.update_play(dt)
        elif st == "clear":
            self.state_t_clear -= dt
            if self.state_t_clear <= 0:
                self.li += 1
                if self.li >= len(LEVELS):
                    self.begin("end")
                    self.sfx.play("win")
                else:
                    self.load_level()
        elif st == "fakewin":
            if random.random() < 0.6:
                self.confetti()
            if self.state_t > 3.6:
                self.state = "play"
                self.level.after_fakewin()
        elif st == "crash":
            if self.state_t > 3.8:
                self.state = "play"
                pg.display.set_caption(TITLE)
                self.level.after_crash()
        elif st == "end":
            if random.random() < 0.4:
                self.confetti()
        self.update_parts(dt)

    def confetti(self):
        cols = [(255, 80, 80), (80, 200, 255), (255, 230, 60), (120, 255, 120), (255, 120, 255)]
        self.parts.append([random.uniform(0, W), -10, random.uniform(-40, 40), random.uniform(60, 160),
                           5.0, 5.0, random.choice(cols), 6, 40])

    def update_parts(self, dt):
        for q in self.parts:
            q[4] -= dt
            q[3] += q[8] * dt
            q[0] += q[2] * dt
            q[1] += q[3] * dt
        self.parts = [q for q in self.parts if q[4] > 0 and q[1] < H + 40]

    def update_play(self, dt):
        lvl, p = self.level, self.p
        lvl.t += 0 if isinstance(lvl, L8) else dt
        if p.dead:
            self.dead_t -= dt
            if self.dead_t <= 0:
                self.respawn()
            return
        self.update_player(dt)
        if self.state != "play":
            return
        # hidden spikes pop up when you get close
        for r in range(ROWS):
            for c in range(COLS):
                if lvl.grid[r][c] == "h":
                    if (c, r) in lvl.popped:
                        lvl.popped[(c, r)] += dt
                    elif abs(p.cx - (c * T + T / 2)) < 80 and abs(p.y + PH - (r + 1) * T) < 70:
                        lvl.popped[(c, r)] = 0.0
                        self.sfx.play("pop")
        # crumbling blocks
        for cell in list(lvl.crumble):
            lvl.crumble[cell] -= dt
            if lvl.crumble[cell] <= 0:
                c, r = cell
                del lvl.crumble[cell]
                lvl.grid[r][c] = "."
                lvl.debris.append([c * T, r * T, 0.0])
                self.sfx.play("crumble")
        for d in lvl.debris:
            d[2] += GRAV * dt
            d[1] += d[2] * dt
        lvl.debris = [d for d in lvl.debris if d[1] < H + 40]
        if lvl.flag:
            lvl.flag.update(dt, p)
        lvl.update(dt, p)
        if self.state != "play":
            return
        # deaths
        if p.y > H + 40 or self.spiked(p) or lvl.hazard(p):
            self.kill()
            return
        if lvl.flag and lvl.flag.touching(p):
            if lvl.on_flag() and self.state == "play":
                self.state = "clear"
                self.state_t_clear = 1.3
                self.banner, self.banner_t = random.choice(["NICE!", "LEVEL CLEAR!", "WOW, OKAY", "FINALLY"]), 1.3
                self.sfx.play("win")
                self.burst(p.cx, p.y, 30, [C_YELLOW, C_WHITE, (120, 255, 120)], 300, 0.9)

    def solids_near(self, x, y):
        lvl = self.level
        out = []
        c0, c1 = int(x // T) - 1, int((x + PW) // T) + 1
        r0, r1 = int(y // T) - 1, int((y + PH) // T) + 1
        for r in range(max(0, r0), min(ROWS, r1 + 1)):
            for c in range(max(0, c0), min(COLS, c1 + 1)):
                if lvl.grid[r][c] in SOLID:
                    out.append((pg.Rect(c * T, r * T, T, T), (c, r)))
        for rect in lvl.extras():
            out.append((rect, None))
        return out

    def update_player(self, dt):
        p, lvl = self.p, self.level
        keys = self.keys()
        left, right = (KEYS_RIGHT, KEYS_LEFT) if self.ctrl == "invert" else (KEYS_LEFT, KEYS_RIGHT)
        d = int(any(keys[k] for k in right)) - int(any(keys[k] for k in left))
        if d:
            p.face = d
        p.vx += (d * SPEED - p.vx) * min(1.0, dt * (18 if p.on else 10))
        p.coyote -= dt
        p.buffer -= dt
        if p.on:
            p.coyote = 0.1
        if p.buffer > 0 and p.coyote > 0:
            p.vy = -JUMP
            p.buffer = p.coyote = 0
            p.squash = -0.25
            self.sfx.play("jump")
        if p.vy < 0 and not any(keys[k] for k in self.jump_keys()):
            p.vy += GRAV * 1.2 * dt
        p.vy = min(p.vy + GRAV * dt, 1400)
        p.squash *= 0.85

        def hit(rx, ry, rect):
            return rx < rect.right and rx + PW > rect.left and ry < rect.bottom and ry + PH > rect.top

        # horizontal
        p.x += p.vx * dt
        for rect, cell in self.solids_near(p.x, p.y):
            if hit(p.x, p.y, rect):
                if p.x + PW / 2 < rect.centerx:
                    p.x = rect.left - PW
                else:
                    p.x = rect.right
                p.vx = 0
                self.touch(cell)
        # vertical
        was_air = not p.on
        p.y += p.vy * dt
        p.on = False
        for rect, cell in self.solids_near(p.x, p.y):
            if hit(p.x, p.y, rect):
                if p.vy > 0:
                    p.y = rect.top - PH
                    if was_air and p.vy > 600:
                        p.squash = 0.3
                    p.vy = 0
                    p.on = True
                    if cell and lvl.grid[cell[1]][cell[0]] == "C" and cell not in lvl.crumble:
                        lvl.crumble[cell] = 0.3
                elif p.vy < 0:
                    p.y = rect.bottom
                    p.vy = 0
                    self.sfx.play("bonk")
                self.touch(cell)
        p.x = max(0.0, min(W - PW, p.x))

    def touch(self, cell):
        lvl = self.level
        if cell and lvl.grid[cell[1]][cell[0]] == "I" and cell not in lvl.revealed:
            lvl.revealed.add(cell)
            self.burst(cell[0] * T + T / 2, cell[1] * T + T / 2, 10, [C_YELLOW, C_WHITE], 160, 0.4, 3)

    def spiked(self, p):
        lvl = self.level
        pr = p.rect()
        c0, c1 = int(p.x // T) - 1, int((p.x + PW) // T) + 1
        r0, r1 = int(p.y // T) - 1, int((p.y + PH) // T) + 1
        for r in range(max(0, r0), min(ROWS, r1 + 1)):
            for c in range(max(0, c0), min(COLS, c1 + 1)):
                ch = lvl.grid[r][c]
                live = ch == "^" or (ch == "h" and lvl.popped.get((c, r), -1) > 0.05)
                if live and pr.colliderect(pg.Rect(c * T + 5, r * T + 13, T - 10, T - 13)):
                    return True
        return False

    # ------------------------------------------------ drawing
    def draw_bg(self):
        self.screen.blit(self.sky, (0, 0))
        for x, y, s in self.clouds:
            for dx, dy, r in ((0, 0, 22), (24, -8, 26), (50, 0, 20), (26, 8, 20)):
                pg.draw.circle(self.screen, C_WHITE, (int(x + dx * s), int(y + dy * s)), int(r * s))
        # distant hills
        pts = [(0, H)] + [(x, 380 + math.sin(x * 0.012) * 26 + math.sin(x * 0.031) * 10) for x in range(0, W + 20, 20)] + [(W, H)]
        pg.draw.polygon(self.screen, (150, 205, 150), pts)

    def draw_brick(self, surf, x, y, faded=False):
        base = (230, 200, 120) if faded else C_BRICK
        mortar = (170, 140, 70) if faded else C_MORTAR
        pg.draw.rect(surf, base, (x, y, T, T))
        pg.draw.line(surf, mortar, (x, y + 14), (x + T - 1, y + 14), 2)
        pg.draw.line(surf, mortar, (x + 14, y), (x + 14, y + 14), 2)
        pg.draw.line(surf, mortar, (x + 4, y + 15), (x + 4, y + T - 1), 2)
        pg.draw.line(surf, mortar, (x + 22, y + 15), (x + 22, y + T - 1), 2)
        pg.draw.rect(surf, mortar, (x, y, T, T), 2)

    def draw_spikes(self, surf, x, y):
        for i in range(2):
            bx = x + i * 15
            pg.draw.polygon(surf, (220, 224, 232), [(bx, y + T), (bx + 7.5, y + 10), (bx + 15, y + T)])
            pg.draw.polygon(surf, (120, 124, 135), [(bx, y + T), (bx + 7.5, y + 10), (bx + 15, y + T)], 2)

    def draw_level(self):
        lvl, surf = self.level, self.screen
        for r in range(ROWS):
            for c in range(COLS):
                ch = lvl.grid[r][c]
                x, y = c * T, r * T
                if ch in GROUNDISH:
                    pg.draw.rect(surf, C_DIRT, (x, y, T, T))
                    for sx, sy in self.speck[(c * 3 + r) % 5]:
                        surf.fill(C_DIRT_DARK, (x + sx, y + sy, 3, 3))
                    if r == 0 or lvl.grid[r - 1][c] not in GROUNDISH:
                        surf.fill(C_GRASS, (x, y, T, 9))
                        surf.fill(C_GRASS_HI, (x, y, T, 3))
                        surf.fill(C_GRASS, (x + 6 + (c * 7) % 12, y + 9, 3, 4))
                    if ch == "C" and lvl.crumble.get((c, r)) is not None:
                        ox = random.randint(-2, 2)
                        pg.draw.line(surf, C_INK, (x + 8 + ox, y + 10), (x + 16, y + 22), 2)
                elif ch == "=":
                    self.draw_brick(surf, x, y)
                elif ch == "I" and (c, r) in lvl.revealed:
                    self.draw_brick(surf, x, y, faded=True)
                    self.text("?", 26, (170, 140, 70), (x + T / 2, y + T / 2 + 1), shadow=False)
                elif ch == "^":
                    self.draw_spikes(surf, x, y)
                elif ch == "h" and (c, r) in lvl.popped:
                    k = min(1.0, lvl.popped[(c, r)] / 0.08)
                    clip = surf.get_clip()
                    surf.set_clip(pg.Rect(x, y, T, T))
                    self.draw_spikes(surf, x, y + (1 - k) * T)
                    surf.set_clip(clip)
        for d in lvl.debris:
            pg.draw.rect(surf, C_DIRT, (int(d[0]) + 3, int(d[1]), T - 6, T - 6))
            surf.fill(C_GRASS, (int(d[0]) + 3, int(d[1]), T - 6, 5))
        lvl.draw_extra(surf)
        if lvl.flag:
            lvl.flag.draw(surf, self.t)

    def draw_player(self):
        p = self.p
        if p is None or p.dead:
            return
        sq = p.squash
        w, h = int(PW * (1 + sq)), int(PH * (1 - sq))
        x, y = int(p.cx - w / 2), int(p.y + PH - h)
        pg.draw.rect(self.screen, C_PLAYER, (x, y, w, h), border_radius=5)
        pg.draw.rect(self.screen, C_INK, (x, y, w, h), 2, border_radius=5)
        ex = x + w / 2 + p.face * 4
        for ox in (-5, 3):
            pg.draw.rect(self.screen, C_WHITE, (ex + ox - 1, y + 7, 5, 7))
            pg.draw.rect(self.screen, C_INK, (ex + ox + (1 if p.face > 0 else -1) + 1, y + 9, 2, 4))
        pg.draw.line(self.screen, C_INK, (x + w / 2 - 3 + p.face * 3, y + h - 8), (x + w / 2 + 3 + p.face * 3, y + h - 8), 2)

    def draw_parts(self):
        for q in self.parts:
            a = max(0.0, q[4] / q[5])
            s = max(1, int(q[7] * (0.4 + 0.6 * a)))
            self.screen.fill(q[6], (int(q[0]), int(q[1]), s, s))

    def draw_hud(self):
        self.text(f"LEVEL {self.li + 1}: {self.level.name}", 30, C_WHITE, (12, 10), "topleft")
        self.text(f"DEATHS: {self.deaths}", 30, (255, 120, 120), (W - 12, 10), "topright")
        m, s = divmod(int(self.time), 60)
        self.text(f"TIME {m:02d}:{s:02d}", 24, C_WHITE, (W - 12, 36), "topright")
        if self.ctrl != "normal" and int(self.t * 3) % 2 == 0:
            label = "CONTROLS: INVERTED" if self.ctrl == "invert" else "JUMP = S / DOWN"
            self.text(label, 30, C_RED, (W / 2, 16))
        if self.banner_t > 0:
            a = min(1.0, self.banner_t * 2)
            img = self.font(56).render(self.banner, True, C_YELLOW)
            sh = self.font(56).render(self.banner, True, C_INK)
            img.set_alpha(int(255 * a))
            sh.set_alpha(int(255 * a))
            r = img.get_rect(center=(W // 2, 175))
            self.screen.blit(sh, r.move(3, 3))
            self.screen.blit(img, r)
        self.draw_narrator()

    def draw_narrator(self):
        if not self.msg:
            return
        shown = int(self.msg_t * 45)
        if shown > len(self.msg) + 45 * 4.5:
            return
        box = pg.Surface((W - 160, 60), pg.SRCALPHA)
        pg.draw.rect(box, (10, 10, 20, 210), box.get_rect(), border_radius=10)
        pg.draw.rect(box, (255, 230, 60, 255), box.get_rect(), 2, border_radius=10)
        self.screen.blit(box, (80, 62))
        self.text("NARRATOR", 18, C_YELLOW, (96, 68), "topleft", shadow=False)
        self.text(self.msg[:shown], 28, C_WHITE, (96, 86), "topleft", shadow=False)

    def draw_menu(self):
        self.draw_bg()
        wob = math.sin(self.t * 2) * 4
        self.text("TOTALLY NORMAL GAME", 86, C_YELLOW, (W / 2, 120 + wob))
        self.text("(nothing weird will happen)", 30, C_INK, (W / 2, 180), shadow=False)
        mouse = pg.mouse.get_pos()
        for rect, label in ((self.play_btn, "PLAY"), (self.quit_btn, "Really? :(" if self.quit_armed else "QUIT")):
            hover = rect.collidepoint(mouse)
            pg.draw.rect(self.screen, (80, 200, 90) if label == "PLAY" else (200, 90, 80), rect, border_radius=10)
            if hover:
                pg.draw.rect(self.screen, C_WHITE, rect, 3, border_radius=10)
            pg.draw.rect(self.screen, C_INK, rect, 3 if not hover else 1, border_radius=10)
            self.text(label, 40, C_WHITE, rect.center)
        if self.menu_quip:
            self.text(self.menu_quip, 30, C_RED, (self.play_btn.centerx, self.play_btn.top - 18))
        self.text("Enter = play    A/D or arrows = move    W / Up / Space = jump    ESC = pause", 24, C_INK, (W / 2, H - 24), shadow=False)

    def draw_loading(self):
        self.screen.fill((20, 20, 30))
        t = self.state_t
        if t < 2.0:
            p = t / 2.0 * 0.99
        elif t < 3.4:
            p = 0.99
        else:
            p = min(1.0, 0.99 + (t - 3.4) * 0.1)
        msgs = [(0.3, "Loading totally normal assets..."), (0.6, "Downloading more RAM..."),
                (0.85, "Hiding the traps... I mean, polishing the levels..."), (0.99, "Asking Torgrim for permission...")]
        label = next((m for lim, m in msgs if p < lim), "Almost there...")
        if p >= 1.0:
            label = "Done! (nothing weird will happen)"
        if self.load_skip:
            label = "Skipping. Fine. Impatient."
        self.text("LOADING", 60, C_WHITE, (W / 2, 200))
        bar = pg.Rect(180, 250, 600, 34)
        pg.draw.rect(self.screen, (60, 60, 80), bar, border_radius=6)
        pg.draw.rect(self.screen, (80, 220, 110), (bar.x + 4, bar.y + 4, int((bar.w - 8) * p), bar.h - 8), border_radius=4)
        self.text(f"{int(p * 100)}%", 30, C_WHITE, bar.center)
        self.text(label, 30, (200, 200, 220), (W / 2, 320), shadow=False)
        self.text("press any key to skip", 22, (120, 120, 140), (W / 2, H - 30), shadow=False)

    def draw_fakewin(self):
        ov = pg.Surface((W, H), pg.SRCALPHA)
        ov.fill((0, 0, 30, 190))
        self.screen.blit(ov, (0, 0))
        self.draw_parts()
        t = self.state_t
        self.text("CONGRATULATIONS!", 84, C_YELLOW, (W / 2, 140 + math.sin(t * 5) * 5))
        self.text("You beat TOTALLY NORMAL GAME!", 40, C_WHITE, (W / 2, 210))
        self.text(f"Deaths: {self.deaths}      Time: {int(self.time)} s", 32, C_WHITE, (W / 2, 260))
        self.text("CREDITS", 30, (160, 200, 255), (W / 2, 330))
        roll = max(0.0, t - 0.8) * 40
        for i, line in enumerate(["Made by: nobody", "Tested by: also nobody", "Traps: none (trust me)", "Thanks for playing!"]):
            y = 370 + i * 30 - roll
            if 340 < y < 480:
                self.text(line, 28, C_WHITE, (W / 2, y))
        if t > 2.6:
            self.text("...wait.", 60, C_RED, (W / 2, 470))

    def draw_crash(self):
        ov = pg.Surface((W, H), pg.SRCALPHA)
        ov.fill((255, 255, 255, 150))
        self.screen.blit(ov, (0, 0))
        t = self.state_t
        if t < 2.9:
            box = pg.Rect(W / 2 - 250, H / 2 - 110, 500, 210)
            pg.draw.rect(self.screen, (235, 235, 235), box)
            pg.draw.rect(self.screen, (60, 60, 60), box, 2)
            pg.draw.rect(self.screen, (40, 70, 160), (box.x, box.y, box.w, 30))
            self.text("Totally Normal Game.exe", 26, C_WHITE, (box.x + 10, box.y + 6), "topleft", shadow=False)
            pg.draw.circle(self.screen, C_RED, (box.x + 45, box.y + 80), 22)
            self.text("X", 34, C_WHITE, (box.x + 45, box.y + 81), shadow=False)
            lines = ["Totally Normal Game has stopped working", "because somebody pressed the button.",
                     "Please do not press buttons."]
            for i, line in enumerate(lines):
                self.text(line, 25, C_INK, (box.x + 85, box.y + 58 + i * 24), "topleft", shadow=False)
            for i, label in enumerate(("Close game", "Cry")):
                b = pg.Rect(box.right - 250 + i * 125, box.bottom - 48, 110, 32)
                pg.draw.rect(self.screen, (215, 215, 215), b)
                pg.draw.rect(self.screen, (90, 90, 90), b, 2)
                self.text(label, 24, C_INK, b.center, shadow=False)
        else:
            self.text("JUST KIDDING :)", 90, C_RED, (W / 2, H / 2))

    def draw_end(self):
        self.draw_bg()
        self.draw_parts()
        d = self.deaths
        rank = ("Suspiciously good" if d <= 5 else "Normal human" if d <= 20
                else "Professional victim" if d <= 50 else "Torgrim's favourite")
        m, s = divmod(int(self.time), 60)
        self.text("YOU ACTUALLY BEAT IT", 76, C_YELLOW, (W / 2, 130))
        self.text("(for real this time, we checked)", 28, C_INK, (W / 2, 180), shadow=False)
        self.text(f"Deaths: {d}", 44, C_WHITE, (W / 2, 250))
        self.text(f"Time: {m:02d}:{s:02d}", 44, C_WHITE, (W / 2, 295))
        self.text(f"Rank: {rank}", 44, (255, 140, 140), (W / 2, 345))
        self.text("R = play again (it will be exactly the same. or will it?)    ESC = menu", 26, C_INK,
                  (W / 2, H - 40), shadow=False)

    def draw(self):
        st = self.state
        if st == "menu":
            self.draw_menu()
            self.draw_parts()
        elif st == "loading":
            self.draw_loading()
        elif st == "end":
            self.draw_end()
        else:
            self.draw_bg()
            self.draw_level()
            self.draw_player()
            if st == "fakewin":
                self.draw_fakewin()
            else:
                self.draw_parts()
                self.draw_hud()
            if st == "crash":
                self.draw_crash()
            if st == "pause":
                ov = pg.Surface((W, H), pg.SRCALPHA)
                ov.fill((0, 0, 0, 150))
                self.screen.blit(ov, (0, 0))
                self.text("PAUSED", 80, C_WHITE, (W / 2, H / 2 - 40))
                self.text("ESC = resume    R = restart level    Q = quit to menu", 30, C_WHITE, (W / 2, H / 2 + 30))

    # ------------------------------------------------ main loop
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 1 / 30)
            for e in pg.event.get():
                self.handle(e)
            self.update(dt)
            self.draw()
            pg.display.flip()


if __name__ == "__main__":
    Game().run()
