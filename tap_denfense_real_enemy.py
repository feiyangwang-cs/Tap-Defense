# game.py
# mw2335-fw292 – Z-path tap defense with menu / pause / game-over (pygame 1.9.6)

import os, time, sys, random, math
import pygame, pigame
from pygame.locals import *
from game_state import api

try:
    import RPi.GPIO as GPIO
    ON_RPI = True
except (ImportError, RuntimeError):
    ON_RPI = False


# ---------------- Configuration ----------------
DEVICE_PITFT = True
TIMEOUT_SEC  = 0      # 0 = no auto-timeout
BAILOUT_PIN  = 27

# PiTFT display settings 
os.putenv('SDL_VIDEODRIVER', 'fbcon')
os.putenv('SDL_VIDEODRV',  'fbcon')
os.putenv('SDL_FBDEV',     '/dev/fb1')
os.putenv('SDL_MOUSEDRV',  'dummy')
os.putenv('SDL_MOUSEDEV',  '/dev/null')
os.putenv('DISPLAY',       '')

SCREEN_SIZE = (320, 240)

pygame.display.init()
pygame.font.init()
pygame.init()

# ---------------- Load BGM ----------------
try:
    pygame.mixer.init()
    pygame.mixer.music.load("./src/bgm.mp3")   
    pygame.mixer.music.set_volume(0.5)   
    pygame.mixer.music.play(-1)          
except Exception as e:
    print("Failed to load BGM:", e)

# ---------------- Load Sound Effects ----------------
try:
    click_snd_menu = pygame.mixer.Sound("./src/click_menu.ogg")
    click_snd_menu.set_volume(0.8)   # 0.0 ~ 1.0
    click_snd = pygame.mixer.Sound("./src/click.ogg")
    click_snd.set_volume(0.8)   # 0.0 ~ 1.0
except Exception as e:
    print("Failed to load click sound:", e)

pitft = pigame.PiTft() if DEVICE_PITFT else None
flags = pygame.FULLSCREEN if DEVICE_PITFT else 0
screen = pygame.display.set_mode(SCREEN_SIZE, flags)

