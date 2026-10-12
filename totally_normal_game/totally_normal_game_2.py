#!/usr/bin/env python3
"""
TOTALLY NORMAL GAME 2 : Electric Boogaloo
The sequel that is even more normal. (It is not normal at all.)

Everything happens INSIDE this one game window: screen shake, flips, mirrors,
color inversion, zoom, wobble, and fake in-game popups that chase you around.
Nothing here touches your computer, your files, or the internet. The window's
real close button always works, and ESC quits from anywhere.

Install:  pip install pygame-ce
Run:      python totally_normal_game_2.py

Move: A/D or arrows    Jump: W / Up / Space    Dismiss a popup: click its [OK]
ESC = quit    P = pause    R = restart level (yes, it counts as a death)
F11 = toggle fullscreen focus mode (a borderless black frame, not a real
      display-mode switch, so alt-tab and your taskbar stay normal)
"""
import math
import random
import sys
import array

import pygame as pg

W, H = 960, 540
T = 30
COLS, ROWS = 32, 18
FPS = 60
SPEED, GRAV, JUMP = 260, 2000, 720
PW, PH = 22, 28
TITLE = "Totally Normal Game 2"

SOLID = set("#IC=")
GROUNDISH = set("#XC")

KEYS_LEFT = (pg.K_a, pg.K_LEFT)
KEYS_RIGHT = (pg.K_d, pg.K_RIGHT)
KEYS_JUMP = (pg.K_w, pg.K_UP, pg.K_SPACE)
KEYS_DOWN = (pg.K_s, pg.K_DOWN)

DEATH_LINES = [
    "Skill issue 2.", "Sequels are hard, huh?", "The floor missed you.", "Torgrim says hi.",
    "Bold. Wrong, but bold.", "Have you considered winning?", "Oof, part two.", "Git gud-er.",
    "That gap was your friend.", "You died. It's a sequel tradition.", "Certified bruh moment 2.",
    "Mikkel is even more disappointed.", "The spikes remember you.",
]

POPUP_TITLES = ["totally_normal.exe", "Definitely Not A Trap", "Free Robux!!!", "System",
                "Torgrim's Corner", "Important Message", "You Have Won", "notification", "achievement.dll"]
POPUP_BODY = [
    "You have been selected to click OK.", "Your game is running too well. Fixing...",
    "Congratulations! You clicked a thing.", "This popup is 100% necessary.",
    "Warning: too much fun detected.", "Are you sure you're sure?",
    "The flag is behind this window. Trust me.", "Please enjoy this interruption.",
    "Achievement unlocked: Read a popup.", "Do NOT close this window. (Please close it.)",
    "Loading emotional support...", "This is fine. Everything is fine.",
    "Beep boop. I am a normal message.", "Your patience has expired.",
]

C_SKY_TOP = (150, 120, 230)
C_SKY_BOT = (245, 205, 240)
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


# ------------------------------------------------------------- sound
class Sfx:
    def __init__(self):
        self.ok = False
        self.snd = {}
        try:
            pg.mixer.init(22050, -16, 1, 512)
            rate, _, channels = pg.mixer.get_init()

            def tone(freq, dur, vol=0.2, wave="sq", slide=1.0):
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
                "jump": tone(420, 0.12, 0.15, "sq", 2.0),
                "die": tone(320, 0.5, 0.22, "sq", 0.2),
                "hop": tone(700, 0.16, 0.16, "sin", 1.9),
                "pop": tone(900, 0.08, 0.18, "sq", 0.5),
                "win": tone(520, 0.55, 0.17, "sq", 2.2),
                "bonk": tone(200, 0.1, 0.22, "sq", 0.6),
                "click": tone(1000, 0.05, 0.14, "sq"),
                "warn": tone(1200, 0.1, 0.11, "sin"),
                "glitch": tone(140, 0.18, 0.2, "noise"),
                "popup": tone(660, 0.09, 0.14, "sq", 1.4),
                "whoosh": tone(300, 0.25, 0.13, "sin", 2.4),
            }
            self.ok = True
        except Exception:
            self.ok = False

    def play(self, name):
        if self.ok and name in self.snd:
            self.snd[name].play()


# ------------------------------------------------------------- entities
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
            go = abs(p.cx - self.x) < 120 and abs(p.y + PH - self.y) < 110
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


