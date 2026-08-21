import json
import math
import random
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
HEART_GAP = 6
STARTING_LIVES = 3
BONUS_CHANCE = 0.12

IVORY = (234, 228, 211)
SLATE = (102, 116, 137)
LIGHT_SLATE = (160, 174, 190)
NAVY = (38, 55, 78)
INK = (23, 38, 58)
FLASH_RED = (155, 54, 67)

SAVE_FILE = Path(__file__).with_name("record.json")
ASSETS_DIR = Path(__file__).with_name("assets")


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
        self.vx = random.uniform(-105, 105)
        self.vy = random.uniform(-150, -45)
        self.life = random.uniform(0.28, 0.5)
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


class FallingStar:
    def __init__(self, level, normal_image, bonus_image):
        self.is_bonus = random.random() < BONUS_CHANCE
        self.value = 3 if self.is_bonus else 1
        self.image = bonus_image if self.is_bonus else normal_image
        margin = STAR_SIZE[0] // 2
        self.x = random.randint(margin, WIDTH - margin)
        self.y = -STAR_SIZE[1]
        self.speed = random.uniform(170, 225) + level * 15
        self.rect = self.image.get_rect()
        self.update_rect()

    def update_rect(self):
        self.rect.center = (round(self.x), round(self.y))

    def update(self, dt):
        self.y += self.speed * dt
        self.update_rect()

    def draw(self, screen):
        screen.blit(self.image, self.rect)
        if self.is_bonus:
            pygame.draw.rect(screen, IVORY, self.rect.inflate(4, 4), 1)


