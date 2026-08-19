import json, math, random, struct
from datetime import datetime
from pathlib import Path
import pygame

CELL, COLS, ROWS, HUD, FPS = 24, 28, 22, 72, 60
WIDTH, HEIGHT = COLS * CELL, ROWS * CELL + HUD
SAVE_FILE = Path(__file__).with_name("save.json")

THEMES = {
    "Clover": {"bg": (240,230,197), "grid": (224,185,121), "panel": (128,72,52), "head": (166,106,60), "body": (165,167,125), "food": (228,170,182), "text": (240,230,197), "muted": (228,170,182), "rock": (131,157,164)},
    "Cyber": {"bg": (12,18,30), "grid": (29,42,63), "panel": (22,30,48), "head": (64,255,196), "body": (30,180,150), "food": (255,68,151), "text": (226,242,255), "muted": (102,163,255), "rock": (126,87,194)},
    "Game Boy": {"bg": (202,220,159), "grid": (174,196,125), "panel": (48,98,48), "head": (15,56,15), "body": (79,126,44), "food": (130,158,60), "text": (202,220,159), "muted": (174,196,125), "rock": (90,110,50)},
}
DIFFICULTIES = {"Лёгкая": (175, 0), "Обычная": (135, 6), "Сложная": (95, 12)}
MODES = ["Классика", "Сквозь стены", "На время", "Два игрока"]


def load_data():
    result = {"scores": [], "theme": "Clover", "sound": True}
    try: result.update(json.loads(SAVE_FILE.read_text(encoding="utf-8")))
    except (FileNotFoundError, json.JSONDecodeError, TypeError): pass
    return result


def save_data(data):
    SAVE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tone(freq, duration=.1):
    rate, raw = 22050, bytearray()
    count = int(rate * duration)
    for i in range(count):
        value = int(6500 * (1 - i / count) * math.sin(2 * math.pi * freq * i / rate))
        raw.extend(struct.pack("<h", value))
    return pygame.mixer.Sound(buffer=bytes(raw))


def melody():
    rate, raw = 22050, bytearray()
    notes = [262, 330, 392, 330, 294, 349, 440, 349]
    for freq in notes:
        count = int(rate * .22)
        for i in range(count):
            envelope = min(1, i / 400) * min(1, (count - i) / 700)
            value = int(1800 * envelope * math.sin(2 * math.pi * freq * i / rate))
            raw.extend(struct.pack("<h", value))
    return pygame.mixer.Sound(buffer=bytes(raw))


def build_sounds():
    try: return {"eat": tone(660), "bonus": tone(920, .16), "lose": tone(170, .35), "music": melody()}
    except pygame.error: return {}


def free_cell(blocked):
    cells = [(x, y) for x in range(COLS) for y in range(ROWS) if (x, y) not in blocked]
    return random.choice(cells) if cells else None


def new_snake(center, direction, second=False):
    x, y = center; dx, dy = direction
    return {"body": [(x,y), (x-dx,y-dy), (x-2*dx,y-2*dy)], "dir": direction,
            "next": direction, "alive": True, "score": 0, "second": second}