class Popup:
    """A fake dialog box drawn INSIDE the game surface. Some run away from the
    cursor; all vanish only when you click their [OK]. Cosmetic — never real OS UI."""
    _n = 0

    def __init__(self, game, runaway=False, text=None, title=None, evil=False):
        self.g = game
        Popup._n += 1
        self.w = random.randint(230, 300)
        self.h = random.randint(120, 150)
        self.x = random.randint(20, W - self.w - 20)
        self.y = random.randint(70, H - self.h - 40)
        self.title = title or random.choice(POPUP_TITLES)
        self.text = text or random.choice(POPUP_BODY)
        self.runaway = runaway
        self.evil = evil          # evil popups spawn a friend when closed (up to a cap)
        self.born = game.t
        self.vx = random.choice([-1, 1]) * random.uniform(40, 90)
        self.vy = random.choice([-1, 1]) * random.uniform(30, 70)

    def ok_rect(self):
        return pg.Rect(self.x + self.w - 78, self.y + self.h - 34, 62, 24)

    def close_rect(self):
        return pg.Rect(self.x + self.w - 24, self.y + 4, 18, 16)

    def update(self, dt, mouse):
        if self.runaway:
            self.x += self.vx * dt
            self.y += self.vy * dt
            if self.x < 10 or self.x + self.w > W - 10:
                self.vx *= -1
            if self.y < 60 or self.y + self.h > H - 20:
                self.vy *= -1
            self.x = max(10, min(W - self.w - 10, self.x))
            self.y = max(60, min(H - self.h - 20, self.y))
            ok = self.ok_rect()
            d = math.hypot(ok.centerx - mouse[0], ok.centery - mouse[1])
            if d < 90:
                a = math.atan2(ok.centery - mouse[1], ok.centerx - mouse[0])
                self.vx += math.cos(a) * 30
                self.vy += math.sin(a) * 30
                sp = math.hypot(self.vx, self.vy)
                if sp > 260:
                    self.vx *= 260 / sp
                    self.vy *= 260 / sp

    def click(self, pos):
        """Return True if this popup should be removed."""
        if self.ok_rect().collidepoint(pos) or self.close_rect().collidepoint(pos):
            self.g.sfx.play("click")
            if self.evil and self.g.popup_spawns < 6:
                self.g.popup_spawns += 2
                for _ in range(2):
                    self.g.popups.append(Popup(self.g, runaway=False, evil=True,
                                               title="haha", text="You closed one. Here are two more."))
            return True
        return False

    def draw(self, surf, mouse):
        x, y, w, h = int(self.x), int(self.y), self.w, self.h
        sh = pg.Surface((w, h), pg.SRCALPHA)
        sh.fill((0, 0, 0, 70))
        surf.blit(sh, (x + 5, y + 5))
        pg.draw.rect(surf, (232, 232, 238), (x, y, w, h))
        pg.draw.rect(surf, (150, 150, 160), (x, y, w, h), 2)
        bar = (40, 70, 170) if not self.evil else (170, 40, 60)
        pg.draw.rect(surf, bar, (x, y, w, 24))
        self.g.text(self.title[:26], 20, C_WHITE, (x + 8, y + 4), "topleft", shadow=False, surf=surf)
        cr = self.close_rect()
        pg.draw.rect(surf, (210, 90, 80), cr)
        pg.draw.rect(surf, C_WHITE, cr, 1)
        self.g.text("x", 20, C_WHITE, cr.center, shadow=False, surf=surf)
        self.g.wrap(self.text, 20, C_INK, (x + 12, y + 36), w - 24, surf=surf)
        ok = self.ok_rect()
        hover = ok.collidepoint(mouse)
        pg.draw.rect(surf, (205, 225, 205) if hover else (215, 215, 220), ok)
        pg.draw.rect(surf, (90, 90, 100), ok, 2)
        self.g.text("OK", 22, C_INK, ok.center, shadow=False, surf=surf)


# ------------------------------------------------------------- levels
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

    def reset(self):
        self.grid = [["." for _ in range(COLS)] for _ in range(ROWS)]
        self.revealed = set()
        self.popped = {}
        self.crumble = {}
        self.debris = []
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

    def build(self):
        pass

    def extras(self):
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
    name = "The Return"
    intro = "You again? Fine. Walk to the flag. Nothing weird will happen. (lol)"

    def build(self):
        self.floor()
        self.flag = Flag(self.g, [(27, 14, "near"), (6, 14, "near"), (29, 14, "near"), (16, 14, "stay")],
                         ["Sequel flag. Faster now.", "Wheee!", "Okay okay, I'll stop. Maybe.",
                          "There. Take it. You earned the shaking."])

    def update(self, dt, p):
        if p.cx > 12 * T:
            self.once("shake", None)
            self.g.fx("shake", 0.6, 6)


