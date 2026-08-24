import json
import math
import os
import random
import sys
from array import array
from pathlib import Path

import pygame


WIDTH, HEIGHT = 800, 600
FPS = 60
PLAYER_SPEED = 430
STAR_SIZE = (44, 44)
BASKET_SIZE = (160, 72)
HEART_SIZE = (26, 26)
BASKET_BOTTOM_MARGIN = 16
HEART_GAP = 5
STARTING_LIVES = 3
MAX_LIVES = 5
BONUS_CHANCE = 0.12
LIFE_CHANCE = 0.05
DANGER_CHANCE = 0.09
COMBO_TIMEOUT = 3.2
WARNING_TIME = 0.55

DIFFICULTIES = {
    "easy": {"label": "ЛЕГКО", "speed": 0.82, "spawn": 1.16, "lives": 4},
    "normal": {"label": "ОБЫЧНО", "speed": 1.0, "spawn": 1.0, "lives": 3},
    "hard": {"label": "СЛОЖНО", "speed": 1.22, "spawn": 0.82, "lives": 3},
}

IVORY = (234, 228, 211)
SLATE = (102, 116, 137)
LIGHT_SLATE = (160, 174, 190)
NAVY = (38, 55, 78)
INK = (23, 38, 58)
FLASH_RED = (155, 54, 67)
BONUS_BLUE = (150, 190, 235)
LIFE_PINK = (230, 150, 172)
DANGER_RED = (143, 64, 76)

BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if getattr(sys, "frozen", False):
    DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "CatchTheStars"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    DATA_DIR = Path(__file__).resolve().parent
SAVE_FILE = DATA_DIR / "record.json"
ASSETS_DIR = BASE_DIR / "assets"


