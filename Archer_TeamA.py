import pygame
from pygame import Vector2, Surface
from random import randint, random, choices as random_choices
from Graph import *

from Character import *
from State import *


def get_away_node(graph, current_pos, opponent_pos):
    """
    Get the nearest node moving away from the opponent
    """
    nearest = None
    nearest_distance = None
    for node in graph.nodes.values():
        distance = (current_pos - Vector2(node.position)).length()
        # make sure we dont move towards the the opponent
        if distance < (current_pos - opponent_pos).length():
            continue
        if nearest is None or distance < nearest_distance:
            nearest = node
            nearest_distance = distance
    return nearest


def vec_project(vec: Vector2, target_vec: Vector2):
    """
    Computes the vector projection of vec on target_vec
    """
    # vec . target_vec
    # ---------------- * vec
    # ||vec||^2
    return (vec.dot(target_vec) / (target_vec.magnitude() ** 2)) * target_vec


def detect_collisions(entity):
    """
    Detect collisions with obstacles
    Returns a list of pairs of obstacle object and the collision points.
    """
    collisions = []
    for obstacle in entity.world.obstacles:
        collide_rel = pygame.sprite.collide_mask(entity, obstacle)
        if collide_rel is None:
            # no collision: skip
            continue

        # compute collision point offset by entity rect top left pt.
        collide_pt = Vector2(entity.rect.left, entity.rect.top) + Vector2(collide_rel)
        # record collision
        collisions.append((obstacle, collide_pt))
    return collisions


def seek(entity, move_pos, offset=4):
    """
    Move towards move_pos at max speed
    Stops moving when within offset radius to prevent bouncing around point
    Returns True if it reaches move_pos (with offset) else False.
    """
    disp = move_pos - entity.position
    if disp.length() < offset:
        return True
    entity.velocity = entity.maxSpeed * disp.normalize()
    return False


def avoid_obstacle(entity, collisions, correct_dist=20):
    """
    When colliding with the obstacle, direct entity to move in the opposite direction
    of the collision for correct_dist to avoid the obstacle.
    Returns position the entity should move to exit collision.
    """
    collided, collide_pt = collisions[0]
    normal = entity.position - collide_pt
    # move in the direction of the normal to avoid the obstacle
    normal_heading = normal.normalize()
    # TODO(mrzzy): explore random perpendicular offset to heading to prevent
    # colliding back immediately
    move_target = collide_pt + (normal_heading * correct_dist)

    return move_target


def line_of_slight(entity, target, step_dist=20, ray_size=(4, 4)):
    """
    Whether entity has line of sight on the given target
    By shooting a virtual "ray of light" toward the target and checking for collisions
    along the way at after traveling for each step_dist.
    """
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


def get_attackers(entity):
    """
    Check if the given entity is being targeted and attacked.
    Returns a list of attackers or a empty list if no one is attacking sorted
         by distance to the given entity
    """
    world = entity.world
    attackers = [
        e
        for e in world.entities.values()
        if getattr(e, "target", None) is not None and e.target.id == entity.id
    ]
    return sorted(
        attackers, key=(lambda attacker: (attacker.position - entity.position).length())
    )


class Archer_TeamA(Character):
    def __init__(self, world, image, projectile_image, base, position):

        Character.__init__(self, world, "archer", image)

        self.projectile_image = projectile_image

        self.base = base
        self.position = position
        self.move_target = GameEntity(world, "archer_move_target", None)
        self.target = None

        self.maxSpeed = 50
        self.min_target_distance = 100
        self.projectile_range = 100
        self.projectile_speed = 100

        seeking_state = ArcherStateSeeking_TeamA(self)
        combat_state = ArcherStateCombat_TeamA(self)
        ko_state = ArcherStateKO_TeamA(self)

        self.brain.add_state(seeking_state)
        self.brain.add_state(combat_state)
        self.brain.add_state(ko_state)

        self.brain.set_state("seeking")

        self.time_passed = 1 / 30

    def render(self, surface):
        Character.render(self, surface)

    def process(self, time_passed):
        # record time passed for states to use.
        self.time_passed = time_passed

        Character.process(self, time_passed)

        level_up_stats_weighted = [
            ("ranged cooldown", 0.7),
            ("healing cooldown", 0.3),
        ]
        if self.can_level_up():
            upgrade_stat = random_choices(
                population=[s[0] for s in level_up_stats_weighted],
                weights=[s[1] for s in level_up_stats_weighted],
                k=1,
            )[0]
            self.level_up(upgrade_stat)


