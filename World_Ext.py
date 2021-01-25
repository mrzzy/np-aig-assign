# Since we cannot modify the world.py file, we can only create functions which
# take in the world as argument and act on world's attributes

from os import close
import random
from pygame import Vector2, sprite, Surface
from Globals import SCREEN_HEIGHT, SCREEN_WIDTH
from typing import Dict, List, Tuple, Callable

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
    if y1 == 0:
        return Vector2(0, 1)

    return Vector2(1, -x1 / y1).normalize()


def dot_prod(vec1: Vector2, vec2: Vector2) -> int:
    return vec1[0] * vec2[0] + vec1[1] * vec2[1]


def proj_vec(vec1: Vector2, vec2: Vector2) -> Vector2:
    return dot_prod(vec1, vec2.normalize()) * vec2.normalize()


def unit_proj_vec(vec1: Vector2, vec2: Vector2) -> Vector2:
    vec = proj_vec(vec1, vec2)
    if vec.length() == 0:
        return vec
    return vec.normalize()


def foot_of_perpendicular(
    pos: Vector2, line_start: Vector2, line_end: Vector2
) -> Vector2:
    # Project the position onto the line
    foot_vec = proj_vec((pos - line_start), (line_end - line_start))
    return line_start + foot_vec


def clamp_to_line_seg(point: Vector2, seg_start: Vector2, seg_end: Vector2):
    """Forces a `point` to be within a line segment.
    If the point is beyond the ends of the line segment, return the closest end
    If the point is not even on a line described by both points, throw an error
    Otherwise, return the point that is on the line segment.
    """
    # Test if point is on the line (ignoring bounds of line segment)
    # If the point is on the line, it must be solvable by:
    # x1 = seg_start_x + lambda * line_vec
    # y1 = seg_start_y + lambda * line_vec
    # where line_vec is a vector on the line
    line_vec = seg_end - seg_start
    if line_vec.x == 0:
        # The line segment is vertical, so the x values should match
        assert point.x == seg_start.x
        lambda_constant = (point.y - seg_start.y) / line_vec.y
    else:
        lambda_constant = (point.x - seg_start.x) / line_vec.x
        expected_y = seg_start.y + lambda_constant * line_vec.y
        # Allow for 0.01 margin for rounding errors
        assert abs(point.y - expected_y) < 0.01

    # The point is outside the line segment if lambda is not in [0, 1]
    if lambda_constant > 1:
        # Point is beyond seg_end
        return seg_end
    elif lambda_constant < 0:
        # Point is before seg_start
        return seg_start
    else:
        # Point is on the line
        return point


def foot_on_line(pos: Vector2, seg_start: Vector2, seg_end: Vector2) -> Vector2:
    """Calculates the foot of perpendicular on the line segment"""
    foot = foot_of_perpendicular(pos, seg_start, seg_end)
    return clamp_to_line_seg(foot, seg_start, seg_end)


def rotate_right(vec: Vector2) -> Vector2:
    """Rotates a vector 90 degrees to the right"""
    return Vector2(-vec[1], vec[0])


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


# Avoiding entities and obstacles
def find_closest_point(
    points: List[Vector2],
    position: Vector2,
    predicate: Callable[[Vector2], bool] = (lambda x: True),
) -> Tuple[int, Vector2]:
    """
    Find the position of closest point in the given unordered points.
    Optionally, specify a predicate that the node must satisfy.
    Returns the index of and position of the closest point.
    """
    # apply predicate to select elligible nodes
    points = list(filter(predicate, points))

    closest_vec = None
    closest_dist = None

    for index, vec in enumerate(points):
        dist = position.distance_to(vec)

        if closest_vec is None:
            closest_vec = index
            closest_dist = dist
            continue

        if dist < closest_dist:
            closest_vec = index
            closest_dist = dist

    return (closest_vec, points[closest_vec])


