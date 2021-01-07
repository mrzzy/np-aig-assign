import os


## Configurable Settings
DEBUG = bool(os.environ.get("DEBUG", default=False))
SHOW_PATHS = bool(os.environ.get("SHOW_PATHS", default=False))
SHOW_SPLASH = bool(os.environ.get("SHOW_SPLASH", default=False))
SPEED_MULTIPLIER = float(os.environ.get("SPEED_MULTIPLIER", default=1.0))

# sets the difficulty of red team
DIFFICULTY = str(os.environ.get("DIFFICULTY", default="easy"))
if DIFFICULTY not in ["easy", "hard"]:
    raise NotImplementedError(f"Unsupported difficulty: {DIFFICULTY}")
# Set this to 1.0 for Easy Mode
# Set this to 1.15 for Hard Mode
RED_MULTIPLIER = 1.0 if DIFFICULTY == "easy" else 1.15

# Game AI source files for game NPCs for Teams A & B
NPC_A_SRCS = os.environ.get(
    "NPC_A_SRCS", "Knight_TeamA.py,Archer_TeamA.py,Wizard_TeamA.py"
).split(",")

NPC_B_SRCS = os.environ.get(
    "NPC_B_SRCS", "Knight_TeamB.py,Archer_TeamB.py,Wizard_TeamB.py"
).split(",")
KNIGHT_A_SRC, ARCHER_A_SRC, WIZARD_A_SRC = NPC_A_SRCS
KNIGHT_B_SRC, ARCHER_B_SRC, WIZARD_B_SRC = NPC_B_SRCS

# whether to run the game in real time.
# if False, will skip the wait time between frames, running the game at faster pace
REAL_TIME = bool(os.environ.get("REAL_TIME", default=False))

# whether to run the game in headless mode
# if True:
# - configures PyGame to use a dummy video driver that does not create a window.
# - automatically disables the splash screen.
# - allows the game to exit without user interaction.
HEADLESS = bool(os.environ.get("HEADLESS", default=True))
if HEADLESS:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    SHOW_SPLASH = False

# metrics resolution: wait time in seconds between sampling metrics
# note that metrics is sampled on based on game time, not real time.
METRICS_RESOLUTION_SECS = float(os.environ.get("METRICS_RESOLUTION_SECS", default=2.0))

## Game Settings
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)

TIME_LIMIT = 180 * 1 / SPEED_MULTIPLIER

TEAM_NAME = ["TeamA", "TeamB"]

RESPAWN_TIME = 5.0 * 1 / SPEED_MULTIPLIER
HEALING_COOLDOWN = 2.0 * 1 / SPEED_MULTIPLIER
HEALING_PERCENTAGE = 20

# --- Unit initial values ---
BASE_MAX_HP = 1000
BASE_MIN_TARGET_DISTANCE = 220
BASE_PROJECTILE_RANGE = BASE_MIN_TARGET_DISTANCE
BASE_PROJECTILE_SPEED = 300 * SPEED_MULTIPLIER
BASE_RANGED_DAMAGE = 40
BASE_RANGED_COOLDOWN = 3.0 * 1 / SPEED_MULTIPLIER
BASE_SPAWN_COOLDOWN = 4.0 * 1 / SPEED_MULTIPLIER

TOWER_MAX_HP = 500
TOWER_MIN_TARGET_DISTANCE = 160
TOWER_PROJECTILE_RANGE = BASE_MIN_TARGET_DISTANCE
TOWER_PROJECTILE_SPEED = 200 * SPEED_MULTIPLIER
TOWER_RANGED_DAMAGE = 30
TOWER_RANGED_COOLDOWN = 3.0 * 1 / SPEED_MULTIPLIER

GREY_TOWER_MIN_TARGET_DISTANCE = 220
GREY_TOWER_PROJECTILE_RANGE = BASE_MIN_TARGET_DISTANCE
GREY_TOWER_PROJECTILE_SPEED = 300 * SPEED_MULTIPLIER
GREY_TOWER_RANGED_DAMAGE = 30
GREY_TOWER_RANGED_COOLDOWN = 3.0 * 1 / SPEED_MULTIPLIER

ORC_MAX_HP = 100
ORC_MAX_SPEED = 50 * SPEED_MULTIPLIER
ORC_MIN_TARGET_DISTANCE = 120
ORC_MELEE_DAMAGE = 20
ORC_MELEE_COOLDOWN = 2.0 * 1 / SPEED_MULTIPLIER

KNIGHT_MAX_HP = 400  # nerfed from 450
KNIGHT_MAX_SPEED = 80 * SPEED_MULTIPLIER
KNIGHT_MIN_TARGET_DISTANCE = 150
KNIGHT_MELEE_DAMAGE = 40
KNIGHT_MELEE_COOLDOWN = 1.5 * 1 / SPEED_MULTIPLIER

ARCHER_MAX_HP = 200
ARCHER_MAX_SPEED = 100 * SPEED_MULTIPLIER
ARCHER_MIN_TARGET_DISTANCE = 150
ARCHER_PROJECTILE_RANGE = BASE_MIN_TARGET_DISTANCE
ARCHER_PROJECTILE_SPEED = 300 * SPEED_MULTIPLIER
ARCHER_RANGED_DAMAGE = 30
ARCHER_RANGED_COOLDOWN = 1.0 * 1 / SPEED_MULTIPLIER

WIZARD_MAX_HP = 150
WIZARD_MAX_SPEED = 60 * SPEED_MULTIPLIER
WIZARD_MIN_TARGET_DISTANCE = 150
WIZARD_PROJECTILE_RANGE = BASE_MIN_TARGET_DISTANCE
WIZARD_PROJECTILE_SPEED = 200 * SPEED_MULTIPLIER
WIZARD_RANGED_DAMAGE = 50
WIZARD_RANGED_COOLDOWN = 2.0 * 1 / SPEED_MULTIPLIER  # buffed from 2.5

# --- Level up values ---
XP_TO_LEVEL = 100
UP_PERCENTAGE_HP = 10
UP_PERCENTAGE_SPEED = 10
UP_PERCENTAGE_MELEE_DAMAGE = 10
UP_PERCENTAGE_MELEE_COOLDOWN = 10
UP_PERCENTAGE_RANGED_DAMAGE = 10
UP_PERCENTAGE_RANGED_COOLDOWN = 10
UP_PERCENTAGE_PROJECTILE_RANGE = 10
UP_PERCENTAGE_HEALING = 20
UP_PERCENTAGE_HEALING_COOLDOWN = 10
