import pygame
from pygame.math import *

from random import randint

from Graph import *

from Character import *
from State import *

from World_Ext import *

# Assume no enemy will have a ranged attack upgraded beyond 5 levels
FLEE_RADIUS = 220 * 1.1 ** 5
# 220 is the maximum radius of the projectile
# 48 is half the size of the explosion
ATTACK_CONSIDER_RADIUS = 220 + 48
# The spot to hit to hit all 3 buildings
SWEET_SPOT_BLUE = Vector2(881, 626)
SWEET_SPOT_RED = Vector2(*SCREEN_SIZE) - Vector2(881, 626)


class Wizard_TeamA(Character):
    def __init__(
        self, world, image, projectile_image, base, position, explosion_image=None
    ):

        Character.__init__(self, world, "wizard", image)

        self.projectile_image = projectile_image
        self.explosion_image = explosion_image

        self.base = base
        self.position = position
        self.move_target = GameEntity(world, "wizard_move_target", None)
        self.target = None
        self.flee_targets = []

        self.maxSpeed = 50
        self.min_target_distance = 100
        self.projectile_range = 100
        self.projectile_speed = 100

        seeking_state = WizardStateSeeking_TeamA(self)
        fleeing_state = WizardStateFleeing_TeamA(self)
        attacking_state = WizardStateAttacking_TeamA(self)
        ko_state = WizardStateKO_TeamA(self)

        self.brain.add_state(seeking_state)
        self.brain.add_state(fleeing_state)
        self.brain.add_state(attacking_state)
        self.brain.add_state(ko_state)

        self.brain.set_state("seeking")

    def render(self, surface):

        Character.render(self, surface)

        # Show flee targets if any
        if DEBUG and not self.ko:
            for flee_target in self.flee_targets:
                pygame.draw.line(
                    surface,
                    (0, 255, 0),
                    self.position,
                    flee_target.position,
                )

            pygame.draw.circle(
                surface,
                (0, 0, 0),
                tuple(map(int, self.position)),
                ATTACK_CONSIDER_RADIUS,
                2,
            )

    def process(self, time_passed):

        Character.process(self, time_passed)

        if self.can_level_up():
            self.level_up("ranged cooldown")


class WizardStateSeeking_TeamA(State):
    def __init__(self, wizard):

        State.__init__(self, "seeking")
        self.wizard = wizard

        self.wizard.path_graph = self.wizard.world.paths[
            randint(0, len(self.wizard.world.paths) - 1)
        ]

    def do_actions(self):

        self.wizard.velocity = self.wizard.move_target.position - self.wizard.position
        if self.wizard.velocity.length() > 0:
            self.wizard.velocity.normalize_ip()
            self.wizard.velocity *= self.wizard.maxSpeed

    def check_conditions(self):
        if self.wizard.current_hp <= self.wizard.max_hp * 0.3:
            return "fleeing"

        opponents = find_closest_opponent(
            self.wizard.world.graph,
            self.wizard,
            ATTACK_CONSIDER_RADIUS,
        )

        if opponents:
            self.wizard.targets = opponents
            return "attacking"

        if (self.wizard.position - self.wizard.move_target.position).length() < 8:

            # continue on path
            if self.current_connection < self.path_length:
                self.wizard.move_target.position = self.path[
                    self.current_connection
                ].toNode.position
                self.current_connection += 1

        return None

    def entry_actions(self):

        nearest_node = self.wizard.path_graph.get_nearest_node(self.wizard.position)

        self.path = pathFindAStar(
            self.wizard.path_graph,
            nearest_node,
            self.wizard.path_graph.nodes[self.wizard.base.target_node_index],
        )

        self.path_length = len(self.path)

        if self.path_length > 0:
            self.current_connection = 0
            self.wizard.move_target.position = self.path[0].fromNode.position

        else:
            self.wizard.move_target.position = self.wizard.path_graph.nodes[
                self.wizard.base.target_node_index
            ].position


