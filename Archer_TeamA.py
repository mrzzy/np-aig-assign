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
        if (
            getattr(e, "target", None) is not None
            and e.target.id == entity.id
            and (e.position - entity.position).length() < ARCHER_MIN_TARGET_DISTANCE
        )
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
        searching_state = ArcherStateSearching_TeamA(self)
        ko_state = ArcherStateKO_TeamA(self)

        self.brain.add_state(seeking_state)
        self.brain.add_state(combat_state)
        self.brain.add_state(searching_state)
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
            ("ranged cooldown", 0.6),
            ("projectile range", 0.3),
            ("healing cooldown", 0.1),
        ]
        if self.can_level_up():
            upgrade_stat = random_choices(
                population=[s[0] for s in level_up_stats_weighted],
                weights=[s[1] for s in level_up_stats_weighted],
                k=1,
            )[0]
            self.level_up(upgrade_stat)
            if upgrade_stat == "projectile range":
                self.min_target_distance = self.projectile_range


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
        # TODO (mrzzy): replace with collect_threats()
        attackers = get_attackers(self.archer)
        if len(attackers) > 0:
            # TODO(mrzzy): fight back against most threatening attacker
            # fight back against nearest attacker
            opponent = attackers[0]
        else:
            # fight nearest opponent
            opponent = find_closest_opponent(
                graph=self.archer.world.graph, entity=self.archer
            )

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
        nearest_node = get_visible_node(self.archer.path_graph, self.archer)

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
    Archer is engaging its target in combat.
    """

    def __init__(self, archer):

        State.__init__(self, "combat")
        self.archer = archer
        self.correct_pos = None

    def do_actions(self):
        # check if being attacked
        # TODO (mrzzy): replace with collect_threats()
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
            # move retreat to attack at a safe distance.
            _, move_pos = find_closest_point(
                points=self.path_pts,
                position=current_pos,
                predicate=(lambda pt: (pt - opponent.position).length() >= safe_dist),
            )
        self.archer.move_target.position = move_pos
        self.archer.velocity = seek(self.archer, self.archer.move_target.position)

    def check_conditions(self):
        # target has KOed
        if is_target_ko(self.archer):
            self.archer.target = None
            return "seeking"

        # lost line of sight: search for target or out of range
        if not line_of_slight(self.archer, self.archer.target, ray_size=(30, 30)):
            return "searching"

        return None

    def entry_actions(self):
        # compile a list of unordered position/points of each node in the path graph
        self.path_pts = [n.position for n in self.archer.path_graph.nodes.values()]
        return None


class ArcherStateSearching_TeamA(State):
    """
    Archer is searching for its target
    """

    def __init__(self, archer):
        State.__init__(self, "searching")
        self.archer = archer
        self.search_offset = 150

    def do_actions(self):
        # move to search the target's position, navigating the graph as required.
        current_pos, opponent, world, graph, time_passed = (
            self.archer.position,
            self.archer.target,
            self.archer.world,
            self.archer.world.graph,
            self.archer.time_passed,
        )
        nearest_node = get_visible_node(graph, self.archer)
        search_node = get_visible_node(graph, opponent)
        if nearest_node.id != search_node.id:
            # use a-star to find route to target when multi node traversal is required
            connections = pathFindAStar(
                graph,
                nearest_node,
                search_node,
            )
            move_pos = connections[0].toNode.position
        else:
            move_pos = search_node.position
        self.archer.velocity = seek(self.archer, move_pos)

    def check_conditions(self):
        # target has KOed
        if is_target_ko(self.archer):
            self.archer.target = None
            return "seeking"
        # route to target is too far
        graph, opponent = self.archer.world.graph, self.archer.target
        if route_dist(graph, self.archer, opponent) > (
            self.archer.min_target_distance + self.search_offset
        ):
            return "seeking"

        # regain line of sight: return to combat mode
        if line_of_slight(self.archer, self.archer.target, ray_size=(30, 30)):
            return "combat"


# TODO(mrzzy): add fleeing state


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