def find_closest_edge(path: List[Vector2], position: Vector2) -> Dict[str, Vector2]:
    """Find the closest edge
    Returns a dictionary:
        {
            "vec": edge vector,
            "foot": foot of perpendicular location,
            "distance": distance to foot of perpendicular
        }
    """
    closest_node = find_closest_point(path, position)[0]

    edge1_foot = foot_on_line(
        position,
        path[(closest_node + 1) % len(path)],
        path[closest_node],
    )
    edge1_vec = path[(closest_node + 1) % len(path)] - path[closest_node]
    d_to_edge1_foot = position.distance_to(edge1_foot)

    edge2_foot = foot_on_line(
        position,
        path[closest_node - 1],
        path[closest_node],
    )
    edge2_vec = path[closest_node] - path[closest_node - 1]
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
    bias: Vector2,
):
    IGNORE_DISTANCE = 20.0
    MAX_DISTANCE = 8.0

    # Decide on which edge to go towards
    closest_edge = find_closest_edge(obstacle_path, avoider.position)

    # Return if the avoider is not within the path
    # An avoider is within the path if the vec to foot is the opposite of the
    # clockwise rotation of the edge's vec.
    # It is assumed that the path points go clockwise:
    #                         |
    #   X -- vec_to_foot -> |foot| -- right_vec -->
    #                         |
    right_vec = rotate_right(closest_edge["vec"]).normalize()
    vec_to_foot = closest_edge["foot"] - avoider.position
    if vec_to_foot.length() == 0:
        # Ignore if the current position is on the foot
        return Vector2(0, 0)
    else:
        vec_to_foot.normalize_ip()

    if vec_to_foot == right_vec:
        return Vector2(0, 0)

    # Return the bias if it is not close to the entity
    # There is no need to avoid the obstacle if the obstacle is not near
    if closest_edge["distance"] > IGNORE_DISTANCE:
        return Vector2(0, 0)

    # Decide on which direction along the edge to go towards based on the bias
    # e.g. clockwise or anti-clockwise
    biased_dir = unit_proj_vec(bias, closest_edge["vec"])
    if biased_dir.length() == 0:
        return closest_edge["vec"]

    # Move towards the path based on how far the entity is from path
    # The further the entity is from the path, the more the bias is ignored
    foot_bias_ratio = (min(closest_edge["distance"], MAX_DISTANCE)) / MAX_DISTANCE
    vec = (closest_edge["foot"] - avoider.position).normalize() * foot_bias_ratio
    vec += biased_dir.normalize() * (1 - foot_bias_ratio)
    return vec


def avoid_obstacles(avoider: GameEntity, bias: Vector2) -> Vector2:
    # Names are solely for debugging purposes
    paths = {
        "mountain_1": load_path("mountain_1_path.txt"),
        "mountain_2": load_path("mountain_2_path.txt"),
        "plateau": load_path("plateau_path.txt"),
    }

    final_vec = Vector2(0, 0)
    for path in paths.values():
        avoid_vec = avoid_obstacle(path, avoider, bias)
        final_vec += avoid_vec

    # If there are no changes to be made to the direction, return the bias
    if final_vec.length() == 0:
        return bias

    return final_vec


def avoid_entities(avoider: GameEntity, entities: List[GameEntity]) -> Vector2:
    final_direction = Vector2(0, 0)
    for entity in entities:
        if has_constant_direction(entity):
            # Dodge perpendicular
            final_direction += perpendicular_unit(entity.velocity)
            continue

        # Dodge away
        final_direction += avoider.position - entity.position

    return final_direction


def avoid_edges(position: Vector2, bias: Vector2):
    TOLERANCE = 10
    final_direction = bias

    # Run upwards or downwards if at the edge of the screen
    if position.x > (SCREEN_WIDTH - TOLERANCE) or position.x < TOLERANCE:
        final_direction = unit_proj_vec(final_direction, Vector2(0, 1))
        # Enemy is directly on the right or left
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(0, 1), Vector2(0, -1)])

    if position.y > (SCREEN_HEIGHT - TOLERANCE) or position.y < TOLERANCE:
        final_direction = unit_proj_vec(final_direction, Vector2(1, 0))
        if final_direction.length() == 0:
            # Randomly pick to move up or down
            final_direction = random.choice([Vector2(1, 0), Vector2(-1, 0)])

    if final_direction.length() == 0:
        return final_direction

    return final_direction.normalize()