class L2(Level):
    name = "Upside Down"
    intro = "The camera is fine. Definitely not going to flip. Definitely."

    def build(self):
        self.floor()
        self.fill(9, 12, 12, 12, "=")
        self.fill(18, 10, 21, 10, "=")
        for c in (14, 24):
            self.grid[14][c] = "^"
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.flipped = False

    def update(self, dt, p):
        if not self.flipped and p.cx > 8 * T:
            self.flipped = True
            self.g.effect_on("flip")
            self.g.say("Oops! Camera's upside down. You'll get used to it. Controls still work normally!")
            self.g.sfx.play("whoosh")


class L3(Level):
    name = "Mirror Mirror"
    intro = "Simple jumps. Left is left, right is right. As always."

    def build(self):
        self.floor(0, 9)
        self.floor(13, 18)
        self.floor(22, 31)
        self.fill(10, 17, 12, 17, "^")
        self.fill(19, 17, 21, 17, "^")
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.stage = 0

    def update(self, dt, p):
        if self.stage == 0 and p.cx > 6 * T:
            self.stage = 1
            self.g.effect_on("mirror")
            self.g.say("The screen is now a mirror. Your eyes are the problem, not me.")
            self.g.sfx.play("whoosh")


class L4(Level):
    name = "Rave Mode"
    intro = "Cozy relaxing level. Very calm. Please relax."

    def build(self):
        self.floor()
        self.fill(8, 12, 11, 12, "=")
        self.fill(15, 13, 15, 14, "=")
        self.fill(20, 11, 23, 11, "=")
        for c in (13, 18, 26):
            self.grid[14][c] = "^"
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.on_ = False

    def update(self, dt, p):
        if not self.on_ and p.cx > 7 * T:
            self.on_ = True
            self.g.effect_on("rave")
            self.g.effect_on("wobble")
            self.g.say("RELAXING INTENSIFIES. (this is still a calm level, ignore the colors)")
            self.g.sfx.play("glitch")


class L5(Level):
    name = "Pop-up Storm"
    intro = "No effects here! Just you, the flag, and total focus."

    def build(self):
        self.floor()
        self.fill(11, 12, 14, 12, "=")
        self.fill(19, 12, 22, 12, "=")
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.timer = 1.0
        self.count = 0

    def update(self, dt, p):
        self.timer -= dt
        if self.timer <= 0 and self.count < 9:
            self.timer = 1.1
            self.count += 1
            self.g.popups.append(Popup(self.g, runaway=self.count > 3))
            self.g.sfx.play("popup")
            if self.count == 1:
                self.g.say("Oh no. Anyway. Click the [OK] buttons to close them. Some run away.")

    def on_flag(self):
        for pp in self.g.popups:
            pp.evil = False
        self.g.popups.clear()
        self.g.say("You survived the popups. I'm almost impressed.")
        return True


class L6(Level):
    name = "Tiny Zoom"
    intro = "Nice big clear view of everything. Enjoy the scenery."

    def build(self):
        self.floor(0, 12)
        self.floor(17, 31)
        self.fill(13, 17, 16, 17, "^")
        self.fill(13, 13, 16, 13, "I")     # invisible bridge over the spikes
        self.grid[14][24] = "h"
        self.flag = Flag(self.g, [(29, 14, "stay")])
        self.zoomed = False

    def update(self, dt, p):
        if not self.zoomed and p.cx > 8 * T:
            self.zoomed = True
            self.g.effect_on("zoom")
            self.g.say("Zooming in for a better look. There's an invisible bridge over the spikes. Probably.")

    def on_death(self):
        return {2: "The bridge is real. Your faith is not."}.get(self.deaths)


class L7(Level):
    name = "The Clone Popup"
    intro = "One tiny message. Close it and move on. Easy."

    def build(self):
        self.floor()
        self.fill(9, 12, 9, 14, "=")     # a 3-tile wall: jump over it
        self.flag = Flag(self.g, [(20, 14, "stay")])
        self.spawned = False

    def update(self, dt, p):
        if not self.spawned:
            self.spawned = True
            self.g.popup_spawns = 0
            self.g.popups.append(Popup(self.g, evil=True, title="haha",
                                       text="Close me. What's the worst that could happen?"))
            self.g.say("Just one popup between you and the flag. Go on. Close it.")

    def on_flag(self):
        self.g.popups.clear()
        self.g.say("You reached the flag WITH popups open? Overachiever.")
        return True


