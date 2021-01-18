# Since we cannot modify the world.py file, we can only create functions which
# take in the world as argument and act on world's attributes

from os import close
import random
from pygame import Vector2
from Globals import SCREEN_HEIGHT, SCREEN_WIDTH
from typing import Dict, List, Tuple

from HAL import Obstacle
from GameEntity import GameEntity

# Obstacle Graphs
mountain_2_path = []

def _load_path():
    cache = {}
    def load_path(filename):
        # memoize the data returned
        nonlocal cache
        if filename in cache:
            return cache[filename]

        path = []
        with open(filename, "r") as f:
            for line in f:
                # Read and create a vector from the line
                vec = Vector2(*map(int, line.strip().split(",")))
                path.append(vec)
        cache[filename] = path
        return path

    return load_path

load_path = _load_path()


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


def dot_prod(vec1: Vector2, vec2: Vector2) -> int:
    return vec1[0]*vec2[0] + vec1[1]*vec2[1]


def proj_vec(vec1: Vector2, vec2: Vector2) -> Vector2:
    return dot_prod(vec1, vec2) * vec2.normalize()


def unit_proj_vec(vec1: Vector2, vec2: Vector2) -> Vector2:
    vec = proj_vec(vec1, vec2)
    if vec.length() == 0:
        return vec
    return vec.normalize()


def foot_of_perpendicular(pos: Vector2, line_start: Vector2, line_end: Vector2) -> Vector2:
    # Project the position onto the line
    foot_vec = proj_vec((pos - line_start), (line_end - line_start).normalize())
    return line_start + foot_vec


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


def is_mountain_2(entity: GameEntity):
    return entity.position == Vector2(620, 280)


def find_closest_node(
    path: List[Vector2],
    position: Vector2,
) -> Tuple[int, Vector2]:
    closest_vec = None
    closest_dist = None

    for vec in path:
        dist = position.distance_to(vec)

        if closest_vec is None:
            closest_vec = len(mountain_2_path) - 1
            closest_dist = dist
            continue

        if dist < closest_dist:
            closest_vec = len(mountain_2_path) - 1
            closest_dist = dist

    return (closest_vec, path[closest_vec])


def find_closest_edge(path: List[Vector2], position: Vector2) -> Dict[str, Vector2]:
    """Find the closest edge
    Returns a dictionary:
        {
            "vec": edge vector,
            "foot": foot of perpendicular location,
            "distance": distance to foot of perpendicular
        }"""
    closest_node = find_closest_node(path, position)[0]

    edge1_foot = foot_of_perpendicular(
        position,
        path[(closest_node + 1) % len(path)],
        path[closest_node],
    )
    edge1_vec = path[(closest_node + 1) % len(path)] - \
        path[closest_node]
    d_to_edge1_foot = position.distance_to(edge1_foot)

    edge2_foot = foot_of_perpendicular(
        position,
        path[closest_node-1],
        path[closest_node],
    )
    edge2_vec = path[closest_node-1] - path[closest_node]
    d_to_edge2_foot = position.distance_to(edge2_foot)

    if d_to_edge1_foot < d_to_edge2_foot:
        return {
            "vec": edge1_vec,
            "foot": edge1_foot,
            "distance": d_to_edge1_foot,
        }

    return {
        "vec": edge2_vec,
        "foot": edge2_foot,
        "distance": d_to_edge2_foot,
    }

def avoid_obstacle(
    obstacle_path: List[Vector2],
    avoider: GameEntity,
    bias: Vector2
):
    MAX_DISTANCE = 30.0

    # Decide on which edge to go towards
    closest_edge = find_closest_edge(obstacle_path, avoider.position)

    # Return the bias if it is not close to the entity
    # There is no need to avoid the obstacle if the obstacle is not near
    if closest_edge["distance"] < MAX_DISTANCE:
        return bias

    # Decide on which direction along the edge to go towards based on the bias
    # e.g. clockwise or anti-clockwise
    biased_dir = unit_proj_vec(bias, closest_edge["vec"])
    if biased_dir.length() == 0:
        return closest_edge["vec"]

    # Move towards the path based on how far the entity is from path
    # The further the entity is from the path, the more the bias is ignored
    foot_bias_ratio = (MAX_DISTANCE - closest_edge["distance"]) / MAX_DISTANCE
    vec = (avoider.position - closest_edge["foot"]).normalize() * foot_bias_ratio
    vec += biased_dir.normalize() * (1 - foot_bias_ratio)
    return vec


def avoid_obstacles(avoider: GameEntity, bias: Vector2):
    paths = [
        load_path("mountain_2_path.txt"),
    ]

    final_vec = bias
    for path in paths:
        final_vec += avoid_obstacle(path, avoider, bias)

    return final_vec


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
        final_direction = unit_proj_vec(final_direction, Vector2(0, 1))
        # Enemy is directly on the right or left
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(0, 1), Vector2(0, -1)])

    if avoider.position.y > (SCREEN_HEIGHT - 10) \
            or avoider.position.y < 10:
        final_direction = unit_proj_vec(final_direction, Vector2(0, 1))
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(1, 0), Vector2(-1, 0)])

    if final_direction.length() == 0:
        return final_direction

    return final_direction.normalize()