def seek(entity: GameEntity, move_pos: Vector2, offset: int = 8) -> Vector2:
    """
    Calculate heading to move towards move_pos.
    Stops moving when within offset radius to prevent bouncing around point.
    TODO: Avoids edges of the world and obstacles
    Returns heading the entity should move to or Vector2(0,0) if no movement is required.
    """
    disp = move_pos - entity.position
    if disp.length() < offset:
        # stop moving when within offset radius to prevent bouncing around move_pos
        return Vector2(0, 0)
    heading = disp.normalize()
    # apply obstacle and edge avoidance
    # heading = avoid_obstacles(entity, heading)
    # heading = avoid_edges(entity.position, heading)

    return heading * entity.maxSpeed


def collect_threats(
    entity: GameEntity, terror_radius: float
) -> Tuple[List[GameEntity], List[GameEntity]]:
    """
    Collect all immediate and non immediate threats within terror radius
    Returns a list of immediate and non immediate threats
    """
    hostile_entities = [
        e
        for e in entity.world.entities.values()
        if is_in_radius(e, entity, terror_radius) and is_hostile(e, entity)
    ]

    immediate_threats = []
    non_immediate_threats = []
    for e in hostile_entities:
        if is_immediate_threat(entity, e):
            immediate_threats.append(e)
            continue
        non_immediate_threats.append(e)
    return immediate_threats, non_immediate_threats


def detect_collisions(entity):
    """
    Detect collisions with obstacles
    Returns a list of pairs of obstacle object and the collision points.
    """
    # TODO(mrzzy): colllision filter to select what to collide against
    collisions = []
    for obstacle in entity.world.obstacles:
        collide_rel = sprite.collide_mask(entity, obstacle)
        if collide_rel is None:
            # no collision: skip
            continue

        # compute collision point offset by entity rect top left pt.
        collide_pt = Vector2(entity.rect.left, entity.rect.top) + Vector2(collide_rel)
        # record collision
        collisions.append((obstacle, collide_pt))
    return collisions


def line_of_slight(
    entity: GameEntity, target: GameEntity, step_dist=20, ray_size=(4, 4)
) -> bool:
    """
    Whether entity has line of sight on the given target
    By shooting a virtual "ray of light" toward the target and checking for collisions
    along the way at after traveling for each step_dist.
    """
    # TODO(mrzzy): line of of target filter and line of sight to positions.
    # shoot a virtual "ray" towards the target
    world = entity.world
    ray = GameEntity(entity.world, "ray", Surface(ray_size))
    # ray of light's collision mask should be filled.
    ray.mask.fill()
    ray.position = entity.position

    while (target.position - ray.position).length() > 0:
        # move step_dist step towards the target
        disp = target.position - ray.position
        heading = disp.normalize()
        ray.position = ray.position + heading * min(step_dist, disp.length())
        # call process() manually is not actually added to the game world
        ray.process(time_passed=0)

        # check for collisions along the way
        collisions = detect_collisions(ray)
        if len(collisions) > 0:
            collided, collide_pt = collisions[0]
            # check that we are not colliding with our target
            if collided.id != target.id:
                # no line of slight: ray collided
                return False
    return True


def project_position(target: GameEntity, time_secs: float) -> Vector2:
    """
    Project the position of the target in time_secs from now.
    """
    # project the velocity of the target
    projected_velocity = target.velocity
    # only project velocity if he is actively moving
    if target.velocity.length() > 0:
        move_target = None
        if getattr(target, "target", None) is not None:
            move_target = target.target
        elif getattr(target, "move_target", None) is not None:
            move_target = target.move_target

        # project velocity if it has not yet reached move target
        # distance check required to prevent normalizing 0
        if (
            move_target is not None
            and (move_target.position - target.position).length() > 0
        ):
            projected_velocity = (
                move_target.position - target.position
            ).normalize() * target.maxSpeed

    # project the targets position using velocity and the time passed in the previous frame
    projected_pos = Vector2(target.position + (projected_velocity * time_secs))
    return projected_pos