class L8(Level):
    name = "Everything Everywhere"
    intro = "Final level! Calm, clean, and effect-free. Pinky promise."

    def build(self):
        self.floor()
        self.fill(7, 15, 10, 17, "X")
        self.fill(6, 12, 11, 12, "=")
        self.grid[14][15] = "h"
        self.fill(18, 15, 21, 17, ".")
        self.fill(18, 15, 21, 15, "C")
        self.fill(18, 17, 21, 17, "^")
        self.fill(25, 11, 28, 11, "=")
        self.flag = Flag(self.g, [(24, 14, "near"), (30, 14, "near"), (28, 6, 2.0), (14, 14, "stay")],
                         ["Nope!", "Up here, sequel star!", "FINE. Real final flag. I mean it."])
        self.t2 = 0.0
        self.pt = 2.0

    def update(self, dt, p):
        self.t2 += dt
        for name, at in (("shake", 0.5), ("wobble", 2.5), ("rave", 5.0), ("mirror", 8.0)):
            if self.t2 >= at:
                self.once("fx" + name, None)
                if name in ("mirror", "rave", "wobble"):
                    self.g.effect_on(name)
                else:
                    self.g.fx("shake", 999, 5)
        self.pt -= dt
        if self.pt <= 0 and len(self.g.popups) < 3:
            self.pt = 3.0
            self.g.popups.append(Popup(self.g, runaway=True))
            self.g.sfx.play("popup")

    def on_flag(self):
        self.g.popups.clear()
        return True

    def on_death(self):
        return {1: "You fell for the fake floor. In the SEQUEL. Shameful."}.get(self.deaths)


LEVELS = [L1, L2, L3, L4, L5, L6, L7, L8]