class WizardStateAttacking_TeamA(State):
    def __init__(self, wizard):

        State.__init__(self, "attacking")
        self.wizard = wizard
        if self.wizard.team_id == 0:
            self.sweet_spot = SWEET_SPOT_BLUE
        else:
            self.sweet_spot = SWEET_SPOT_RED

    def do_actions(self):
        self.wizard.targets = find_closest_opponents(
            self.wizard.world.graph,
            self.wizard,
            ATTACK_CONSIDER_RADIUS,
        )

        target_positions = []
        for target in self.wizard.targets:
            pos = find_ideal_projectile_target(
                target, self.wizard.position, self.wizard.projectile_speed
            )
            target_positions.append(pos)
            if target.name in {"tower", "base"}:
                # Hit all three things when possible
                target_positions = [self.sweet_spot]

        if target_positions:
            target_positions = remove_outliers(target_positions)
            position = calculate_mean(target_positions)

            self.wizard.velocity = Vector2(0, 0)
            if self.wizard.current_ranged_cooldown <= 0:
                self.wizard.ranged_attack(position, self.wizard.explosion_image)

            if (
                target_positions[0] == self.sweet_spot
                and distance(self.wizard.position, self.sweet_spot)
                > self.wizard.projectile_range
            ):
                # Move towards the sweet spot
                final_direction = self.sweet_spot - self.wizard.position
                final_direction = avoid_obstacles(self.wizard, final_direction)

                # Glide along edges
                final_direction = avoid_edges(self.wizard.position, final_direction)

                self.wizard.velocity = final_direction

                if self.wizard.velocity.length() > 0:
                    self.wizard.velocity.normalize_ip()
                    self.wizard.velocity *= self.wizard.maxSpeed

    def check_conditions(self):
        if self.wizard.current_hp <= self.wizard.max_hp * 0.3:
            return "fleeing"

        if len(self.wizard.targets) == 0:
            return "seeking"

        return None

    def entry_actions(self):

        return None


class WizardStateFleeing_TeamA(State):
    def __init__(self, wizard):
        super().__init__("fleeing")
        self.wizard = wizard

    def do_actions(self):
        # Try and heal
        if self.wizard.current_hp != self.wizard.max_hp:
            self.wizard.heal()

        # Get all hostile entities within FLEE_RADIUS
        # Dodge immediate threats
        immediate_threats, non_immediate_threats = collect_threats(
            self.wizard, FLEE_RADIUS
        )
        # Set flee targets
        self.wizard.flee_targets = immediate_threats

        # Calculate the flee direction from all the threats
        final_direction = avoid_entities(self.wizard, immediate_threats)

        if not immediate_threats:
            final_direction = avoid_entities(self.wizard, non_immediate_threats)

        # Move along the obstacle lines if near them
        final_direction = avoid_obstacles(self.wizard, final_direction)

        # Glide along edges
        final_direction = avoid_edges(self.wizard.position, final_direction)

        # Flee
        self.wizard.velocity = final_direction
        if self.wizard.velocity.length() > 0:
            self.wizard.velocity.normalize_ip()
            self.wizard.velocity *= self.wizard.maxSpeed

    def check_conditions(self):
        if self.wizard.current_hp == self.wizard.max_hp:
            return "seeking"


class WizardStateKO_TeamA(State):
    def __init__(self, wizard):

        State.__init__(self, "ko")
        self.wizard = wizard

    def do_actions(self):

        return None

    def check_conditions(self):

        # respawned
        if self.wizard.current_respawn_time <= 0:
            self.wizard.current_respawn_time = self.wizard.respawn_time
            self.wizard.ko = False
            self.wizard.path_graph = self.wizard.world.paths[
                randint(0, len(self.wizard.world.paths) - 1)
            ]
            return "seeking"

        return None

    def entry_actions(self):

        self.wizard.current_hp = self.wizard.max_hp
        self.wizard.position = Vector2(self.wizard.base.spawn_position)
        self.wizard.velocity = Vector2(0, 0)
        self.wizard.target = None

        return None