W, H = screen.get_size()
BAR_H = max(40, H // 8)

QUIT_BTN_W = 120     
QUIT_BTN_H = 45      
MARGIN = 12          

quit_btn_rect = pygame.Rect(
    W - QUIT_BTN_W - MARGIN,   
    H - QUIT_BTN_H - MARGIN,   
    QUIT_BTN_W,
    QUIT_BTN_H
)

font = pygame.font.Font(None, 24)
big_font = pygame.font.Font(None, 32)
small_font = pygame.font.Font(None, 20)
pause_font = pygame.font.Font(None, 28)

pygame.mouse.set_visible(True)
clock = pygame.time.Clock()

if ON_RPI:
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BAILOUT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

running = True
start_time = time.time()
last_sync_time = 0.0

# ---------------- Game State Machine ----------------
STATE_MENU     = "menu"
STATE_PLAYING  = "playing"
STATE_PAUSED   = "paused"
STATE_GAME_OVER= "game_over"

game_state = STATE_MENU
game_result = None   # "win" / "lose"

# Chatbot indicator status: "listen", "think", "speak", or None
chatbot_status = None

chatbot_blink_timer = 0.0
chatbot_blink_state = True 

# Difficulty & volume for menu UI
DIFFICULTY_LEVELS = ["easy", "normal", "hard"]
difficulty_index = 1          # start at "normal"
volume = 50                   # 0-100, UI only for now

# Menu buttons
menu_start_rect   = pygame.Rect(W//2 - 60, H//2 - 80, 120, 40)
menu_diff_rect    = pygame.Rect(20, H//2 - 30, 140, 40)
menu_vol_minus    = pygame.Rect(10, H//2 + 30, 35, 35)
menu_vol_plus     = pygame.Rect(110, H//2 + 30, 35, 35)
menu_howto_rect   = pygame.Rect(W//2 + 20, H//2 -10, 140, 40)

show_quit_btn = True
show_howto = False   


# Pause button during game
pause_btn_rect    = pygame.Rect(W//2 - 30, 5, 60, 24)

# Pause overlay buttons
pause_resume_rect = pygame.Rect(W//2 - 50, H//2 - 35, 120, 50)
pause_menu_rect   = pygame.Rect(W//2 - 60, H//2 + 30, 140, 50)

# Game-over buttons
go_restart_rect   = pygame.Rect(W//2 - 60, H//2-15,      120, 35)
go_menu_rect      = pygame.Rect(W//2 - 60, H//2 + 30, 120, 35)
go_exit_rect      = pygame.Rect(W//2 - 60, H//2 + 80, 120, 35)

# ---------------- Enemy & Path Configuration ----------------
ENEMY_W, ENEMY_H = 40, 24
INIT_HP          = 5
ENEMY_SPEED      = 30.0
SPAWN_INTERVAL   = 2.0
MAX_ENEMIES      = 7
ENEMY_SPAWNED    = 0

# Player HP
PLAYER_HP        = 3

# Z-shaped path
PATH_POINTS = [

]
PATH_SETS = {}

def build_paths():
    """Build two candidate paths for each difficulty level."""
    global PATH_SETS

    mid_y  = H // 2
    top_y  = 50
    bot_y  = H - 80

    PATH_SETS = {
    # EASY
    "easy": [
        [
            (-ENEMY_W, mid_y),
            (W + ENEMY_W, mid_y),
        ],
        [
            (-ENEMY_W, top_y),
            (W // 2, bot_y),
            (W + ENEMY_W, bot_y - 10),
        ],
    ],

    # NORMAL
    "normal": [
        [
            (-ENEMY_W, 80),
            (W - 40, 80),
            (40, 170),
            (W + ENEMY_W, 170),
        ],
        [
            (-ENEMY_W,110),
            (W // 4, 70),
            (W // 2, 150),
            (3 * W // 4, 90),
            (W + ENEMY_W, 170),
        ],
    ],

    # HARD
    "hard": [
    
        [
        (-ENEMY_W, 60),
        (W // 6, 60),      
        (W // 3, 200),     
        (W // 2, 80),      
        (2 * W // 3, 210), 
        (5 * W // 6, 90),  
        (W + ENEMY_W, 170) 
        ],
    
        [
        (-ENEMY_W, 50),
        (W // 5, 210),     
        (2 * W // 5, 70),  
        (3 * W // 5, 200), 
        (4 * W // 5, 80),  
        (W + ENEMY_W, 160) 
        ],
    ],
}


    

def choose_path_for_current_difficulty():
    """Randomly choose one of the two paths for the current difficulty."""
    global PATH_POINTS
    diff = DIFFICULTY_LEVELS[difficulty_index]
    PATH_POINTS = random.choice(PATH_SETS[diff])

enemies = []
last_spawn_time = start_time
build_paths()
choose_path_for_current_difficulty()

# Difficulty affects enemy speed / HP / count
def apply_difficulty():
    global ENEMY_SPEED, INIT_HP, MAX_ENEMIES, PATH_POINTS,PLAYER_HP
    diff = DIFFICULTY_LEVELS[difficulty_index]
    if diff == "easy":
        ENEMY_SPEED = 25.0
        INIT_HP     = 3
        MAX_ENEMIES = 5
        PLAYER_HP   = 7

    elif diff == "normal":
        ENEMY_SPEED = 30.0
        INIT_HP     = 6
        MAX_ENEMIES = 8
        PLAYER_HP   = 5

    else:  # hard
        ENEMY_SPEED = 60.0
        INIT_HP     = 9
        MAX_ENEMIES = 12
        PLAYER_HP   = 3
  

def reset_round():
    """Reset all per-round variables and start playing."""
    global enemies, ENEMY_SPAWNED, PLAYER_HP
    global last_spawn_time, game_state, game_result

    apply_difficulty()
    choose_path_for_current_difficulty()
    enemies = []
    ENEMY_SPAWNED = 0
    
    last_spawn_time = time.time()
    game_result = None
    game_state = STATE_PLAYING
    hide_quit_bar()

def spawn_enemy():
    global ENEMY_SPAWNED
    sx, sy = PATH_POINTS[0]
    rect = pygame.Rect(int(sx), int(sy) - ENEMY_H//2, ENEMY_W, ENEMY_H)
    enemy = {
        "rect": rect,
        "hp": INIT_HP,
        "x": float(sx),
        "y": float(sy),
        "speed": ENEMY_SPEED,
        "seg_idx": 0
    }
    enemies.append(enemy)
    ENEMY_SPAWNED += 1

def advance_along_path(enemy, dt):
    """Move an enemy along the Z-shaped polyline path."""
    while dt > 0 and enemy["seg_idx"] < len(PATH_POINTS) - 1:
        sx, sy = enemy["x"], enemy["y"]
        tx, ty = PATH_POINTS[enemy["seg_idx"] + 1]

        dx = tx - sx
        dy = ty - sy
        dist = (dx*dx + dy*dy) ** 0.5

        if dist == 0:
            enemy["seg_idx"] += 1
            continue

        max_move = enemy["speed"] * dt

        if max_move >= dist:
            enemy["x"], enemy["y"] = float(tx), float(ty)
            enemy["seg_idx"] += 1
            dt -= dist / enemy["speed"]
        else:
            ratio = max_move / dist
            enemy["x"] = sx + dx * ratio
            enemy["y"] = sy + dy * ratio
            dt = 0

    enemy["rect"].x = int(enemy["x"])
    enemy["rect"].y = int(enemy["y"] - ENEMY_H // 2)

def update_enemies(dt):
    """Update movement, remove dead/out-of-bound enemies, subtract player HP."""
    global enemies, PLAYER_HP

    alive = []
    for e in enemies:
        advance_along_path(e, dt)

        escaped = (
            e["seg_idx"] >= len(PATH_POINTS) - 1 and
            e["x"] >= PATH_POINTS[-1][0]
        )

        if escaped:
            PLAYER_HP -= 1
            continue

        if e["hp"] > 0:
            alive.append(e)

    enemies = alive

def maybe_spawn_enemy(now):
    global last_spawn_time
    if ENEMY_SPAWNED >= MAX_ENEMIES:
        return
    if now - last_spawn_time >= SPAWN_INTERVAL:
        spawn_enemy()
        last_spawn_time = now


# ---------------- Load Tiled Pixel Background ----------------
BG_SURF = None
try:
    bg_tile = pygame.image.load("./src/sbg_tile.png").convert()   
    tile_w, tile_h = bg_tile.get_size()
    BG_SURF = pygame.Surface((W, H))
    for y in range(0, H, tile_h):
        for x in range(0, W, tile_w):
            BG_SURF.blit(bg_tile, (x, y))
except Exception as e:
    print("Failed to load bg_tile.png:", e)
    BG_SURF = None

# ---------------- Load Tiled Pixel Background for menu ----------------
MENU_BG_SURF = None
try:
    menu_bg_tile = pygame.image.load("./src/menu_bg_tile.png").convert()   
    tile_w, tile_h = menu_bg_tile.get_size()
    MENU_BG_SURF = pygame.Surface((W, H))
    for y in range(0, H, tile_h):
        for x in range(0, W, tile_w):
            MENU_BG_SURF.blit(menu_bg_tile, (x, y))
except Exception as e:
    print("Failed to load menu_bg_tile.png:", e)
    MENU_BG_SURF = None

# ---------------- Load Path Tile ----------------
PATH_TILE = None
try:
    PATH_TILE = pygame.image.load("./src/path_tile.png").convert_alpha()
    PATH_TILE = pygame.transform.scale(PATH_TILE, (24, 24))
except Exception as e:
    print("Failed to load path_tile.png:", e)
    PATH_TILE = None


# ---------------- Chatbot Icons ----------------
try:
    ICON_LISTEN = pygame.image.load("./src/icon_listen.png").convert_alpha()
    ICON_LISTEN = pygame.transform.scale(ICON_LISTEN, (22, 22))

    ICON_THINK = pygame.image.load("./src/icon_think.png").convert_alpha()
    ICON_THINK = pygame.transform.scale(ICON_THINK, (22, 22))

    ICON_SPEAK = pygame.image.load("./src/icon_speak.png").convert_alpha()
    ICON_SPEAK = pygame.transform.scale(ICON_SPEAK, (22, 22))
except Exception as e:
    print("Failed loading chatbot icons:", e)
    ICON_LISTEN = ICON_THINK = ICON_SPEAK = None


# ---------------- Load Heart Icon ----------------
try:
    HEART_IMG = pygame.image.load("./src/heart.png").convert_alpha()
    HEART_IMG = pygame.transform.scale(HEART_IMG, (24, 24))
except:
    HEART_IMG = None

# ---------------- Load Enemy Sprites for Each Difficulty ----------------
ENEMY_SPRITES = {
    "easy":  None,
    "normal": None,
    "hard": None
}

def load_enemy_sprites():
    files = {
        "easy":   "./src/enemy_easy.png",
        "normal": "./src/enemy_normal.png",
        "hard":   "./src/enemy_hard.png"
    }

    for diff, filename in files.items():
        try:
            img = pygame.image.load(filename).convert_alpha()
            img = pygame.transform.scale(img, (ENEMY_W, ENEMY_H))
            ENEMY_SPRITES[diff] = img
        except:
            print("Failed to load:", filename)
            ENEMY_SPRITES[diff] = None

load_enemy_sprites()


# ---------------- Drawing helpers ----------------
def draw_path():
    pts = [(float(x), float(y)) for (x, y) in PATH_POINTS]
    if len(pts) < 2:
        return

    # no path tile pic
    if PATH_TILE is None:
        int_pts = [(int(x), int(y)) for (x, y) in pts]
        pygame.draw.lines(screen, (100, 100, 100), False, int_pts, 2)
        return

    tile_w, tile_h = PATH_TILE.get_size()

    
    for i in range(len(pts) - 1):
        sx, sy = pts[i]
        tx, ty = pts[i + 1]
        dx = tx - sx
        dy = ty - sy
        dist = math.hypot(dx, dy)
        if dist == 0:
            continue

        
        steps = int(dist / tile_w) + 1
        angle = math.degrees(math.atan2(dy, dx))  # change the directio of the pic
        tile_rot = pygame.transform.rotate(PATH_TILE, -angle)

        for step in range(steps + 1):
            t = step / float(steps)
            x = sx + dx * t
            y = sy + dy * t
            rect = tile_rot.get_rect(center=(int(x), int(y)))
            screen.blit(tile_rot, rect)


def hide_quit_bar():
    global show_quit_btn
    show_quit_btn = False

def show_quit_bar():
    global show_quit_btn
    show_quit_btn = True

def draw_quit_bar():

    if not show_quit_btn:
        return 

    pygame.draw.rect(screen, (255, 0, 0), quit_btn_rect)
    label = font.render("EXIT", True, (255, 255, 255))
    screen.blit(label, label.get_rect(center=quit_btn_rect.center))

def draw_chatbot_indicator(dt):
    global chatbot_blink_timer, chatbot_blink_state

    if chatbot_status is None:
        return

    x = 10
    y = H - 25   

    if chatbot_status == "listen":
        icon = ICON_LISTEN

    elif chatbot_status == "think":
    # rotate spinner icon
        spinner_angle = (pygame.time.get_ticks() / 5) % 360
        icon = pygame.transform.rotate(ICON_THINK, -spinner_angle)

    elif chatbot_status == "speak":
        icon = ICON_SPEAK

    else:
        return

    if icon is None:
        return

    #blink
    chatbot_blink_timer += dt
    if chatbot_blink_timer >= 0.5:
        chatbot_blink_timer = 0
        chatbot_blink_state = not chatbot_blink_state

    # if not chatbot_blink_state:
    #     icon = pygame.transform.rotozoom(icon, 0, 0.7) 
    
    screen.blit(icon, (x, y))



def draw_enemy_and_ui():
    # Enemies and path
    draw_path()
    for e in enemies:
        hp = e["hp"]
        rect = e["rect"]
        ratio = max(0.0, min(1.0, float(hp) / INIT_HP))
        color = (255, int(120 * ratio), int(80 * ratio))

        
        current_diff = DIFFICULTY_LEVELS[difficulty_index]
        enemy_img = ENEMY_SPRITES[current_diff]

        if enemy_img:
            img_rect = enemy_img.get_rect(center=rect.center)
            screen.blit(enemy_img, img_rect)
        else:
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (220,220,220), rect, 1)


        hp_txt = small_font.render(str(hp), True, (255, 255, 255))
        hp_rect = hp_txt.get_rect(center=(rect.centerx, rect.top - 8))
        screen.blit(hp_txt, hp_rect)
    # Remaining enemies
    remaining = max(0, MAX_ENEMIES - ENEMY_SPAWNED)
    rem_txt = small_font.render("Enemies left: %d" % remaining,
                                True, (255, 255, 0))
    screen.blit(rem_txt, (5, 5))

    # Player HP (right top)
    if HEART_IMG:
        heart_x = W - HEART_IMG.get_width() - 40
        heart_y = 5
        screen.blit(HEART_IMG, (heart_x, heart_y))
        hp_txt = small_font.render(str(PLAYER_HP), True, (255, 80, 80))
        screen.blit(hp_txt,
                    (heart_x + HEART_IMG.get_width() + 5, heart_y + 2))

    # Pause button
    pygame.draw.rect(screen, (80, 80, 80), pause_btn_rect)
    # draw "||"
    x0, y0, w0, h0 = pause_btn_rect
    pygame.draw.rect(screen, (220, 220, 220),
                     (x0 + 10, y0 + 4, 8, h0 - 8))
    pygame.draw.rect(screen, (220, 220, 220),
                     (x0 + w0 - 18, y0 + 4, 8, h0 - 8))

def draw_menu():
    if MENU_BG_SURF:
        screen.blit(MENU_BG_SURF, (0, 0))
    else:
        screen.fill((0,0,0))

    title = big_font.render("Tap Defense", True, (200, 200, 255))
    screen.blit(title, title.get_rect(center=(W//2, 20)))

    diff = DIFFICULTY_LEVELS[difficulty_index]
    diff_label = font.render("Difficulty: %s" % diff, True, (255,255,255))
    pygame.draw.rect(screen, (255, 165, 0), menu_diff_rect)
    screen.blit(diff_label,
                diff_label.get_rect(center=menu_diff_rect.center))

    vol_label = font.render("Vol: %d" % volume, True, (255,255,255))
    screen.blit(vol_label, (50, H//2 + 35))

    # volume buttons
    pygame.draw.rect(screen, (90,90,90), menu_vol_minus)
    pygame.draw.rect(screen, (90,90,90), menu_vol_plus)
    minus_txt = font.render("-", True, (255,255,255))
    plus_txt  = font.render("+", True, (255,255,255))
    screen.blit(minus_txt, minus_txt.get_rect(center=menu_vol_minus.center))
    screen.blit(plus_txt,  plus_txt.get_rect(center=menu_vol_plus.center))

    # Start button
    pygame.draw.rect(screen, (0,150,80), menu_start_rect)
    start_txt = font.render("START", True, (0,0,0))
    screen.blit(start_txt, start_txt.get_rect(center=menu_start_rect.center))

    # How to play
    pygame.draw.rect(screen, (50,50,120), menu_howto_rect)
    h_text = small_font.render("How to play", True, (255,255,255))
    screen.blit(h_text, h_text.get_rect(center=menu_howto_rect.center))

    if show_howto:
        draw_how_to_overlay()
    else:
        draw_quit_bar()
    
    draw_chatbot_indicator(dt)

    pygame.display.flip()

def draw_how_to_overlay():
    # simple text overlay on menu
    overlay = pygame.Surface((W-40, H-60))
    overlay.set_alpha(220)
    overlay.fill((0,0,0))
    rect = overlay.get_rect(center=(W//2, H//2))
    screen.blit(overlay, rect)
    hide_quit_bar()

    lines = [
        "Tap enemies to deal damage.",
        "If an enemy escapes,",
        "you lose 1 HP.",
        "Lose all HP = Game Over.",
        "Pause with the button on top.",
        "Tap anywhere to close."
        
    ]
    y = rect.top + 20
    for line in lines:
        t = small_font.render(line, True, (255,255,255))
        screen.blit(t, (rect.left + 20, y))
        y += 22
    

def draw_playing():
    if BG_SURF:
        screen.blit(BG_SURF, (0, 0))
    else:
        screen.fill((0,0,0))

    draw_enemy_and_ui()
    draw_quit_bar()
    draw_chatbot_indicator(dt)
    pygame.display.flip()

def draw_paused():
    screen.fill((0,0,0))
    draw_enemy_and_ui()

    # overlay
    overlay = pygame.Surface((W//1.5, H//1.3))
    overlay.set_alpha(220)
    overlay.fill((0, 0, 0))
    rect = overlay.get_rect(center=(W//2, H//2+20))
    screen.blit(overlay, rect)

    txt = big_font.render("Paused", True, (255,255,255))
    screen.blit(txt, txt.get_rect(center=(W//2, rect.top+5)))

    pygame.draw.rect(screen, (0,150,80), pause_resume_rect)
    r_txt = font.render("Resume", True, (0,0,0))
    screen.blit(r_txt, r_txt.get_rect(center=pause_resume_rect.center))

    pygame.draw.rect(screen, (150,80,0), pause_menu_rect)
    m_txt = small_font.render("Back to Menu", True, (0,0,0))
    screen.blit(m_txt, m_txt.get_rect(center=pause_menu_rect.center))

    draw_quit_bar()
    draw_chatbot_indicator(dt)
    pygame.display.flip()

def draw_game_over():
    screen.fill((0,0,0))
    msg = "You Win!" if game_result == "win" else "Game Over"
    color = (0,255,0) if game_result == "win" else (255,50,50)
    t = big_font.render(msg, True, color)
    screen.blit(t, t.get_rect(center=(W//2, 70)))

    pygame.draw.rect(screen, (0,150,80), go_restart_rect)
    rt = font.render("Restart", True, (0,0,0))
    screen.blit(rt, rt.get_rect(center=go_restart_rect.center))

    pygame.draw.rect(screen, (70,70,140), go_menu_rect)
    mt = small_font.render("Change difficulty", True, (255,255,255))
    screen.blit(mt, mt.get_rect(center=go_menu_rect.center))

    pygame.draw.rect(screen, (120,50,50), go_exit_rect)
    et = font.render("Exit", True, (0,0,0))
    screen.blit(et, et.get_rect(center=go_exit_rect.center))

    draw_quit_bar()
    draw_chatbot_indicator(dt)
    pygame.display.flip()

# ---------------- Input handlers ----------------
def handle_menu_click(pos):
    global difficulty_index, volume, running, show_howto
    click_snd_menu.play()

    if show_howto:
        show_howto = False
        show_quit_bar()
        return
    if show_quit_btn and quit_btn_rect.collidepoint(pos):
        running = False
        return

    if menu_start_rect.collidepoint(pos):
        reset_round()
        return

    if menu_diff_rect.collidepoint(pos):
        difficulty_index = (difficulty_index + 1) % len(DIFFICULTY_LEVELS)
        ###
        api.set_difficulty(DIFFICULTY_LEVELS[difficulty_index])
        return

    if menu_vol_minus.collidepoint(pos):
        volume = max(0, volume - 10)
        pygame.mixer.music.set_volume(volume / 100.0)
        click_snd_menu.set_volume(volume / 100.0) 
        click_snd.set_volume(volume / 100.0) 
        ###
        api.set_volume(volume)
        return

    if menu_vol_plus.collidepoint(pos):
        volume = min(100, volume + 10)
        pygame.mixer.music.set_volume(volume / 100.0)
        click_snd_menu.set_volume(volume / 100.0) 
        click_snd.set_volume(volume / 100.0)
        ###
        api.set_volume(volume)
        return

    if menu_howto_rect.collidepoint(pos):
        show_howto = True
        hide_quit_bar()
        return

def handle_playing_click(pos):
    global game_state, running

    click_snd.play()

    if pause_btn_rect.collidepoint(pos):
        game_state = STATE_PAUSED
        return

    # hit enemies
    for e in enemies:
        if e["rect"].collidepoint(pos):
            e["hp"] -= 1
            break

def handle_paused_click(pos):
    global game_state, running
    click_snd_menu.play()

    if pause_resume_rect.collidepoint(pos):
        game_state = STATE_PLAYING
        hide_quit_bar()
        return

    if pause_menu_rect.collidepoint(pos):
        game_state = STATE_MENU
        show_quit_bar()
        return

def handle_game_over_click(pos):
    global running, game_state
    click_snd_menu.play()
    if quit_btn_rect.collidepoint(pos):
        running = False
        return

    if go_restart_rect.collidepoint(pos):
        reset_round()
        return

    if go_menu_rect.collidepoint(pos):
        game_state = STATE_MENU
        return

    if go_exit_rect.collidepoint(pos):
        running = False
        return

def check_gpio_bailout():
    global running
    if ON_RPI and not GPIO.input(BAILOUT_PIN):
        running = False

# chatbot funcs
def sync_to_chat_state():
    """Write current status to GameState for chatbot to read."""
    api.update_state({
        "stage": game_state,
        "remaining_enemies": max(0, MAX_ENEMIES - ENEMY_SPAWNED),
        "player_hp": PLAYER_HP,
    })

def api_phraser():
    """Clear one-shot command flags after they've been consumed."""
    api.update_state({
        "want_start": False,
        "want_pause": False,
        "want_resume": False,
        "want_restart": False,
        "want_exit": False,
    })

def apply_chat_commands():
    """Apply one-shot voice commands from GameState."""
    global running, game_state, volume, difficulty_index, chatbot_status

    s = api.get_state()
    if not s:
        return
        
    if s.get("chat_status") != None:
        chatbot_status = s.get("chat_status")
    new_volume = s.get("volume", volume)
    if isinstance(new_volume, int) and 0 <= new_volume <= 100 and new_volume != volume:
        volume = new_volume
        pygame.mixer.music.set_volume(volume / 100.0)
        click_snd_menu.set_volume(volume / 100.0)
        click_snd.set_volume(volume / 100.0)

    new_diff = s.get("difficulty", DIFFICULTY_LEVELS[difficulty_index])
    if new_diff in DIFFICULTY_LEVELS and new_diff != DIFFICULTY_LEVELS[difficulty_index]:
        difficulty_index = DIFFICULTY_LEVELS.index(new_diff)

    want_start   = s.get("want_start", False)
    want_pause   = s.get("want_pause", False)
    want_resume  = s.get("want_resume", False)
    want_restart = s.get("want_restart", False)
    want_exit    = s.get("want_exit", False)

    consumed = False

    # start game from menu
    if game_state == STATE_MENU and want_start:
        reset_round()
        consumed = True

    # pause / resume while playing / paused
    elif game_state == STATE_PLAYING and want_pause:
        game_state = STATE_PAUSED
        consumed = True

    elif game_state == STATE_PAUSED and want_resume:
        game_state = STATE_PLAYING
        consumed = True

    # restart after game over
    elif game_state == STATE_GAME_OVER and want_restart:
        reset_round()
        consumed = True


    elif want_exit:
        running = False
        consumed = True

    if consumed:
        api_phraser()



# ---------------- Main Loop ----------------
try:
    while running:
        dt = clock.tick(30) / 1000.0
        now = time.time()

        if pitft is not None:
            pitft.update()

        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == MOUSEBUTTONUP:
                pos = pygame.mouse.get_pos()
                if game_state == STATE_MENU:
                    handle_menu_click(pos)
                elif game_state == STATE_PLAYING:
                    handle_playing_click(pos)
                elif game_state == STATE_PAUSED:
                    handle_paused_click(pos)
                elif game_state == STATE_GAME_OVER:
                    handle_game_over_click(pos)

        check_gpio_bailout()

        # apply voice command first
        apply_chat_commands()

        # Only update gameplay when actually playing
        if game_state == STATE_PLAYING:
            maybe_spawn_enemy(now)
            update_enemies(dt)

            # Check win / lose
            if PLAYER_HP <= 0:
                game_state = STATE_GAME_OVER
                game_result = "lose"
            elif ENEMY_SPAWNED >= MAX_ENEMIES and len(enemies) == 0:
                game_state = STATE_GAME_OVER
                game_result = "win"

        # sync states to chatbot
        if now - last_sync_time >= 0.5:
            sync_to_chat_state()
            last_sync_time = now

        # Draw by state
        if game_state == STATE_MENU:
            draw_menu()
        elif game_state == STATE_PLAYING:
            draw_playing()
        elif game_state == STATE_PAUSED:
            draw_paused()
        elif game_state == STATE_GAME_OVER:
            draw_game_over()

finally:
    pygame.quit()
    if ON_RPI:
        GPIO.cleanup()
    if pitft is not None:
        del pitft
