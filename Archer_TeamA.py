import pygame
from pygame import Vector2
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


def seek(entity, move_pos):
    """
    Move towards move_pos at max speed
    """
    entity.velocity = move_pos - entity.position
    if entity.velocity.length() > 0:
        entity.velocity.normalize_ip()
        entity.velocity *= entity.maxSpeed


def avoid_obstacle(entity):
    """
    When colliding with the obstacle, direct entity to move in the opposite direction
    of the collision to avoid the obstacle.
    """
    collisions = detect_collisions(entity)
    if len(collisions) >= 1:
        collided, collide_pt = collisions[0]
        normal = entity.position - collide_pt
        # move in the direction of the normal to avoid the obstacle
        normal_heading = normal.normalize()
        move_target = collide_pt + (normal_heading * entity.maxSpeed)
        seek(entity, move_target)


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

    def render(self, surface):
        Character.render(self, surface)

    def process(self, time_passed):

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

        # check if opponent is in range
        nearest_opponent = self.archer.world.get_nearest_opponent(self.archer)
        if nearest_opponent is not None:
            opponent_distance = (
                self.archer.position - nearest_opponent.position
            ).length()
            if opponent_distance <= self.archer.min_target_distance:
                self.archer.target = nearest_opponent
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

    def do_actions(self):

        target = self.archer.target
        target_distance = (self.archer.position - target.position).length()
        current_pos = self.archer.position

        # attack: attack target when within range
        if target_distance <= self.archer.projectile_range:
            self.archer.velocity = Vector2(0, 0)
            if self.archer.current_ranged_cooldown <= 0:
                attack_pos = target.position
                self.archer.ranged_attack(attack_pos)

        # movement: stay only close enough to attack
        if target_distance > self.archer.projectile_range:
            # seek target if out of range
            seek(self.archer, target.position)
        elif target_distance < self.archer.projectile_range:
            # move to attack at safe distance
            # move towards nearest node that is also moving away from opponent
            away_node = get_away_node(
                self.archer.path_graph, current_pos, target.position
            )
            move_heading = (away_node.position - current_pos).normalize()
            move_magnitude = target_distance - self.archer.projectile_range
            move_target = move_heading * move_magnitude
            seek(self.archer, move_target)

        # movement: correct movement when colliding to prevent getting stuck on walls
        avoid_obstacle(self.archer)

    def check_conditions(self):

        # target is gone
        if (
            self.archer.world.get(self.archer.target.id) is None
            or self.archer.target.ko
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
