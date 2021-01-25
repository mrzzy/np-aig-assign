import pygame

from random import randint, random
from Graph import *

from World_Ext import wait_and_copy
from Character import *
from State import *


class Knight_TeamA(Character):
    def __init__(self, world, image, base, position):

        Character.__init__(self, world, "knight", image)

        self.base = base
        self.position = position
        self.move_target = GameEntity(world, "knight_move_target", None)
        self.target = None

        self.maxSpeed = 80
        self.min_target_distance = 100
        self.melee_damage = 20
        self.melee_cooldown = 2.0

        waiting_state = wait_and_copy(self.name)(self)
        seeking_state = KnightStateSeeking_TeamA(self)
        fleeing_state = KnightStateFleeing_TeamA(self)
        attacking_state = KnightStateAttacking_TeamA(self)
        ko_state = KnightStateKO_TeamA(self)

        self.brain.add_state(waiting_state)
        self.brain.add_state(seeking_state)
        self.brain.add_state(fleeing_state)
        self.brain.add_state(attacking_state)
        self.brain.add_state(ko_state)

        self.brain.set_state("waiting")

    def render(self, surface):

        Character.render(self, surface)

    def process(self, time_passed):

        Character.process(self, time_passed)

        level_up_stats = ["healing_cooldown", "speed", "melee cooldown"]
        if self.can_level_up():
            choice = randint(0, len(level_up_stats) - 1)
            self.level_up(level_up_stats[choice])


class KnightStateSeeking_TeamA(State):
    def __init__(self, knight):

        State.__init__(self, "seeking")
        self.knight = knight

        self.knight.path_graph = self.knight.world.paths[
            randint(0, len(self.knight.world.paths) - 1)
        ]

    def do_actions(self):

        if self.knight.current_hp < self.knight.max_hp:
            self.knight.heal()

        self.knight.velocity = self.knight.move_target.position - self.knight.position
        if self.knight.velocity.length() > 0:
            self.knight.velocity.normalize_ip()
            self.knight.velocity *= self.knight.maxSpeed

    def check_conditions(self):

        # check if opponent is in range
        nearest_opponent = self.knight.world.get_nearest_opponent(self.knight)
        if nearest_opponent is not None:
            opponent_distance = (
                self.knight.position - nearest_opponent.position
            ).length()
            if opponent_distance <= self.knight.min_target_distance:
                self.knight.target = nearest_opponent
                return "attacking"

        if (self.knight.position - self.knight.move_target.position).length() < 8:

            # continue on path
            if self.current_connection < self.path_length:
                self.knight.move_target.position = self.path[
                    self.current_connection
                ].toNode.position
                self.current_connection += 1

        return None

    def entry_actions(self):

        nearest_node = self.knight.path_graph.get_nearest_node(self.knight.position)

        self.path = pathFindAStar(
            self.knight.path_graph,
            nearest_node,
            self.knight.path_graph.nodes[self.knight.base.target_node_index],
        )

        self.path_length = len(self.path)

        if self.path_length > 0:
            self.current_connection = 0
            self.knight.move_target.position = self.path[0].fromNode.position

        else:
            self.knight.move_target.position = self.knight.path_graph.nodes[
                self.knight.base.target_node_index
            ].position


class KnightStateFleeing_TeamA(State):
    def __init__(self, knight):

        State.__init__(self, "fleeing")
        self.knight = knight

        # set end nodes to be near team base
        if self.knight.team_id == 0:
            keys = [5, 0, 1, 2]
        else:
            keys = [3, 4, 7, 6]

        self.possible_end_nodes = [
            self.knight.world.graph.nodes.get(key) for key in keys
        ]

        # set graph to world graph
        self.path_graph = self.knight.world.graph

    def do_actions(self):

        self.knight.heal()

        if self.knight.move_target.position != None:

            self.knight.velocity = (
                self.knight.move_target.position - self.knight.position
            )

            if self.knight.velocity.length() > 0:
                self.knight.velocity.normalize_ip()
                self.knight.velocity *= self.knight.maxSpeed

    def check_conditions(self):

        if self.knight.target != None:

            # if target targetting chara and chara can kill without dying
            if (
                self.knight.target.target
                and self.knight.target.target.id == self.knight.id
            ):

                enemies = enemies_targetting(self.knight, self.knight.world)

                if time_to_death(self.knight, enemies) > time_to_kill(
                    self.knight, self.knight.target, "melee"
                ):
                    return "attacking"
            else:

                self.knight.target = None
                return "seeking"

        # if knight hp >= 85%
        if self.knight.current_hp >= self.knight.max_hp * 0.85:
            return "seeking"

        if (self.knight.position - self.knight.move_target.position).length() < 8:

            # continue on path
            if self.current_connection < self.path_length:
                self.knight.move_target.position = self.path[
                    self.current_connection
                ].toNode.position
                self.current_connection += 1

            # reached end of path
            else:
                nearest_opponent = self.knight.world.get_nearest_opponent(self.knight)

                # move if there are enemies
                if nearest_opponent is not None:
                    getNewPath(self)

        return None

    def entry_actions(self):

        getNewPath(self)