# ------------------------------------------------------------- game
class Game:
    def __init__(self):
        pg.init()
        self.sfx = Sfx()
        self.screen = pg.display.set_mode((W, H))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.world = pg.Surface((W, H))
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
        self.popups = []
        self.popup_spawns = 0
        self.msg, self.msg_t = "", 0.0
        self.banner, self.banner_t = "", 0.0
        self.caption_t = 0.0
        # screen effects
        self.effects = {"flip": False, "mirror": False, "rave": False, "wobble": False, "zoom": False}
        self.shake_t = 0.0
        self.shake_mag = 0.0
        self.play_btn = pg.Rect(360, 300, 240, 60)
        self.dodges = 4
        self.menu_quip = ""
        self.load_skip = False
        self.fullscreen = False
        self.scale = 1.0
        self.offset = (0, 0)
        self.sky = self._make_sky()
        self.clouds = [[random.uniform(0, W), random.uniform(30, 250), random.uniform(0.6, 1.4)] for _ in range(7)]
        self.speck = [[(random.randrange(2, T - 4), random.randrange(10, T - 4)) for _ in range(4)] for _ in range(5)]

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
        surf = surf if surf is not None else self.world
        f = self.font(size)
        img = f.render(txt, True, col)
        r = img.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        if shadow:
            sh = f.render(txt, True, (0, 0, 0))
            surf.blit(sh, r.move(2, 2))
        surf.blit(img, r)
        return r

    def wrap(self, txt, size, col, pos, width, surf=None):
        surf = surf if surf is not None else self.world
        f = self.font(size)
        words = txt.split()
        line, y = "", pos[1]
        for w in words:
            test = (line + " " + w).strip()
            if f.size(test)[0] > width and line:
                self.text(line, size, col, (pos[0], y), "topleft", shadow=False, surf=surf)
                y += size - 4
                line = w
            else:
                line = test
        if line:
            self.text(line, size, col, (pos[0], y), "topleft", shadow=False, surf=surf)

    def say(self, text):
        self.msg, self.msg_t = text, 0.0

    def fx(self, kind, dur, mag):
        if kind == "shake":
            self.shake_t = max(self.shake_t, dur)
            self.shake_mag = mag

    def effect_on(self, name):
        self.effects[name] = True

    def burst(self, x, y, n, cols, speed=260, life=0.7, size=4, grav=900):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = speed * random.uniform(0.3, 1.0)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 120, life, life,
                               random.choice(cols), size, grav])

    def keys(self):
        return pg.key.get_pressed()

    # ------------------------------------------------ input remap for window scaling + effects
    def to_world(self, pos):
        """Map a real window pixel to a position on the 960x540 game surface,
        undoing the fullscreen letterbox scale/offset (identity in windowed mode)."""
        sc = self.scale or 1.0
        ox, oy = self.offset
        return ((pos[0] - ox) / sc, (pos[1] - oy) / sc)

    def effect_mouse(self, raw_pos):
        """Map a real window pixel all the way into world content space,
        also undoing the flip / mirror / zoom effects so popup clicks line up."""
        mx, my = self.to_world(raw_pos)
        if self.state == "play":
            if self.effects["zoom"]:
                z = 1.8
                cx, cy = self.p.cx if self.p else W / 2, (self.p.y if self.p else H / 2)
                ox = max(0, min(W - W / z, cx - W / z / 2))
                oy = max(0, min(H - H / z, cy - H / z / 2))
                mx, my = ox + mx / z, oy + my / z
            if self.effects["mirror"]:
                mx = W - mx
            if self.effects["flip"]:
                my = H - my
        return (mx, my)

    def world_mouse(self):
        return self.effect_mouse(pg.mouse.get_pos())

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        try:
            if self.fullscreen:
                # FULLSCREEN|SCALED lets SDL pick the right monitor (wherever the
                # window already is) and handles the black-bar letterboxing and
                # mouse-coordinate scaling itself, so it always lines up correctly
                # -- no display-mode switch, no manual desktop-size guessing.
                self.screen = pg.display.set_mode((W, H), pg.FULLSCREEN | pg.SCALED)
            else:
                self.screen = pg.display.set_mode((W, H))
        except Exception:
            self.fullscreen = not self.fullscreen
        self.sfx.play("whoosh")

    # ------------------------------------------------ flow
    def start_game(self):
        self.deaths, self.time, self.li = 0, 0.0, 0
        self.load_level()

    def load_level(self):
        for k in self.effects:
            self.effects[k] = False
        self.shake_t = 0.0
        self.popups.clear()
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
        self.fx("shake", 0.35, 8)
        self.sfx.play("die")
        self.say(self.level.on_death() or random.choice(DEATH_LINES))

    # ------------------------------------------------ events
    def handle(self, e):
        if e.type == pg.QUIT:
            pg.quit()
            sys.exit()
        if e.type == pg.KEYDOWN and e.key == pg.K_F11:
            self.toggle_fullscreen()
            return
        if e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE and self.state not in ("menu",):
            if self.state == "play":
                self.state = "pause"
                return
        st = self.state
        if st == "menu":
            if e.type == pg.MOUSEMOTION and self.dodges > 0 and self.play_btn.collidepoint(self.to_world(e.pos)):
                self.dodge(self.to_world(e.pos))
            elif e.type == pg.MOUSEBUTTONDOWN and e.button == 1 and self.play_btn.collidepoint(self.to_world(e.pos)):
                self.sfx.play("click")
                self.begin("loading")
            elif e.type == pg.KEYDOWN and e.key in (pg.K_RETURN, pg.K_SPACE, pg.K_KP_ENTER):
                self.begin("loading")
            elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                pg.quit()
                sys.exit()
        elif st == "loading":
            if e.type in (pg.KEYDOWN, pg.MOUSEBUTTONDOWN):
                self.load_skip = True
        elif st == "play":
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1 and self.popups:
                pos = self.effect_mouse(e.pos)
                for pp in reversed(self.popups):
                    if pp.click(pos):
                        self.popups.remove(pp)
                        break
            elif e.type == pg.KEYDOWN:
                if e.key == pg.K_p:
                    self.state = "pause"
                elif e.key == pg.K_r and not self.p.dead:
                    self.kill()
                    self.say("Restarting counts as a death. Sequel rules, same as before.")
                elif e.key in KEYS_JUMP:
                    self.p.buffer = 0.13
        elif st == "pause":
            if e.type == pg.KEYDOWN:
                if e.key in (pg.K_p,):
                    self.state = "play"
                elif e.key == pg.K_ESCAPE:
                    self.state = "play"
                elif e.key == pg.K_q:
                    self.to_menu()
                elif e.key == pg.K_r:
                    self.state = "play"
                    self.kill()
        elif st == "end":
            if e.type == pg.KEYDOWN:
                if e.key == pg.K_r:
                    self.start_game()
                elif e.key in (pg.K_RETURN,):
                    self.to_menu()

    def dodge(self, mouse):
        for _ in range(60):
            x = random.randint(30, W - 270)
            y = random.randint(170, H - 80)
            r = pg.Rect(x, y, self.play_btn.w, self.play_btn.h)
            if math.hypot(r.centerx - mouse[0], r.centery - mouse[1]) > 200:
                self.play_btn = r
                break
        self.dodges -= 1
        self.menu_quip = ["Not this time!", "Nope!", "Getting warmer!", "So close!"][min(3, self.dodges)]
        self.sfx.play("hop")

    def begin(self, state):
        self.state, self.state_t = state, 0.0

    def to_menu(self):
        self.state = "menu"
        self.dodges = 4
        self.menu_quip = ""
        self.play_btn = pg.Rect(360, 300, 240, 60)
        self.level = None
        self.parts = []
        self.popups = []
        for k in self.effects:
            self.effects[k] = False

    # ------------------------------------------------ update
    def update(self, dt):
        self.t += dt
        self.state_t += dt
        for c in self.clouds:
            c[0] += 12 * c[2] * dt
            if c[0] > W + 120:
                c[0] = -120
        self.msg_t += dt
        self.banner_t -= dt
        if self.shake_t > 0:
            self.shake_t -= dt
        st = self.state
        wm = self.world_mouse()
        for pp in self.popups:
            pp.update(dt, wm)
        if st == "loading":
            if self.state_t > 3.6 or (self.load_skip and self.state_t > 0.3):
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
        lvl.t += dt
        if p.dead:
            self.dead_t -= dt
            if self.dead_t <= 0:
                self.respawn()
            return
        self.update_player(dt)
        if self.state != "play":
            return
        for r in range(ROWS):
            for c in range(COLS):
                if lvl.grid[r][c] == "h":
                    if (c, r) in lvl.popped:
                        lvl.popped[(c, r)] += dt
                    elif abs(p.cx - (c * T + T / 2)) < 80 and abs(p.y + PH - (r + 1) * T) < 70:
                        lvl.popped[(c, r)] = 0.0
                        self.sfx.play("pop")
        for cell in list(lvl.crumble):
            lvl.crumble[cell] -= dt
            if lvl.crumble[cell] <= 0:
                c, r = cell
                del lvl.crumble[cell]
                lvl.grid[r][c] = "."
                lvl.debris.append([c * T, r * T, 0.0])
                self.sfx.play("glitch")
        for d in lvl.debris:
            d[2] += GRAV * dt
            d[1] += d[2] * dt
        lvl.debris = [d for d in lvl.debris if d[1] < H + 40]
        if lvl.flag:
            lvl.flag.update(dt, p)
        lvl.update(dt, p)
        if self.state != "play":
            return
        if p.y > H + 40 or self.spiked(p) or lvl.hazard(p):
            self.kill()
            return
        if lvl.flag and lvl.flag.touching(p):
            if lvl.on_flag() and self.state == "play":
                self.state = "clear"
                self.state_t_clear = 1.3
                self.banner, self.banner_t = random.choice(["NICE!", "LEVEL CLEAR!", "HUH, OKAY", "FINALLY 2"]), 1.3
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
        # mirror / flip swap the movement so the on-screen picture stays intuitive
        left, right = KEYS_LEFT, KEYS_RIGHT
        if self.effects["mirror"]:
            left, right = right, left
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
        if p.vy < 0 and not any(keys[k] for k in KEYS_JUMP):
            p.vy += GRAV * 1.2 * dt
        p.vy = min(p.vy + GRAV * dt, 1400)
        p.squash *= 0.85

        def hit(rx, ry, rect):
            return rx < rect.right and rx + PW > rect.left and ry < rect.bottom and ry + PH > rect.top

        p.x += p.vx * dt
        for rect, cell in self.solids_near(p.x, p.y):
            if hit(p.x, p.y, rect):
                if p.x + PW / 2 < rect.centerx:
                    p.x = rect.left - PW
                else:
                    p.x = rect.right
                p.vx = 0
                self.touch(cell)
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
        self.world.blit(self.sky, (0, 0))
        for x, y, s in self.clouds:
            for dx, dy, r in ((0, 0, 22), (24, -8, 26), (50, 0, 20), (26, 8, 20)):
                pg.draw.circle(self.world, C_WHITE, (int(x + dx * s), int(y + dy * s)), int(r * s))
        pts = [(0, H)] + [(x, 380 + math.sin(x * 0.012) * 26 + math.sin(x * 0.031) * 10) for x in range(0, W + 20, 20)] + [(W, H)]
        pg.draw.polygon(self.world, (150, 205, 150), pts)

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
        lvl, surf = self.level, self.world
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
        pg.draw.rect(self.world, C_PLAYER, (x, y, w, h), border_radius=5)
        pg.draw.rect(self.world, C_INK, (x, y, w, h), 2, border_radius=5)
        ex = x + w / 2 + p.face * 4
        for ox in (-5, 3):
            pg.draw.rect(self.world, C_WHITE, (ex + ox - 1, y + 7, 5, 7))
            pg.draw.rect(self.world, C_INK, (ex + ox + (1 if p.face > 0 else -1) + 1, y + 9, 2, 4))
        pg.draw.line(self.world, C_INK, (x + w / 2 - 3 + p.face * 3, y + h - 8), (x + w / 2 + 3 + p.face * 3, y + h - 8), 2)

    def draw_parts(self):
        for q in self.parts:
            a = max(0.0, q[4] / q[5])
            s = max(1, int(q[7] * (0.4 + 0.6 * a)))
            self.world.fill(q[6], (int(q[0]), int(q[1]), s, s))

    def draw_hud(self):
        self.text(f"LVL {self.li + 1}: {self.level.name}", 30, C_WHITE, (12, 10), "topleft")
        self.text(f"DEATHS: {self.deaths}", 30, (255, 120, 120), (W - 12, 10), "topright")
        active = [k.upper() for k, v in self.effects.items() if v]
        if active and int(self.t * 3) % 2 == 0:
            self.text("EFFECTS: " + " ".join(active), 22, C_RED, (W / 2, 16))
        if self.banner_t > 0:
            a = min(1.0, self.banner_t * 2)
            img = self.font(52).render(self.banner, True, C_YELLOW)
            sh = self.font(52).render(self.banner, True, C_INK)
            img.set_alpha(int(255 * a))
            sh.set_alpha(int(255 * a))
            r = img.get_rect(center=(W // 2, 175))
            self.world.blit(sh, r.move(3, 3))
            self.world.blit(img, r)
        self.draw_narrator()

    def draw_narrator(self):
        if not self.msg:
            return
        shown = int(self.msg_t * 45)
        if shown > len(self.msg) + 45 * 5:
            return
        box = pg.Surface((W - 160, 58), pg.SRCALPHA)
        pg.draw.rect(box, (10, 10, 20, 210), box.get_rect(), border_radius=10)
        pg.draw.rect(box, (255, 230, 60, 255), box.get_rect(), 2, border_radius=10)
        self.world.blit(box, (80, 60))
        self.text("NARRATOR", 18, C_YELLOW, (96, 66), "topleft", shadow=False)
        self.text(self.msg[:shown], 26, C_WHITE, (96, 84), "topleft", shadow=False)

    def draw_popups(self):
        wm = self.world_mouse()
        for pp in self.popups:
            pp.draw(self.world, wm)

    # ---- compose world onto screen with the active screen effects
    def present(self):
        surf = self.world
        if self.state == "play":
            if self.effects["rave"]:
                tint = pg.Surface((W, H))
                hue = (math.sin(self.t * 4) * 0.5 + 0.5)
                tint.fill((int(120 + 120 * math.sin(self.t * 5)),
                           int(120 + 120 * math.sin(self.t * 5 + 2)),
                           int(120 + 120 * math.sin(self.t * 5 + 4))))
                surf = surf.copy()
                surf.blit(tint, (0, 0), special_flags=pg.BLEND_MULT)
            if self.effects["zoom"]:
                z = 1.8
                cx, cy = (self.p.cx, self.p.y) if self.p else (W / 2, H / 2)
                vw, vh = int(W / z), int(H / z)
                ox = int(max(0, min(W - vw, cx - vw / 2)))
                oy = int(max(0, min(H - vh, cy - vh / 2)))
                sub = surf.subsurface((ox, oy, vw, vh))
                surf = pg.transform.smoothscale(sub, (W, H))
            if self.effects["mirror"]:
                surf = pg.transform.flip(surf, True, False)
            if self.effects["flip"]:
                surf = pg.transform.flip(surf, False, True)
            if self.effects["wobble"]:
                surf = surf.copy()
                out = pg.Surface((W, H))
                out.blit(self.sky, (0, 0))
                for y in range(0, H, 6):
                    off = int(math.sin(self.t * 6 + y * 0.05) * 8)
                    out.blit(surf, (off, y), (0, y, W, 6))
                surf = out
        # letterbox scale onto the real window (identity 1:1 in windowed mode,
        # scaled + centered with black bars when fullscreen focus mode is on)
        tw, th = self.screen.get_size()
        scale = min(tw / W, th / H) if tw > 0 and th > 0 else 1.0
        if scale <= 0:
            scale = 1.0
        sw, sh = max(1, int(W * scale)), max(1, int(H * scale))
        lx, ly = (tw - sw) // 2, (th - sh) // 2
        self.scale, self.offset = scale, (lx, ly)
        if scale != 1.0:
            surf = pg.transform.smoothscale(surf, (sw, sh))
        shx = shy = 0
        if self.shake_t > 0:
            shx = random.randint(-1, 1) * self.shake_mag
            shy = random.randint(-1, 1) * self.shake_mag
        self.screen.fill((0, 0, 0))
        self.screen.blit(surf, (lx + int(shx), ly + int(shy)))

    def draw_menu(self):
        self.draw_bg()
        wob = math.sin(self.t * 2) * 4
        self.text("TOTALLY NORMAL", 74, C_YELLOW, (W / 2, 95 + wob))
        self.text("GAME 2", 90, C_YELLOW, (W / 2, 165 + wob))
        self.text("the sequel is even more normal", 28, C_INK, (W / 2, 225), shadow=False)
        mouse = self.to_world(pg.mouse.get_pos())
        hover = self.play_btn.collidepoint(mouse)
        pg.draw.rect(self.world, (120, 90, 210), self.play_btn, border_radius=12)
        pg.draw.rect(self.world, C_WHITE if hover else C_INK, self.play_btn, 3, border_radius=12)
        self.text("PLAY", 44, C_WHITE, self.play_btn.center)
        if self.menu_quip:
            self.text(self.menu_quip, 30, C_RED, (self.play_btn.centerx, self.play_btn.top - 20))
        self.text("Enter = play    move: A/D or arrows    jump: W / Up / Space", 24, C_INK, (W / 2, H - 52), shadow=False)
        self.text("ESC = quit anytime    F11 = fullscreen focus mode", 24, C_INK, (W / 2, H - 26), shadow=False)

    def draw_loading(self):
        self.world.fill((25, 15, 40))
        t = self.state_t
        p = min(0.99, t / 2.2 * 0.99) if t < 3.0 else min(1.0, 0.99 + (t - 3.0) * 0.1)
        msgs = [(0.3, "Loading even more normal assets..."), (0.6, "Doubling the trolls..."),
                (0.85, "Installing screen effects you didn't ask for..."), (0.99, "Waking up Torgrim...")]
        label = next((m for lim, m in msgs if p < lim), "Almost, almost...")
        if self.load_skip:
            label = "Impatient AND back for the sequel. Bold."
        self.text("LOADING 2", 60, C_WHITE, (W / 2, 200))
        bar = pg.Rect(180, 250, 600, 34)
        pg.draw.rect(self.world, (60, 50, 80), bar, border_radius=6)
        pg.draw.rect(self.world, (150, 110, 230), (bar.x + 4, bar.y + 4, int((bar.w - 8) * p), bar.h - 8), border_radius=4)
        self.text(f"{int(p * 100)}%", 30, C_WHITE, bar.center)
        self.text(label, 28, (210, 200, 230), (W / 2, 320), shadow=False)
        self.text("press any key to skip", 22, (130, 120, 150), (W / 2, H - 30), shadow=False)

    def draw_end(self):
        self.draw_bg()
        self.draw_parts()
        d = self.deaths
        rank = ("Suspiciously good 2" if d <= 5 else "Normal human 2" if d <= 20
                else "Professional victim 2" if d <= 50 else "Torgrim's favourite 2")
        m, s = divmod(int(self.time), 60)
        self.text("YOU BEAT THE SEQUEL", 70, C_YELLOW, (W / 2, 120))
        self.text("(and it was totally normal the whole time)", 26, C_INK, (W / 2, 172), shadow=False)
        self.text(f"Deaths: {d}", 44, C_WHITE, (W / 2, 245))
        self.text(f"Time: {m:02d}:{s:02d}", 44, C_WHITE, (W / 2, 290))
        self.text(f"Rank: {rank}", 44, (255, 140, 140), (W / 2, 340))
        self.text("R = play again    Enter = menu", 26, C_INK, (W / 2, H - 40), shadow=False)

    def draw(self):
        st = self.state
        if st == "menu":
            self.draw_menu()
            self.draw_parts()
            self.present()
            return
        if st == "loading":
            self.draw_loading()
            self.present()
            return
        if st == "end":
            self.draw_end()
            self.present()
            return
        self.draw_bg()
        self.draw_level()
        self.draw_player()
        self.draw_parts()
        self.draw_hud()
        self.draw_popups()
        if st == "pause":
            ov = pg.Surface((W, H), pg.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            self.world.blit(ov, (0, 0))
            self.text("PAUSED", 80, C_WHITE, (W / 2, H / 2 - 40))
            self.text("P or ESC = resume    R = restart level    Q = menu", 28, C_WHITE, (W / 2, H / 2 + 30))
        self.present()

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