class PixelFont:
    """Рисует текст в низком разрешении и увеличивает его без сглаживания."""

    def __init__(self, size):
        self.scale = 2
        self.font = pygame.font.Font(None, max(10, size // self.scale))

    def render(self, text, antialias, color):
        small = self.font.render(text, False, color)
        return pygame.transform.scale(
            small,
            (small.get_width() * self.scale, small.get_height() * self.scale),
        )


def load_record():
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        return max(0, int(data.get("record", 0)))
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_record(record):
    try:
        SAVE_FILE.write_text(
            json.dumps({"record": record}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def make_tone(sequence, volume=0.22):
    sample_rate = 44100
    samples = array("h")
    for frequency, duration in sequence:
        count = int(sample_rate * duration)
        for index in range(count):
            attack = min(1.0, index / max(1, sample_rate * 0.008))
            release = min(1.0, (count - index) / max(1, sample_rate * 0.025))
            envelope = min(attack, release)
            value = math.sin(2 * math.pi * frequency * index / sample_rate)
            samples.append(int(32767 * volume * envelope * value))
    return pygame.mixer.Sound(buffer=samples.tobytes())


class Particle:
    def __init__(self, center, color):
        self.x, self.y = center
        self.vx = random.uniform(-115, 115)
        self.vy = random.uniform(-165, -45)
        self.life = random.uniform(0.28, 0.52)
        self.max_life = self.life
        self.size = random.choice((3, 4, 5))
        self.color = color

    def update(self, dt):
        self.life -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 310 * dt

    def draw(self, screen):
        if self.life <= 0:
            return
        alpha = int(255 * self.life / self.max_life)
        pixel = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        pixel.fill((*self.color, alpha))
        screen.blit(pixel, (round(self.x), round(self.y)))


class PopupText:
    def __init__(self, text, center, color):
        self.text = text
        self.x, self.y = center
        self.color = color
        self.life = 0.85
        self.max_life = self.life

    def update(self, dt):
        self.life -= dt
        self.y -= 42 * dt

    def draw(self, screen, font):
        if self.life <= 0:
            return
        image = font.render(self.text, False, self.color)
        alpha = max(0, min(255, round(255 * self.life / self.max_life)))
        image.set_alpha(alpha)
        screen.blit(image, image.get_rect(center=(round(self.x), round(self.y))))


class DriftingPixel:
    def __init__(self):
        self.x = random.uniform(0, WIDTH)
        self.y = random.uniform(105, HEIGHT - 95)
        self.speed = random.uniform(4, 13)
        self.size = random.choice((1, 1, 1, 2))
        self.color = random.choice((SLATE, LIGHT_SLATE, IVORY))

    def update(self, dt):
        self.x -= self.speed * dt
        self.y += math.sin(self.x * 0.018) * dt * 2
        if self.x < -3:
            self.x = WIDTH + random.uniform(0, 80)
            self.y = random.uniform(105, HEIGHT - 95)

    def draw(self, screen):
        pygame.draw.rect(
            screen,
            self.color,
            (round(self.x), round(self.y), self.size, self.size),
        )


class FallingStar:
    def __init__(self, level, images, difficulty, spawn_x=None):
        roll = random.random()
        if roll < DANGER_CHANCE:
            self.kind = "danger"
        elif roll < DANGER_CHANCE + LIFE_CHANCE:
            self.kind = "life"
        elif roll < DANGER_CHANCE + LIFE_CHANCE + BONUS_CHANCE:
            self.kind = "bonus"
        else:
            self.kind = "normal"

        self.value = 3 if self.kind == "bonus" else 1
        self.image = images[self.kind]
        margin = STAR_SIZE[0] // 2
        self.x = spawn_x if spawn_x is not None else random.randint(margin, WIDTH - margin)
        self.y = -STAR_SIZE[1]
        self.speed = (random.uniform(170, 225) + level * 15) * difficulty["speed"]
        self.age = random.uniform(0, 1)
        self.rect = self.image.get_rect()
        self.update_rect()

    def update_rect(self):
        self.rect.center = (round(self.x), round(self.y))

    def update(self, dt):
        self.age += dt
        self.y += self.speed * dt
        self.update_rect()

    def draw(self, screen):
        pulse = 4 if int(self.age * 8) % 8 == 0 else 0
        if pulse:
            image = pygame.transform.scale(
                self.image,
                (STAR_SIZE[0] + pulse, STAR_SIZE[1] + pulse),
            )
            rect = image.get_rect(center=self.rect.center)
        else:
            image = self.image
            rect = self.rect
        screen.blit(image, rect)


class Basket:
    def __init__(self, image):
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.midbottom = (WIDTH // 2, HEIGHT - BASKET_BOTTOM_MARGIN)
        self.bounce_timer = 0.0
        self.elapsed = 0.0

    @property
    def catch_rect(self):
        return pygame.Rect(
            self.rect.left + 22,
            self.rect.top + 5,
            self.rect.width - 44,
            22,
        )

    def bounce(self):
        self.bounce_timer = 0.16

    def update(self, dt):
        self.elapsed += dt
        self.bounce_timer = max(0.0, self.bounce_timer - dt)
        keys = pygame.key.get_pressed()
        direction = (
            keys[pygame.K_RIGHT]
            + keys[pygame.K_d]
            - keys[pygame.K_LEFT]
            - keys[pygame.K_a]
        )
        self.rect.x += round(direction * PLAYER_SPEED * dt)
        self.rect.clamp_ip(pygame.Rect(12, 0, WIDTH - 24, HEIGHT))

    def draw(self, screen):
        idle_offset = round(math.sin(self.elapsed * 3.5))
        if self.bounce_timer > 0:
            phase = self.bounce_timer / 0.16
            image = pygame.transform.scale(
                self.image,
                (BASKET_SIZE[0] + round(10 * phase), BASKET_SIZE[1] - round(5 * phase)),
            )
            rect = image.get_rect(midbottom=self.rect.midbottom)
        else:
            image = self.image
            rect = self.rect.move(0, idle_offset)
        screen.blit(image, rect)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Лови звёзды")
        self.windowed_size = (WIDTH, HEIGHT)
        self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.fullscreen = False
        self.clock = pygame.time.Clock()

        self.font = PixelFont(36)
        self.big_font = PixelFont(76)
        self.medium_font = PixelFont(44)
        self.small_font = PixelFont(27)
        self.tiny_font = PixelFont(22)

        self.background = pygame.image.load(ASSETS_DIR / "background.png").convert()
        self.star_image = pygame.transform.scale(
            pygame.image.load(ASSETS_DIR / "star.png").convert_alpha(), STAR_SIZE
        )
        self.basket_image = pygame.transform.scale(
            pygame.image.load(ASSETS_DIR / "basket.png").convert_alpha(), BASKET_SIZE
        )
        self.heart_image = pygame.transform.scale(
            pygame.image.load(ASSETS_DIR / "heart.png").convert_alpha(), HEART_SIZE
        )
        self.star_images = {
            "normal": self.star_image,
            "bonus": pygame.transform.scale(
                pygame.image.load(ASSETS_DIR / "star_bonus.png").convert_alpha(), STAR_SIZE
            ),
            "life": pygame.transform.scale(
                pygame.image.load(ASSETS_DIR / "star_life.png").convert_alpha(), STAR_SIZE
            ),
            "danger": pygame.transform.scale(
                pygame.image.load(ASSETS_DIR / "star_danger.png").convert_alpha(), STAR_SIZE
            ),
        }
        pygame.display.set_icon(self.star_image)

        self.sounds = {}
        self.sound_enabled = True
        try:
            if pygame.mixer.get_init() is not None:
                pygame.mixer.quit()
            pygame.mixer.init(frequency=44100, size=-16, channels=1)
            self.sounds = {
                "catch": make_tone(((660, 0.045), (880, 0.07))),
                "bonus": make_tone(((660, 0.04), (990, 0.05), (1320, 0.09))),
                "life": make_tone(((540, 0.04), (810, 0.05), (1080, 0.12))),
                "danger": make_tone(((165, 0.09), (110, 0.16)), 0.2),
                "miss": make_tone(((210, 0.08), (145, 0.13)), 0.18),
                "game_over": make_tone(((300, 0.1), (220, 0.12), (145, 0.22)), 0.18),
                "count": make_tone(((440, 0.055),), 0.15),
                "start": make_tone(((660, 0.04), (990, 0.09)), 0.18),
                "click": make_tone(((520, 0.04),), 0.15),
            }
        except pygame.error:
            self.sound_enabled = False

        self.difficulty_buttons = {
            "easy": pygame.Rect(205, 327, 120, 40),
            "normal": pygame.Rect(340, 327, 120, 40),
            "hard": pygame.Rect(475, 327, 120, 40),
        }
        self.play_button = pygame.Rect(WIDTH // 2 - 115, 386, 230, 58)
        self.menu_sound_button = pygame.Rect(WIDTH // 2 - 115, 458, 230, 44)
        self.resume_button = pygame.Rect(WIDTH // 2 - 115, 335, 230, 54)
        self.retry_button = pygame.Rect(WIDTH // 2 - 125, 472, 250, 54)
        self.sound_toggle_rect = pygame.Rect(WIDTH - 132, 70, 118, 30)

        self.record = load_record()
        self.running = True
        self.state = "menu"
        self.difficulty_name = "normal"
        self.background_pixels = [DriftingPixel() for _ in range(42)]
        self.reset_round()

    def reset_round(self):
        self.player = Basket(self.basket_image)
        self.stars = []
        self.particles = []
        self.popup_texts = []
        self.score = 0
        self.lives = DIFFICULTIES[self.difficulty_name]["lives"]
        self.combo = 0
        self.best_combo = 0
        self.combo_timer = 0.0
        self.combo_message_timer = 0.0
        self.spawn_timer = 0.4
        self.pending_star = None
        self.warning_timer = 0.0
        self.flash_timer = 0.0
        self.countdown_timer = 3.0
        self.countdown_number = 4
        self.play_time = 0.0
        self.caught_total = 0
        self.caught_bonus = 0
        self.caught_life = 0
        self.caught_danger = 0
        self.missed_total = 0

    def start_game(self):
        self.reset_round()
        self.state = "countdown"
        self.play_sound("click")

    @property
    def level(self):
        return self.score // 8

    @property
    def multiplier(self):
        return 2 if self.combo >= 3 else 1

    def play_sound(self, name):
        if self.sound_enabled and name in self.sounds:
            self.sounds[name].play()

    def toggle_sound(self):
        if not self.sounds:
            self.sound_enabled = False
            return
        self.sound_enabled = not self.sound_enabled
        if self.sound_enabled:
            self.play_sound("click")
        else:
            pygame.mixer.stop()

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.windowed_size = self.window.get_size()
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)

    def scale_info(self):
        window_width, window_height = self.window.get_size()
        scale = min(window_width / WIDTH, window_height / HEIGHT)
        target_size = (max(1, round(WIDTH * scale)), max(1, round(HEIGHT * scale)))
        offset = (
            (window_width - target_size[0]) // 2,
            (window_height - target_size[1]) // 2,
        )
        return scale, target_size, offset

    def logical_mouse_position(self, position=None):
        if position is None:
            position = pygame.mouse.get_pos()
        scale, target_size, offset = self.scale_info()
        x = position[0] - offset[0]
        y = position[1] - offset[1]
        if x < 0 or y < 0 or x >= target_size[0] or y >= target_size[1]:
            return (-1000, -1000)
        return (round(x / scale), round(y / scale))

    def spawn_particles(self, center, kind="normal"):
        colors = {
            "normal": IVORY,
            "bonus": BONUS_BLUE,
            "life": LIFE_PINK,
            "danger": DANGER_RED,
        }
        count = 16 if kind in ("bonus", "life") else 10
        self.particles.extend(Particle(center, colors[kind]) for _ in range(count))

    def lose_life(self, sound="miss"):
        self.lives -= 1
        self.combo = 0
        self.combo_timer = 0.0
        self.flash_timer = 0.2
        self.play_sound(sound)
        if self.lives <= 0:
            self.state = "game_over"
            save_record(self.record)
            self.play_sound("game_over")

    def catch_star(self, star):
        self.player.bounce()
        self.spawn_particles(star.rect.center, star.kind)
        if star.kind == "danger":
            self.caught_danger += 1
            self.popup_texts.append(PopupText("-1 ЖИЗНЬ", star.rect.center, DANGER_RED))
            self.lose_life("danger")
            return

        self.combo += 1
        self.best_combo = max(self.best_combo, self.combo)
        self.combo_timer = COMBO_TIMEOUT
        self.combo_message_timer = 0.8
        self.caught_total += 1
        if star.kind == "life":
            self.caught_life += 1
            if self.lives < MAX_LIVES:
                self.lives += 1
                popup = "+ЖИЗНЬ"
            else:
                self.score += 2 * self.multiplier
                popup = f"+{2 * self.multiplier}"
            self.popup_texts.append(PopupText(popup, star.rect.center, LIFE_PINK))
            self.play_sound("life")
        else:
            points = star.value * self.multiplier
            self.score += points
            if star.kind == "bonus":
                self.caught_bonus += 1
            self.popup_texts.append(
                PopupText(f"+{points}", star.rect.center, BONUS_BLUE if star.kind == "bonus" else IVORY)
            )
            self.play_sound("bonus" if star.kind == "bonus" else "catch")

        if self.score > self.record:
            self.record = self.score
            save_record(self.record)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.windowed_size = (max(480, event.w), max(360, event.h))
                self.window = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self.toggle_fullscreen()
                elif event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"
                    elif self.state == "countdown":
                        self.state = "menu"
                    else:
                        self.running = False
                elif event.key == pygame.K_p and self.state in ("playing", "paused"):
                    self.state = "paused" if self.state == "playing" else "playing"
                    self.play_sound("click")
                elif event.key == pygame.K_m:
                    self.toggle_sound()
                elif self.state == "menu" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    self.difficulty_name = {
                        pygame.K_1: "easy",
                        pygame.K_2: "normal",
                        pygame.K_3: "hard",
                    }[event.key]
                    self.reset_round()
                    self.play_sound("click")
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state in ("menu", "game_over"):
                        self.start_game()
                    elif self.state == "paused":
                        self.state = "playing"
                elif event.key == pygame.K_r and self.state == "game_over":
                    self.start_game()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mouse_pos = self.logical_mouse_position(event.pos)
                if self.state == "menu":
                    if self.play_button.collidepoint(mouse_pos):
                        self.start_game()
                    elif self.menu_sound_button.collidepoint(mouse_pos):
                        self.toggle_sound()
                    else:
                        for name, button in self.difficulty_buttons.items():
                            if button.collidepoint(mouse_pos):
                                self.difficulty_name = name
                                self.reset_round()
                                self.play_sound("click")
                                break
                elif self.state == "paused" and self.resume_button.collidepoint(mouse_pos):
                    self.state = "playing"
                    self.play_sound("click")
                elif self.state == "game_over" and self.retry_button.collidepoint(mouse_pos):
                    self.start_game()
                elif self.sound_toggle_rect.collidepoint(mouse_pos):
                    self.toggle_sound()

    def update(self, dt):
        for pixel in self.background_pixels:
            pixel.update(dt)

        if self.state == "countdown":
            self.countdown_timer -= dt
            number = max(1, math.ceil(self.countdown_timer))
            if number != self.countdown_number:
                self.countdown_number = number
                self.play_sound("count")
            if self.countdown_timer <= 0:
                self.state = "playing"
                self.play_sound("start")
            return

        if self.state != "playing":
            return

        self.play_time += dt
        self.player.update(dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.combo_message_timer = max(0.0, self.combo_message_timer - dt)
        if self.combo > 0:
            self.combo_timer = max(0.0, self.combo_timer - dt)
            if self.combo_timer <= 0:
                self.combo = 0

        for particle in self.particles[:]:
            particle.update(dt)
            if particle.life <= 0:
                self.particles.remove(particle)
        for popup in self.popup_texts[:]:
            popup.update(dt)
            if popup.life <= 0:
                self.popup_texts.remove(popup)

        self.spawn_timer -= dt
        difficulty = DIFFICULTIES[self.difficulty_name]
        if self.spawn_timer <= 0 and self.pending_star is None:
            self.pending_star = FallingStar(self.level, self.star_images, difficulty)
            self.warning_timer = WARNING_TIME
        if self.pending_star is not None:
            self.warning_timer -= dt
            if self.warning_timer <= 0:
                self.stars.append(self.pending_star)
                self.pending_star = None
                base_delay = random.uniform(0.72, 1.05) - self.level * 0.045
                self.spawn_timer = max(0.3, base_delay * difficulty["spawn"])

        for star in self.stars[:]:
            star.update(dt)
            if self.player.catch_rect.collidepoint(star.rect.midbottom):
                self.stars.remove(star)
                self.catch_star(star)
                if self.state == "game_over":
                    break
            elif star.rect.top > HEIGHT:
                self.stars.remove(star)
                if star.kind != "danger":
                    self.missed_total += 1
                    self.lose_life()
                    if self.state == "game_over":
                        break

    def draw_text(self, text, font, color, center, shadow=True):
        image = font.render(text, False, color)
        rect = image.get_rect(center=center)
        if shadow:
            shadow_image = font.render(text, False, (7, 12, 20))
            self.screen.blit(shadow_image, rect.move(3, 3))
        self.screen.blit(image, rect)

    def draw_panel(self, rect, fill=INK):
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, SLATE, rect, 2)
        pygame.draw.line(
            self.screen,
            IVORY,
            (rect.left + 4, rect.top + 4),
            (rect.right - 5, rect.top + 4),
            1,
        )

    def draw_button(self, rect, text, font=None):
        font = font or self.small_font
        hovered = rect.collidepoint(self.logical_mouse_position())
        fill = SLATE if hovered else NAVY
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, IVORY, rect, 2)
        self.draw_text(text, font, IVORY, rect.center, shadow=False)

    def draw_choice_button(self, rect, text, selected):
        hovered = rect.collidepoint(self.logical_mouse_position())
        fill = IVORY if selected else (SLATE if hovered else NAVY)
        text_color = INK if selected else IVORY
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, IVORY, rect, 2)
        self.draw_text(text, self.tiny_font, text_color, rect.center, shadow=False)

    def draw_background(self):
        self.screen.blit(self.background, (0, 0))
        for pixel in self.background_pixels:
            pixel.draw(self.screen)

    def draw_hud(self):
        left_panel = pygame.Rect(14, 12, 192, 120)
        self.draw_panel(left_panel)
        self.screen.blit(self.font.render(f"Счёт: {self.score}", False, IVORY), (26, 20))
        self.screen.blit(self.tiny_font.render(f"Рекорд: {self.record}", False, LIGHT_SLATE), (26, 58))
        self.screen.blit(self.tiny_font.render(f"Уровень: {self.level + 1}", False, LIGHT_SLATE), (26, 80))
        combo_text = f"Комбо: {self.combo}  x{self.multiplier}"
        combo_color = BONUS_BLUE if self.multiplier > 1 else LIGHT_SLATE
        self.screen.blit(self.tiny_font.render(combo_text, False, combo_color), (26, 101))
        bar_rect = pygame.Rect(26, 121, 160, 5)
        pygame.draw.rect(self.screen, NAVY, bar_rect)
        if self.combo > 0:
            filled = round(bar_rect.width * self.combo_timer / COMBO_TIMEOUT)
            pygame.draw.rect(self.screen, combo_color, (bar_rect.x, bar_rect.y, filled, bar_rect.height))

        lives_label = self.small_font.render("Жизни:", False, IVORY)
        hearts_width = MAX_LIVES * HEART_SIZE[0] + (MAX_LIVES - 1) * HEART_GAP
        right_panel_width = lives_label.get_width() + hearts_width + 30
        right_panel = pygame.Rect(WIDTH - right_panel_width - 14, 12, right_panel_width, 48)
        self.draw_panel(right_panel)
        lives_x = right_panel.left + 10
        self.screen.blit(lives_label, (lives_x, 22))
        hearts_x = lives_x + lives_label.get_width() + 8
        for index in range(MAX_LIVES):
            heart_x = hearts_x + index * (HEART_SIZE[0] + HEART_GAP)
            if index < self.lives:
                self.screen.blit(self.heart_image, (heart_x, 23))
            else:
                pygame.draw.rect(self.screen, SLATE, (heart_x + 6, 30, 14, 11), 1)

        sound_text = "ЗВУК: ВКЛ" if self.sound_enabled else "ЗВУК: ВЫКЛ"
        self.draw_button(self.sound_toggle_rect, sound_text, self.tiny_font)

        if self.combo >= 3 and self.combo_message_timer > 0:
            self.draw_text(
                f"КОМБО {self.combo}  x2!",
                self.medium_font,
                BONUS_BLUE,
                (WIDTH // 2, 145),
            )

    def draw_menu(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((12, 25, 41, 125))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 250, 42, 500, 520)
        self.draw_panel(panel)
        self.draw_text("ЛОВИ ЗВЁЗДЫ", self.big_font, IVORY, (WIDTH // 2, 112))
        self.draw_text("пиксельная аркада", self.small_font, LIGHT_SLATE, (WIDTH // 2, 160))
        self.draw_text("← → или A / D — движение", self.small_font, IVORY, (WIDTH // 2, 205), shadow=False)
        self.draw_text("P — пауза   M — звук   F11 — весь экран", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 234), shadow=False)
        self.draw_text("Синяя +3   Розовая +жизнь   Тёмную не лови", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 275), shadow=False)
        self.draw_text("СЛОЖНОСТЬ", self.tiny_font, IVORY, (WIDTH // 2, 306), shadow=False)
        for name, button in self.difficulty_buttons.items():
            self.draw_choice_button(
                button,
                DIFFICULTIES[name]["label"],
                name == self.difficulty_name,
            )
        self.draw_button(self.play_button, "ИГРАТЬ", self.medium_font)
        sound_text = "ЗВУК: ВКЛ" if self.sound_enabled else "ЗВУК: ВЫКЛ"
        self.draw_button(self.menu_sound_button, sound_text)
        self.draw_text("Клавиши 1 / 2 / 3 тоже выбирают сложность", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 530), shadow=False)

    def draw_pause(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 22, 38, 190))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 190, 205, 380, 230)
        self.draw_panel(panel)
        self.draw_text("ПАУЗА", self.big_font, IVORY, (WIDTH // 2, 275))
        self.draw_button(self.resume_button, "ПРОДОЛЖИТЬ")
        self.draw_text("P или Esc — продолжить", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 410), shadow=False)

    def draw_countdown(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 22, 38, 145))
        self.screen.blit(overlay, (0, 0))
        number = max(1, math.ceil(self.countdown_timer))
        self.draw_text(str(number), self.big_font, IVORY, (WIDTH // 2, HEIGHT // 2 - 10))
        self.draw_text("ПРИГОТОВЬСЯ", self.small_font, LIGHT_SLATE, (WIDTH // 2, HEIGHT // 2 + 62), shadow=False)

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 22, 38, 205))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 245, 48, 490, 534)
        self.draw_panel(panel)
        self.draw_text("ИГРА ОКОНЧЕНА", self.big_font, IVORY, (WIDTH // 2, 112))
        self.draw_text(f"Счёт: {self.score}", self.font, IVORY, (WIDTH // 2, 174))
        self.draw_text(f"Рекорд: {self.record}", self.small_font, BONUS_BLUE, (WIDTH // 2, 212), shadow=False)
        stats = (
            f"Сложность: {DIFFICULTIES[self.difficulty_name]['label']}",
            f"Поймано полезных: {self.caught_total}",
            f"Бонусных звёзд: {self.caught_bonus}",
            f"Звёзд-жизней: {self.caught_life}",
            f"Пропущено: {self.missed_total}",
            f"Поймано опасных: {self.caught_danger}",
            f"Лучшее комбо: {self.best_combo}",
            f"Время игры: {self.play_time:.1f} сек.",
        )
        for index, line in enumerate(stats):
            self.draw_text(line, self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 248 + index * 27), shadow=False)
        self.draw_button(self.retry_button, "СЫГРАТЬ СНОВА")
        self.draw_text("Enter или R — новая игра", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 552), shadow=False)

    def draw_spawn_warning(self):
        if self.pending_star is None:
            return
        colors = {
            "normal": IVORY,
            "bonus": BONUS_BLUE,
            "life": LIFE_PINK,
            "danger": DANGER_RED,
        }
        x = round(self.pending_star.x)
        color = colors[self.pending_star.kind]
        blink = int(self.warning_timer * 14) % 2 == 0
        if blink:
            pygame.draw.polygon(self.screen, color, ((x - 9, 143), (x + 9, 143), (x, 154)))
            pygame.draw.line(self.screen, INK, (x - 9, 142), (x + 9, 142), 2)

    def present(self):
        _, target_size, offset = self.scale_info()
        scaled = pygame.transform.scale(self.screen, target_size)
        self.window.fill(INK)
        self.window.blit(scaled, offset)
        pygame.display.flip()

    def draw(self):
        self.draw_background()
        if self.state == "menu":
            self.player.draw(self.screen)
            self.draw_menu()
            self.present()
            return

        for star in self.stars:
            star.draw(self.screen)
        for particle in self.particles:
            particle.draw(self.screen)
        for popup in self.popup_texts:
            popup.draw(self.screen, self.small_font)
        self.player.draw(self.screen)
        self.draw_hud()
        self.draw_spawn_warning()

        if self.flash_timer > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(100 * self.flash_timer / 0.2)
            flash.fill((*FLASH_RED, alpha))
            self.screen.blit(flash, (0, 0))

        if self.state == "countdown":
            self.draw_countdown()
        elif self.state == "paused":
            self.draw_pause()
        elif self.state == "game_over":
            self.draw_game_over()
        self.present()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