class KnightStateAttacking_TeamA(State):
    def __init__(self, knight):

        State.__init__(self, "attacking")
        self.knight = knight

    def do_actions(self):

        # colliding with target
        if pygame.sprite.collide_rect(self.knight, self.knight.target):
            self.knight.velocity = Vector2(0, 0)
            self.knight.melee_attack(self.knight.target)

        else:
            self.knight.velocity = self.knight.target.position - self.knight.position
            if self.knight.velocity.length() > 0:
                self.knight.velocity.normalize_ip()
                self.knight.velocity *= self.knight.maxSpeed

    def check_conditions(self):

        # target is gone
        if (
            self.knight.world.get(self.knight.target.id) is None
            or self.knight.target.ko
        ):
            self.knight.target = None
            return "seeking"

        if self.knight.current_hp <= self.knight.max_hp * 0.3:

            enemies = enemies_targetting(self.knight, self.knight.world)

            # if character can kill first
            # or enemies no longer targetting character
            if len(enemies) < 1 or time_to_death(self.knight, enemies) > time_to_kill(
                self.knight, self.knight.target, "melee"
            ):
                return None

            return "fleeing"

        return None

    def entry_actions(self):

        return None


class KnightStateKO_TeamA(State):
    def __init__(self, knight):

        State.__init__(self, "ko")
        self.knight = knight

    def do_actions(self):

        return None

    def check_conditions(self):

        # respawned
        if self.knight.current_respawn_time <= 0:
            self.knight.current_respawn_time = self.knight.respawn_time
            self.knight.ko = False
            self.knight.path_graph = self.knight.world.paths[
                randint(0, len(self.knight.world.paths) - 1)
            ]
            return "seeking"

        return None

    def entry_actions(self):

        self.knight.current_hp = self.knight.max_hp
        self.knight.position = Vector2(self.knight.base.spawn_position)
        self.knight.velocity = Vector2(0, 0)
        self.knight.target = None

        return None


# get numbre of enemies targetting character
def enemies_targetting(chara, world):

    enemies = []

    for entity in world.entities.values():

        # neutral entity
        if entity.team_id == 2:
            continue

        # same team
        if entity.team_id == chara.team_id:
            continue

        if entity.name == "projectile" or entity.name == "explosion":
            continue

        if entity.ko:
            continue

        # check enemy target
        if entity.target:
            if entity.target.id == chara.id:
                enemies.append(entity)

    return enemies


# calculate how long it'll take for enemy to kill
def time_to_death(chara, enemies):

    if len(enemies) < 1:
        return None

    # put enemy attacks, cooldown in separate list
    attack_pts = []
    cooldown = []
    original_cooldown = []

    num_enemies = len(enemies)
    total_damage = 0
    time = 0

    for enemy in enemies:
        if enemy.name == "archer" or enemy.name == "wizard":
            cooldown.append(enemy.ranged_cooldown)
            original_cooldown.append(enemy.ranged_cooldown)
            attack_pts.append(enemy.ranged_damage)

        else:
            cooldown.append(enemy.melee_cooldown)
            original_cooldown.append(enemy.melee_cooldown)
            attack_pts.append(enemy.melee_damage)

    # while loop for each second
    while True:

        # calculate damage done each second
        for i in range(0, num_enemies):

            # -- check cooldown
            if cooldown[i] <= 0:
                # -- if cooldown ended, add damage
                total_damage += attack_pts[i]
                # -- reset cooldown
                cooldown[i] = original_cooldown[i] + cooldown[i]

            else:
                cooldown[i] -= 1

        if total_damage >= chara.current_hp:
            return time

        # increment time
        time += 1


# calculate how long it'll take for character to kill
def time_to_kill(chara, enemy, attack_type):

    attack_speed = 0
    attack_pts = 0

    # projectile or melee
    if attack_type == "ranged":
        attack_speed = chara.ranged_cooldown
        attack_pts = chara.ranged_damage

    else:
        attack_speed = chara.melee_cooldown
        attack_pts = chara.melee_damage

    return (enemy.current_hp / (attack_pts) * attack_speed) + chara.current_healing_cooldown

def getNewPath(chara):
    nearest_node = chara.path_graph.get_nearest_node(chara.knight.position)

    nodes = list(chara.knight.world.graph.nodes.values())
    random_end_node = nearest_node
    while random_end_node.id == nearest_node.id:
        random_end_node = chara.possible_end_nodes[randint(0, 2)]

    chara.path = pathFindAStar(chara.path_graph, nearest_node, random_end_node)

    chara.path_length = len(chara.path)

    if chara.path_length > 0:
        chara.current_connection = 0
        chara.knight.move_target.position = chara.path[0].fromNode.position

    else:
        chara.knight.move_target.position = None
