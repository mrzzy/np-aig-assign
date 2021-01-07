# Since we cannot modify the world.py file, we can only create functions which
# take in the world as argument and act on world's attributes

import random
from Globals import SCREEN_HEIGHT, SCREEN_WIDTH
from typing import List

from pygame import Vector2
from GameEntity import GameEntity

# Other Math functions
def perpendicular_unit(vec: Vector2) -> Vector2:
    # Move perpendicular to the direction of the projectile
    # When a vector is perpendicular to another vector, the dot product is
    # zero. We can pick a random value for the other vector's x (1). Solving
    # with this information we get this formula: y2 = -x1/y1
    x1, y1 = vec
    return Vector2(
        1,
        -x1/y1
    ).normalize()


def dot_prod(vec1: Vector2, vec2: Vector2) -> Vector2:
    return vec1.elementwise() * vec2


# Finding entities
def filter_entities(entities: List[GameEntity], filters):
    for e in entities:
        if any(f(e) for f in filters):
            continue
        yield e


def is_neutral_hostile(entity: GameEntity):
    if entity.team_id != 2:
        raise ValueError("Entity provided is not neutral")

    if entity.name == "tower" or entity.name == "projectile":
        return True

    return False


def is_hostile(a: GameEntity, b: GameEntity):
    """Checks if `a` entity is hostile to `b` entity."""
    if a.team_id == b.team_id:
        return False

    if a.team_id == 2:
        if is_neutral_hostile(a):
            return True
        return False

    if b.team_id == 2:
        if is_neutral_hostile(b):
            return True
        return False

    return True


def is_in_radius(a: GameEntity, b: GameEntity, radius):
    return (a.position - b.position).length() <= radius


def is_immediate_threat(to: GameEntity, threat: GameEntity):
    if not is_hostile(to, threat):
        return False

    # Melee entity threats
    if threat.name == "knight" or threat.name == "orc":
        if is_in_radius(to, threat, 40):
            return True
        return False

    # Near a tower
    if is_in_radius(to, threat, 100):
        if threat.team_id == 2 and threat.name == "tower":
            return True
        if threat.team_id != to.team_id and threat.name == "tower":
            return True

    if threat.name in ("projectile", "explosion"):
        return True

    return False


def has_constant_direction(entity: GameEntity):
    if entity.name == "projectile":
        return True

    return False


# Avoiding entities
def avoid_entities(avoider: GameEntity, entities: List[GameEntity]) -> Vector2:
    final_direction = Vector2(0, 0)
    for entity in entities:
        if has_constant_direction(entity):
            # Dodge perpendicular
            final_direction += perpendicular_unit(entity.velocity)
            continue

        # Dodge away
        final_direction += avoider.position - entity.position

    # Run upwards or downwards if at the edge of the screen
    if avoider.position.x > (SCREEN_WIDTH - 10) \
            or avoider.position.x < 10:
        final_direction = dot_prod(final_direction, Vector2(0, 1))
        # Enemy is directly on the right or left
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(0, 1), Vector2(0, -1)])

    if avoider.position.y > (SCREEN_HEIGHT - 10) \
            or avoider.position.y < 10:
        final_direction = dot_prod(final_direction, Vector2(1, 0))
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(1, 0), Vector2(-1, 0)])

    if final_direction.length() == 0:
        return final_direction

    return final_direction.normalize()