class Basket:
    def __init__(self, image):
        self.image = image
        self.rect = self.image.get_rect()
        self.rect.midbottom = (WIDTH // 2, HEIGHT - BASKET_BOTTOM_MARGIN)

    @property
    def catch_rect(self):
        return pygame.Rect(
            self.rect.left + 22,
            self.rect.top + 5,
            self.rect.width - 44,
            22,
        )

    def update(self, dt):
        keys = pygame.key.get_pressed()
        direction = keys[pygame.K_RIGHT] + keys[pygame.K_d] - keys[pygame.K_LEFT] - keys[pygame.K_a]
        self.rect.x += round(direction * PLAYER_SPEED * dt)
        self.rect.clamp_ip(pygame.Rect(12, 0, WIDTH - 24, HEIGHT))

    def draw(self, screen):
        screen.blit(self.image, self.rect)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Лови звёзды")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.big_font = pygame.font.Font(None, 76)
        self.medium_font = pygame.font.Font(None, 44)
        self.small_font = pygame.font.Font(None, 27)
        self.tiny_font = pygame.font.Font(None, 22)

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
        self.bonus_star_image = self.star_image.copy()
        bonus_tint = pygame.Surface(STAR_SIZE, pygame.SRCALPHA)
        bonus_tint.fill((150, 190, 235, 255))
        self.bonus_star_image.blit(bonus_tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
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
                "miss": make_tone(((210, 0.08), (145, 0.13)), 0.18),
                "game_over": make_tone(((300, 0.1), (220, 0.12), (145, 0.22)), 0.18),
                "click": make_tone(((520, 0.04),), 0.15),
            }
        except pygame.error:
            self.sound_enabled = False

        self.play_button = pygame.Rect(WIDTH // 2 - 115, 326, 230, 58)
        self.menu_sound_button = pygame.Rect(WIDTH // 2 - 115, 400, 230, 48)
        self.resume_button = pygame.Rect(WIDTH // 2 - 115, 335, 230, 54)
        self.retry_button = pygame.Rect(WIDTH // 2 - 125, 374, 250, 54)
        self.sound_toggle_rect = pygame.Rect(WIDTH - 132, 70, 118, 30)

        self.record = load_record()
        self.running = True
        self.state = "menu"
        self.reset_round()

    def reset_round(self):
        self.player = Basket(self.basket_image)
        self.stars = []
        self.particles = []
        self.score = 0
        self.lives = STARTING_LIVES
        self.spawn_timer = 0.4
        self.flash_timer = 0.0

    def start_game(self):
        self.reset_round()
        self.state = "playing"
        self.play_sound("click")

    @property
    def level(self):
        return self.score // 8

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

    def spawn_particles(self, center, bonus=False):
        color = LIGHT_SLATE if bonus else IVORY
        count = 15 if bonus else 9
        self.particles.extend(Particle(center, color) for _ in range(count))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.state = "paused"
                    elif self.state == "paused":
                        self.state = "playing"
                    else:
                        self.running = False
                elif event.key == pygame.K_p and self.state in ("playing", "paused"):
                    self.state = "paused" if self.state == "playing" else "playing"
                    self.play_sound("click")
                elif event.key == pygame.K_m:
                    self.toggle_sound()
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    if self.state in ("menu", "game_over"):
                        self.start_game()
                    elif self.state == "paused":
                        self.state = "playing"
                elif event.key == pygame.K_r and self.state == "game_over":
                    self.start_game()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.state == "menu":
                    if self.play_button.collidepoint(event.pos):
                        self.start_game()
                    elif self.menu_sound_button.collidepoint(event.pos):
                        self.toggle_sound()
                elif self.state == "paused" and self.resume_button.collidepoint(event.pos):
                    self.state = "playing"
                    self.play_sound("click")
                elif self.state == "game_over" and self.retry_button.collidepoint(event.pos):
                    self.start_game()
                elif self.sound_toggle_rect.collidepoint(event.pos):
                    self.toggle_sound()

    def update(self, dt):
        if self.state != "playing":
            return

        self.player.update(dt)
        self.flash_timer = max(0.0, self.flash_timer - dt)

        for particle in self.particles[:]:
            particle.update(dt)
            if particle.life <= 0:
                self.particles.remove(particle)

        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.stars.append(FallingStar(self.level, self.star_image, self.bonus_star_image))
            self.spawn_timer = max(0.3, random.uniform(0.72, 1.05) - self.level * 0.045)

        for star in self.stars[:]:
            star.update(dt)
            if self.player.catch_rect.collidepoint(star.rect.midbottom):
                self.stars.remove(star)
                self.score += star.value
                self.spawn_particles(star.rect.center, star.is_bonus)
                self.play_sound("bonus" if star.is_bonus else "catch")
                if self.score > self.record:
                    self.record = self.score
                    save_record(self.record)
            elif star.rect.top > HEIGHT:
                self.stars.remove(star)
                self.lives -= 1
                self.flash_timer = 0.18
                self.play_sound("miss")
                if self.lives <= 0:
                    self.state = "game_over"
                    save_record(self.record)
                    self.play_sound("game_over")
                    break

    def draw_text(self, text, font, color, center, shadow=True):
        image = font.render(text, True, color)
        rect = image.get_rect(center=center)
        if shadow:
            shadow_image = font.render(text, True, (7, 12, 20))
            self.screen.blit(shadow_image, rect.move(3, 3))
        self.screen.blit(image, rect)

    def draw_panel(self, rect, fill=INK):
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, SLATE, rect, 2)
        pygame.draw.line(self.screen, IVORY, (rect.left + 4, rect.top + 4), (rect.right - 5, rect.top + 4), 1)

    def draw_button(self, rect, text, font=None):
        font = font or self.small_font
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        fill = SLATE if hovered else NAVY
        pygame.draw.rect(self.screen, fill, rect)
        pygame.draw.rect(self.screen, IVORY, rect, 2)
        self.draw_text(text, font, IVORY, rect.center, shadow=False)

    def draw_hud(self):
        left_panel = pygame.Rect(14, 12, 178, 90)
        self.draw_panel(left_panel)

        score_image = self.font.render(f"Счёт: {self.score}", True, IVORY)
        record_image = self.tiny_font.render(f"Рекорд: {self.record}", True, LIGHT_SLATE)
        level_image = self.tiny_font.render(f"Уровень: {self.level + 1}", True, LIGHT_SLATE)
        self.screen.blit(score_image, (26, 20))
        self.screen.blit(record_image, (26, 58))
        self.screen.blit(level_image, (26, 79))

        lives_label = self.small_font.render("Жизни:", True, IVORY)
        hearts_width = STARTING_LIVES * HEART_SIZE[0] + (STARTING_LIVES - 1) * HEART_GAP
        right_panel_width = lives_label.get_width() + hearts_width + 32
        right_panel = pygame.Rect(WIDTH - right_panel_width - 14, 12, right_panel_width, 48)
        self.draw_panel(right_panel)

        lives_x = right_panel.left + 10
        self.screen.blit(lives_label, (lives_x, 22))
        hearts_x = lives_x + lives_label.get_width() + 8
        for index in range(self.lives):
            heart_x = hearts_x + index * (HEART_SIZE[0] + HEART_GAP)
            self.screen.blit(self.heart_image, (heart_x, 23))

        sound_text = "ЗВУК: ВКЛ" if self.sound_enabled else "ЗВУК: ВЫКЛ"
        self.draw_button(self.sound_toggle_rect, sound_text, self.tiny_font)

    def draw_menu(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((12, 25, 41, 125))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(WIDTH // 2 - 230, 105, 460, 405)
        self.draw_panel(panel)
        self.draw_text("ЛОВИ ЗВЁЗДЫ", self.big_font, IVORY, (WIDTH // 2, 176))
        self.draw_text("монохромная пиксельная аркада", self.small_font, LIGHT_SLATE, (WIDTH // 2, 225))
        self.draw_text("← → или A / D — движение", self.small_font, IVORY, (WIDTH // 2, 270), shadow=False)
        self.draw_text("P — пауза     M — звук", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 300), shadow=False)
        self.draw_button(self.play_button, "ИГРАТЬ", self.medium_font)
        sound_text = "ЗВУК: ВКЛ" if self.sound_enabled else "ЗВУК: ВЫКЛ"
        self.draw_button(self.menu_sound_button, sound_text)
        self.draw_text("Бонусная звезда приносит +3", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 470), shadow=False)

    def draw_pause(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 22, 38, 190))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 190, 205, 380, 230)
        self.draw_panel(panel)
        self.draw_text("ПАУЗА", self.big_font, IVORY, (WIDTH // 2, 275))
        self.draw_button(self.resume_button, "ПРОДОЛЖИТЬ")
        self.draw_text("P или Esc — продолжить", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 410), shadow=False)

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 22, 38, 205))
        self.screen.blit(overlay, (0, 0))
        panel = pygame.Rect(WIDTH // 2 - 235, 155, 470, 315)
        self.draw_panel(panel)
        self.draw_text("ИГРА ОКОНЧЕНА", self.big_font, IVORY, (WIDTH // 2, 225))
        self.draw_text(f"Собрано звёзд: {self.score}", self.font, IVORY, (WIDTH // 2, 300))
        self.draw_text(f"Рекорд: {self.record}", self.small_font, LIGHT_SLATE, (WIDTH // 2, 340), shadow=False)
        self.draw_button(self.retry_button, "СЫГРАТЬ СНОВА")
        self.draw_text("Enter или R — новая игра", self.tiny_font, LIGHT_SLATE, (WIDTH // 2, 450), shadow=False)

    def draw(self):
        self.screen.blit(self.background, (0, 0))

        if self.state == "menu":
            self.player.draw(self.screen)
            self.draw_menu()
            pygame.display.flip()
            return

        for star in self.stars:
            star.draw(self.screen)
        for particle in self.particles:
            particle.draw(self.screen)
        self.player.draw(self.screen)
        self.draw_hud()

        if self.flash_timer > 0:
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(95 * self.flash_timer / 0.18)
            flash.fill((*FLASH_RED, alpha))
            self.screen.blit(flash, (0, 0))

        if self.state == "paused":
            self.draw_pause()
        elif self.state == "game_over":
            self.draw_game_over()

        pygame.display.flip()

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
