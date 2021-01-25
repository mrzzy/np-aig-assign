import pygame
from pygame import Vector2, Surface
from random import randint, random, choices as random_choices, choice as random_choice
from Graph import *

from Character import *
from State import *
from World_Ext import *


# TODO(mrzzy): replace this
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
            and (e.position - entity.position).length() < entity.min_target_distance
        )
    ]
    return sorted(
        attackers, key=(lambda attacker: (attacker.position - entity.position).length())
    )


class Archer_TeamA(Character):
    def __init__(self, world, image, projectile_image, base, position):

        Character.__init__(self, world, "archer", image)

        self.projectile_image = projectile_image
        self.projectile_size = projectile_image.get_rect().size

        self.base = base
        self.position = position
        self.move_target = GameEntity(world, "archer_move_target", None)
        self.target = None

        self.maxSpeed = 50
        self.min_target_distance = 100
        self.projectile_range = 100
        self.projectile_speed = 100

        self.graph = interpolate_graph(self.world.graph)
        # choose a random starting node, ultimately deciding the path taken
        starting_nodes = [
            c.toNode
            for c in self.graph.getConnections(
                self.graph.nodes[self.base.spawn_node_index]
            )
        ]
        self.starting_node = random_choice(starting_nodes)

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
            ("projectile range", 0.2),
            ("speed", 0.2),
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

    def get_opponent(self):
        # TODO (mrzzy): replace with collect_threats()
        # check if being attacked
        attackers = get_attackers(self.archer)
        if len(attackers) > 0:
            # TODO(mrzzy): fight back against most threatening attacker
            # fight back against nearest attacker
            opponent = attackers[0]
        else:
            # fight nearest opponent
            opponent = find_closest_opponent(
                graph=self.archer.graph,
                entity=self.archer,
                terror_radius=self.archer.min_target_distance,
            )

        return opponent

    def do_actions(self):
        self.archer.velocity = seek(self.archer, self.archer.move_target.position)
        self.opponent = self.get_opponent()

        # patch up health while seeking and no opponent in sight
        if self.archer.current_hp < self.archer.max_hp and not self.opponent:
            self.archer.heal()

    def check_conditions(self):
        opponent = self.opponent
        if opponent is not None:
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
        base = self.archer.base
        if distance(self.archer.position, base.spawn_position) <= 0:
            # just spawned: navigating via starting node
            start_node = self.archer.starting_node
        else:
            # continue navigating to enemy base via nearest node
            start_node = self.archer.graph.get_nearest_node(self.archer.position)

        self.path = pathFindAStar(
            self.archer.graph,
            start_node,
            self.archer.graph.nodes[base.target_node_index],
        )

        self.path_length = len(self.path)

        if self.path_length > 0:
            self.current_connection = 0
            self.archer.move_target.position = self.path[0].fromNode.position

        else:
            self.archer.move_target.position = self.archer.graph.nodes[
                base.target_node_index
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
        # TODO: remove
        self.archer.projected_pos = projected_pos

        # attack: attack opponent when within range
        if (
            opponent_dist <= self.archer.projectile_range
            and self.archer.current_ranged_cooldown <= 0
        ):
            projected_travel_time = opponent_dist / self.archer.projectile_speed
            attack_pos = project_position(opponent, time_passed + projected_travel_time)
            self.archer.ranged_attack(attack_pos)
            # TODO: remove
            self.archer.attack_pos = attack_pos

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
        if not line_of_slight(
            self.archer, self.archer.target, ray_width=self.archer.projectile_size[1]
        ):
            return "searching"

        return None

    def entry_actions(self):
        # compile a list of unordered position/points of each node in the graph
        self.path_pts = [n.position for n in self.archer.graph.nodes.values()]
        return None


class ArcherStateSearching_TeamA(State):
    """
    Archer is searching for its target
    """

    def __init__(self, archer):
        State.__init__(self, "searching")
        self.archer = archer
        self.search_offset = 150
        self.heal_threshold = 0.70
        self.regain_sight_threshold = 1.4

    def do_actions(self):
        # patch up on health when searching
        if (self.archer.current_hp / self.archer.max_hp) < self.heal_threshold:
            self.archer.heal()

        # move to search the target's position, navigating the graph as required.
        current_pos, opponent, world, graph, time_passed = (
            self.archer.position,
            self.archer.target,
            self.archer.world,
            self.archer.graph,
            self.archer.time_passed,
        )
        nearest_node = graph.get_nearest_node(self.archer.position)
        search_node = graph.get_nearest_node(opponent.position)
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
        graph, opponent = self.archer.graph, self.archer.target
        if route_dist(graph, self.archer.position, opponent.position) > (
            self.archer.min_target_distance + self.search_offset
        ):
            return "seeking"

        # regain line of sight: return to combat mode
        if line_of_slight(
            self.archer,
            self.archer.target,
            ray_width=self.archer.projectile_size[1] * self.regain_sight_threshold,
        ):
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