class ArcherStateSeeking_TeamA(State):
    # TODO (mrzzy): Push together with knight/use as damage sponge
    def __init__(self, archer):

        State.__init__(self, "seeking")
        self.archer = archer

        self.archer.path_graph = self.archer.world.paths[
            randint(0, len(self.archer.world.paths) - 1)
        ]

    def do_actions(self):
        self.archer.velocity = self.archer.move_target.position - self.archer.position
        if self.archer.velocity.length() > 0:
            self.archer.velocity.normalize_ip()
            self.archer.velocity *= self.archer.maxSpeed

        # patch up health while seeking
        if self.archer.current_hp < self.archer.max_hp:
            self.archer.heal()

    def check_conditions(self):
        # check if being attacked
        attackers = get_attackers(self.archer)
        if len(attackers) > 0:
            # fight back against nearest attacker
            opponent = attackers[0]
        else:
            # fight nearest opponent
            opponent = self.archer.world.get_nearest_opponent(self.archer)

        # check if opponent is in range
        if opponent is not None:
            opponent_distance = (self.archer.position - opponent.position).length()
            if opponent_distance <= self.archer.min_target_distance:
                self.archer.target = opponent
                return "combat"

        if (self.archer.position - self.archer.move_target.position).length() < 8:

            # continue on path
            if self.current_connection < self.path_length:
                self.archer.move_target.position = self.path[
                    self.current_connection
                ].toNode.position
                self.current_connection += 1

        return None

    def entry_actions(self):

        nearest_node = self.archer.path_graph.get_nearest_node(self.archer.position)

        self.path = pathFindAStar(
            self.archer.path_graph,
            nearest_node,
            self.archer.path_graph.nodes[self.archer.base.target_node_index],
        )

        self.path_length = len(self.path)

        if self.path_length > 0:
            self.current_connection = 0
            self.archer.move_target.position = self.path[0].fromNode.position

        else:
            self.archer.move_target.position = self.archer.path_graph.nodes[
                self.archer.base.target_node_index
            ].position


class ArcherStateCombat_TeamA(State):
    """
    Combat State
    """

    def __init__(self, archer):

        State.__init__(self, "combat")
        self.archer = archer
        self.correct_pos = None

    def do_actions(self):
        # check if being attacked
        attackers = get_attackers(self.archer)
        if len(attackers) > 0:
            # fight back against nearest attacker instead
            self.archer.target = attackers[0]

        target, current_pos, time_passed = (
            self.archer.target,
            self.archer.position,
            self.archer.time_passed,
        )
        # project the targets velocity by trying to infer where he is trying to move to.
        projected_velocity = target.velocity
        # only project velocity if he is actively moving
        if target.velocity.length() > 0:
            if getattr(target, "target", None) is not None:
                projected_velocity = (
                    target.target.position - target.position
                ).normalize() * target.maxSpeed
            elif getattr(target, "move_target", None) is not None:
                projected_velocity = (
                    target.move_target.position - target.position
                ).normalize() * target.maxSpeed

        # project the targets position using velocity and the time passed in the previous frame
        projected_pos = Vector2(target.position + (projected_velocity * time_passed))
        target_distance = (projected_pos - self.archer.position).length()

        # attack: attack target when within range
        if (
            target_distance <= self.archer.projectile_range
            and self.archer.current_ranged_cooldown <= 0
        ):
            # take in account arrow travel time when attacking
            projected_travel_time = target_distance / self.archer.projectile_speed
            attack_pos = Vector2(
                projected_pos + (projected_velocity * projected_travel_time)
            )
            self.archer.projected_pos = attack_pos
            # TODO: remove
            self.archer.ranged_attack(attack_pos)

        # movement: correct movement when colliding to prevent getting stuck on walls
        collisions = detect_collisions(self.archer)
        if len(collisions) > 0:
            self.correct_pos = avoid_obstacle(self.archer, collisions, 70)
            self.archer.correct_pos = self.correct_pos

        if self.correct_pos is not None:
            reached = seek(self.archer, self.correct_pos)
            if reached:
                self.correct_pos = None
        combat_range = self.archer.projectile_range
        if target_distance == combat_range:
            # target within range: stop to attack
            self.archer.velocity = Vector2(0, 0)
        elif target_distance > combat_range:
            # seek target if out of range
            seek(self.archer, projected_pos)
        elif target_distance < combat_range:
            # move to attack at safe distance
            # move towards nearest node that is also moving away from opponent
            away_node = get_away_node(
                self.archer.path_graph, current_pos, projected_pos
            )
            move_heading = (away_node.position - current_pos).normalize()
            move_magnitude = target_distance - self.archer.projectile_range
            move_target = move_heading * move_magnitude
            seek(self.archer, move_target)

    def check_conditions(self):
        # target is gone/lost line of sight
        if (
            self.archer.world.get(self.archer.target.id) is None
            or self.archer.target.ko
            # KO takes 1 frame to register
            or self.archer.target.current_hp <= 0
            or not line_of_slight(
                self.archer,
                self.archer.target,
                # use ray with slightly larger size than arrow projectile size
                # this should reduce the chance of shooting a obstacle thru a corner
                ray_size=(30, 30),
            )
        ):
            self.archer.target = None
            return "seeking"

        return None

    def entry_actions(self):

        return None


class ArcherStateKO_TeamA(State):
    def __init__(self, archer):

        State.__init__(self, "ko")
        self.archer = archer

    def do_actions(self):

        return None

    def check_conditions(self):

        # respawned
        if self.archer.current_respawn_time <= 0:
            self.archer.current_respawn_time = self.archer.respawn_time
            self.archer.ko = False
            self.archer.path_graph = self.archer.world.paths[
                randint(0, len(self.archer.world.paths) - 1)
            ]
            return "seeking"

        return None

    def entry_actions(self):

        self.archer.current_hp = self.archer.max_hp
        self.archer.position = Vector2(self.archer.base.spawn_position)
        self.archer.velocity = Vector2(0, 0)
        self.archer.target = None

        return None
