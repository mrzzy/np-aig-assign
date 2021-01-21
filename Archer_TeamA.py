import pygame
from pygame import Vector2, Surface
from random import randint, random, choices as random_choices
from Graph import *

from Character import *
from State import *
from World_Ext import *


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
    def __init__(self, archer):

        State.__init__(self, "seeking")
        self.archer = archer

        self.archer.path_graph = self.archer.world.paths[
            randint(0, len(self.archer.world.paths) - 1)
        ]

    def do_actions(self):
        self.archer.velocity = seek(self.archer, self.archer.move_target.position)

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

        opponent, current_pos, time_passed = (
            self.archer.target,
            self.archer.position,
            self.archer.time_passed,
        )
        # project the opponents position in the next frame
        # using a the time passsed of the previous frame as reference
        projected_pos = project_position(opponent, time_passed)
        opponent_dist = (projected_pos - current_pos).length()

        # attack: attack opponent when within range
        if (
            opponent_dist <= self.archer.projectile_range
            and self.archer.current_ranged_cooldown <= 0
        ):
            # project the position when the arrow should hit the opponent
            # take into account arrow travel time
            projected_travel_time = opponent_dist / self.archer.projectile_speed
            attack_pos = project_position(opponent, time_passed + projected_travel_time)
            self.archer.ranged_attack(attack_pos)

        # movement: practice safe distancing by move to attack at safe distance.
        safe_dist = self.archer.projectile_range
        # +- safe_offset is considered safe distance
        safe_offset = 4
        if abs(opponent_dist - safe_dist) <= safe_offset:
            # opponent within range: stop to attack
            move_pos = current_pos
        elif opponent_dist > safe_dist:
            # seek opponent if out of ranged
            move_pos = projected_pos
        elif opponent_dist < safe_dist:
            # move towards nearest point in path that is also moving away from opponent
            _, move_pos = find_closest_point(
                points=self.path_pts,
                position=current_pos,
                predicate=(lambda pt: (pt - opponent.position).length() >= safe_dist),
            )
        self.archer.move_target.position = move_pos
        self.archer.velocity = seek(self.archer, self.archer.move_target.position)

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
        # compile a list of unordered position/points of each node in the path graph
        self.path_pts = [n.position for n in self.archer.path_graph.nodes.values()]
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
