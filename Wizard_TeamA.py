import pygame
from pygame.math import *

from random import randint

from Graph import *

from Character import *
from State import *

from World_Ext import *

# Assume no enemy will have a ranged attack upgraded beyond 5 levels
FLEE_RADIUS = 220 * 1.1 ** 5


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
        if DEBUG or True:
            if not self.ko:
                for flee_target in self.flee_targets:
                    pygame.draw.line(
                        surface,
                        (0, 255, 0),
                        self.position,
                        flee_target.position,
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
        if self.wizard.current_hp <= self.wizard.max_hp * 0.5:
            return "fleeing"

        # check if opponent is in range
        nearest_opponent = self.wizard.world.get_nearest_opponent(self.wizard)
        if nearest_opponent is not None:
            opponent_distance = (
                self.wizard.position - nearest_opponent.position
            ).length()
            if opponent_distance <= self.wizard.min_target_distance:
                self.wizard.target = nearest_opponent
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

    def do_actions(self):

        opponent_distance = (
            self.wizard.position - self.wizard.target.position
        ).length()

        # opponent within range
        if opponent_distance <= self.wizard.min_target_distance:
            self.wizard.velocity = Vector2(0, 0)
            if self.wizard.current_ranged_cooldown <= 0:
                position = self.wizard.target.position

                # Hit all three things when possible
                if self.wizard.target.name in {"tower", "base"}:
                    # Right-side base
                    position = Vector2(881, 626)
                    # Flip if the target base is the left-side base
                    if self.wizard.target.position.x > 1024:
                        position = Vector2(*SCREEN_SIZE) - position

                self.wizard.ranged_attack(position, self.wizard.explosion_image)

        else:
            self.wizard.velocity = self.wizard.target.position - self.wizard.position
            if self.wizard.velocity.length() > 0:
                self.wizard.velocity.normalize_ip()
                self.wizard.velocity *= self.wizard.maxSpeed

    def check_conditions(self):
        if self.wizard.current_hp <= self.wizard.max_hp * 0.3:
            return "fleeing"

        # target is gone
        if (
            self.wizard.world.get(self.wizard.target.id) is None
            or self.wizard.target.ko
        ):
            self.wizard.target = None
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

        # # Calculate the flee direction from all the threats
        final_direction = avoid_entities(self.wizard, immediate_threats)

        if not immediate_threats:
            final_direction = avoid_entities(self.wizard, non_immediate_threats)

        # # Move along the obstacle lines if near them
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