class Game:
    def __init__(self):
        self.data = load_data(); self.theme_name = self.data["theme"]; self.sound = self.data["sound"]
        self.difficulty, self.mode, self.state = "Обычная", "Классика", "menu"
        self.menu_index = self.settings_index = 0; self.name = "PLAYER"; self.name_saved = False
        self.sounds = build_sounds(); self.particles = []; self.reset()
        if self.sound and "music" in self.sounds: self.sounds["music"].play(loops=-1)

    @property
    def c(self): return THEMES[self.theme_name]

    def blocked(self): return self.obstacles | set(sum((s["body"] for s in self.snakes), []))

    def spawn_food(self):
        kind = random.choices(["apple", "gold", "berry"], [75, 15, 10])[0]
        return {"pos": free_cell(self.blocked()), "kind": kind, "age": 0}

    def reset(self):
        self.snakes = [new_snake((COLS//3, ROWS//2), (1,0))]
        if self.mode == "Два игрока": self.snakes.append(new_snake((COLS*2//3, ROWS//2), (-1,0), True))
        occupied = set(sum((s["body"] for s in self.snakes), [])); count = DIFFICULTIES[self.difficulty][1]
        if self.mode == "Два игрока": count //= 2
        self.obstacles = set()
        while len(self.obstacles) < count:
            pos = free_cell(occupied | self.obstacles)
            if not pos: break
            self.obstacles.add(pos)
        self.food = self.spawn_food(); self.timer = 60.0 if self.mode == "На время" else None
        self.move_timer = self.slow_timer = 0; self.paused = False; self.name_saved = False; self.particles.clear()

    def play_sound(self, name):
        if self.sound and name in self.sounds: self.sounds[name].play()

    def start(self): self.reset(); self.state = "playing"
    def score(self): return max(s["score"] for s in self.snakes)

    def finish(self):
        if self.state != "game_over": self.play_sound("lose"); self.state = "game_over"; self.name = "PLAYER"

    def save_score(self):
        if self.name_saved: return
        self.data["scores"].append({"name": self.name or "PLAYER", "score": self.score(), "mode": self.mode, "date": datetime.now().strftime("%d.%m.%Y")})
        self.data["scores"] = sorted(self.data["scores"], key=lambda x: x["score"], reverse=True)[:5]
        save_data(self.data); self.name_saved = True

    def turn(self, index, direction):
        if index >= len(self.snakes): return
        snake = self.snakes[index]
        if direction != (-snake["dir"][0], -snake["dir"][1]): snake["next"] = direction

    def adjust_menu(self, step):
        if self.menu_index == 1:
            values = list(DIFFICULTIES); self.difficulty = values[(values.index(self.difficulty)+step) % len(values)]
        elif self.menu_index == 2: self.mode = MODES[(MODES.index(self.mode)+step) % len(MODES)]

    def adjust_setting(self, step):
        if self.settings_index == 0:
            values = list(THEMES); self.theme_name = values[(values.index(self.theme_name)+step) % len(values)]; self.data["theme"] = self.theme_name
        else:
            self.sound = not self.sound; self.data["sound"] = self.sound
            if "music" in self.sounds:
                if self.sound: self.sounds["music"].play(loops=-1)
                else: self.sounds["music"].stop()
        save_data(self.data)

    def event(self, event):
        if event.type != pygame.KEYDOWN: return True
        key = event.key
        if key == pygame.K_ESCAPE:
            if self.state == "menu": return False
            self.state = "menu"; return True
        if self.state == "menu":
            options = ["Играть", "Сложность", "Режим", "Рекорды", "Настройки", "Выход"]
            if key in (pygame.K_UP, pygame.K_w): self.menu_index = (self.menu_index-1) % len(options)
            elif key in (pygame.K_DOWN, pygame.K_s): self.menu_index = (self.menu_index+1) % len(options)
            elif key in (pygame.K_LEFT, pygame.K_a): self.adjust_menu(-1)
            elif key in (pygame.K_RIGHT, pygame.K_d): self.adjust_menu(1)
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                choice = options[self.menu_index]
                if choice == "Играть": self.start()
                elif choice == "Рекорды": self.state = "scores"
                elif choice == "Настройки": self.state = "settings"
                elif choice == "Выход": return False
                else: self.adjust_menu(1)
        elif self.state == "settings":
            if key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s): self.settings_index = 1-self.settings_index
            elif key in (pygame.K_LEFT, pygame.K_a): self.adjust_setting(-1)
            elif key in (pygame.K_RIGHT, pygame.K_d, pygame.K_RETURN, pygame.K_SPACE): self.adjust_setting(1)
        elif self.state == "playing":
            directions = {pygame.K_UP:(0,-1), pygame.K_DOWN:(0,1), pygame.K_LEFT:(-1,0), pygame.K_RIGHT:(1,0), pygame.K_w:(0,-1), pygame.K_s:(0,1), pygame.K_a:(-1,0), pygame.K_d:(1,0)}
            if key == pygame.K_SPACE: self.paused = not self.paused
            elif key in directions:
                arrows = key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)
                self.turn(0 if arrows or self.mode != "Два игрока" else 1, directions[key])
        elif self.state == "game_over":
            if key == pygame.K_RETURN: self.save_score(); self.start()
            elif key == pygame.K_BACKSPACE: self.name = self.name[:-1]
            elif event.unicode.isprintable() and len(self.name) < 10:
                if self.name == "PLAYER": self.name = ""
                self.name += event.unicode.upper()
        return True

    def particles_at(self, pos, color):
        x, y = pos[0]*CELL+CELL//2, pos[1]*CELL+HUD+CELL//2
        for _ in range(12): self.particles.append([x,y,random.uniform(-90,90),random.uniform(-90,90),.45,color])

    def food_color(self):
        return self.c["grid"] if self.food["kind"] == "gold" else self.c["rock"] if self.food["kind"] == "berry" else self.c["food"]

    def update(self, dt):
        for p in self.particles: p[0] += p[2]*dt; p[1] += p[3]*dt; p[4] -= dt
        self.particles = [p for p in self.particles if p[4] > 0]
        if self.state != "playing" or self.paused: return
        if self.timer is not None:
            self.timer -= dt
            if self.timer <= 0: self.finish(); return
        self.food["age"] += dt
        if self.food["kind"] == "gold" and self.food["age"] > 6: self.food = self.spawn_food()
        self.slow_timer = max(0, self.slow_timer-dt); self.move_timer += dt*1000
        speed = max(65, DIFFICULTIES[self.difficulty][0] + (55 if self.slow_timer else 0) - self.score()*2)
        if self.move_timer >= speed: self.move_timer %= speed; self.move()

    def move(self):
        heads = []
        for snake in self.snakes:
            if not snake["alive"]: heads.append(None); continue
            snake["dir"] = snake["next"]; hx,hy = snake["body"][0]; dx,dy = snake["dir"]
            head = (hx+dx, hy+dy)
            if self.mode == "Сквозь стены": head = (head[0] % COLS, head[1] % ROWS)
            heads.append(head)
        for i, snake in enumerate(self.snakes):
            head = heads[i]
            if head is None: continue
            outside = not (0 <= head[0] < COLS and 0 <= head[1] < ROWS)
            occupied = self.obstacles | set(sum((s["body"][:-1] for s in self.snakes), []))
            if outside or head in occupied or (len(self.snakes)>1 and heads.count(head)>1): snake["alive"] = False; continue
            snake["body"].insert(0, head)
            if head == self.food["pos"]:
                snake["score"] += {"apple":1,"gold":3,"berry":1}[self.food["kind"]]
                if self.food["kind"] == "berry": self.slow_timer = 5
                self.play_sound("eat" if self.food["kind"] == "apple" else "bonus")
                self.particles_at(head, self.food_color()); self.food = self.spawn_food()
            else: snake["body"].pop()
        if not any(s["alive"] for s in self.snakes): self.finish()


def txt(screen, font, value, color, center):
    image = font.render(value, True, color); screen.blit(image, image.get_rect(center=center))


def cell(screen, color, pos, pad=2, radius=4):
    x,y=pos; pygame.draw.rect(screen,color,(x*CELL+pad,y*CELL+HUD+pad,CELL-pad*2,CELL-pad*2),border_radius=radius)


def background(screen, game):
    c=game.c; screen.fill(c["bg"]); pygame.draw.rect(screen,c["panel"],(0,0,WIDTH,HUD))
    for x in range(0,WIDTH,CELL): pygame.draw.line(screen,c["grid"],(x,HUD),(x,HEIGHT))
    for y in range(HUD,HEIGHT,CELL): pygame.draw.line(screen,c["grid"],(0,y),(WIDTH,y))


def shade(screen, fonts, game, heading, hint):
    layer=pygame.Surface((WIDTH,HEIGHT-HUD),pygame.SRCALPHA); layer.fill((*game.c["panel"],215)); screen.blit(layer,(0,HUD))
    txt(screen,fonts["large"],heading,game.c["text"],(WIDTH//2,HEIGHT//2-18)); txt(screen,fonts["body"],hint,game.c["muted"],(WIDTH//2,HEIGHT//2+28))


def draw_play(screen, fonts, game):
    background(screen,game); c=game.c
    txt(screen,fonts["title"],"PIXEL SNAKE",c["text"],(120,25)); label=game.mode+(f"  {max(0,math.ceil(game.timer))}с" if game.timer is not None else "")
    txt(screen,fonts["small"],label,c["muted"],(125,52)); scores=" | ".join(f"P{i+1}: {s['score']}" for i,s in enumerate(game.snakes))
    txt(screen,fonts["body"],scores,c["text"],(WIDTH-130,25)); txt(screen,fonts["small"],game.difficulty,c["muted"],(WIDTH-130,52))
    for pos in game.obstacles: cell(screen,c["rock"],pos,3,2)
    if game.food["pos"]: cell(screen,game.food_color(),game.food["pos"],2+int((math.sin(pygame.time.get_ticks()/140)+1)*1.5),7)
    for i,snake in enumerate(game.snakes):
        for pos in reversed(snake["body"]): cell(screen,c["rock"] if snake["second"] else c["body"],pos)
        if snake["alive"]: cell(screen,c["food"] if snake["second"] else c["head"],snake["body"][0],1)
    for x,y,_,_,life,color in game.particles: pygame.draw.circle(screen,color,(int(x),int(y)),max(1,int(5*life/.45)))
    if game.paused: shade(screen,fonts,game,"ПАУЗА","Пробел — продолжить")


def draw_menu(screen, fonts, game):
    background(screen,game); c=game.c; layer=pygame.Surface((WIDTH,HEIGHT-HUD),pygame.SRCALPHA); layer.fill((*c["bg"],238)); screen.blit(layer,(0,HUD))
    txt(screen,fonts["large"],"PIXEL SNAKE",c["panel"],(WIDTH//2,125))
    options=["Играть",f"Сложность: < {game.difficulty} >",f"Режим: < {game.mode} >","Рекорды","Настройки","Выход"]
    for i,value in enumerate(options): txt(screen,fonts["body"],("▶ " if i==game.menu_index else "  ")+value,c["panel"] if i==game.menu_index else c["rock"],(WIDTH//2,215+i*52))
    txt(screen,fonts["small"],"↑↓ выбор   ←→ изменить   Enter подтвердить",c["panel"],(WIDTH//2,HEIGHT-35))


def draw_simple(screen, fonts, game):
    background(screen,game); c=game.c
    if game.state == "settings":
        txt(screen,fonts["large"],"НАСТРОЙКИ",c["panel"],(WIDTH//2,150)); values=[f"Тема: < {game.theme_name} >",f"Звук: < {'Вкл' if game.sound else 'Выкл'} >"]
        for i,v in enumerate(values): txt(screen,fonts["body"],("▶ " if i==game.settings_index else "  ")+v,c["panel"] if i==game.settings_index else c["rock"],(WIDTH//2,260+i*65))
    else:
        txt(screen,fonts["large"],"ТАБЛИЦА РЕКОРДОВ",c["panel"],(WIDTH//2,130)); scores=game.data.get("scores",[])
        if not scores: txt(screen,fonts["body"],"Рекордов пока нет",c["rock"],(WIDTH//2,245))
        for i,item in enumerate(scores): txt(screen,fonts["small"],f"{i+1}. {item['name']:<10} {item['score']:>3}  {item['mode']}  {item['date']}",c["panel"],(WIDTH//2,210+i*55))
    txt(screen,fonts["small"],"Esc — вернуться",c["panel"],(WIDTH//2,HEIGHT-45))


def draw_over(screen, fonts, game):
    draw_play(screen,fonts,game); shade(screen,fonts,game,"ИГРА ОКОНЧЕНА",f"Счёт: {game.score()}")
    txt(screen,fonts["body"],f"Имя: {game.name}_",game.c["text"],(WIDTH//2,HEIGHT//2+72)); txt(screen,fonts["small"],"Enter — сохранить и снова   Esc — меню",game.c["muted"],(WIDTH//2,HEIGHT//2+110))


def main():
    pygame.mixer.pre_init(22050,-16,1,256); pygame.init(); screen=pygame.display.set_mode((WIDTH,HEIGHT)); pygame.display.set_caption("Pixel Snake Deluxe"); clock=pygame.time.Clock()
    fonts={"small":pygame.font.SysFont("consolas",16),"body":pygame.font.SysFont("consolas",20),"title":pygame.font.SysFont("consolas",25,bold=True),"large":pygame.font.SysFont("consolas",34,bold=True)}
    game=Game(); running=True
    while running:
        dt=clock.tick(FPS)/1000
        for event in pygame.event.get():
            if event.type==pygame.QUIT or not game.event(event): running=False
        game.update(dt)
        if game.state=="menu": draw_menu(screen,fonts,game)
        elif game.state in ("settings","scores"): draw_simple(screen,fonts,game)
        elif game.state=="game_over": draw_over(screen,fonts,game)
        else: draw_play(screen,fonts,game)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__": main()
