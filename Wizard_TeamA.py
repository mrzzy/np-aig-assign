import pygame
from pygame.math import *

from random import randint, random
from Graph import *

from Character import *
from State import *

# World extensions
def entity_is_hostile(entity, team_id):
    if entity.team_id == team_id:
        return False

    if entity.team_id == 2 and entity.name != "tower":
        return False

    return True


def entity_is_immediate_threat(entity, victim_entity):
    # Ignore entities that are on the same team
    if entity.team_id == victim_entity.team_id:
        return False

    if entity.name == "projectile" or entity.name == "explosion":
        return True

    # TODO(joeltio): Any hostile that is close to the entity is a threat as well
    if entity.name == "knight" and entity_is_in_radius(entity, victim_entity, 100):
        return True

    return False


def entity_is_in_radius(entity, source_entity, radius):
    return (source_entity.position - entity.position).length() <= radius


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

        pygame.draw.circle(
            surface,
            (0, 0, 0),
            (int(self.position[0]), int(self.position[1])),
            int(100),
            int(2),
        )

        # Show flee targets if any
        if DEBUG or True:
            if not self.ko:
                for flee_target in self.flee_targets:
                    pygame.draw.line(
                        surface, (0, 255, 0), self.position, flee_target.position,
                    )

    def process(self, time_passed):

        Character.process(self, time_passed)

        level_up_stats = [
            "hp",
            "speed",
            "ranged damage",
            "ranged cooldown",
            "projectile range",
        ]
        if self.can_level_up():
            choice = randint(0, len(level_up_stats) - 1)
            self.level_up("ranged cooldown")


def dodge_imm_threat_vec(threat, entity):
    if threat.name == "projectile":
        # Move perpendicular to the direction of the projectile
        # When a vector is perpendicular to another vector, the dot product is
        # zero. We can pick a random value for the other vector's x (1). Solving
        # with this information we get this formula: y2 = -x1/y1
        x1, y1 = threat.velocity
        return Vector2(
            1,
            -x1/y1
        ).normalize()

    # Assume it is an explosion otherwise
    # Flee away
    return (entity.position - threat.position).normalize()


def dodge_opponent_vec(opp_character, entity):
    # TODO(joeltio): Knights can still trap enemies at an edge
    return (entity.position - opp_character.position).normalize()

# Assume no enemy will have a ranged attack upgraded beyond 5 levels
FLEE_RADIUS = 220 * 1.1 ** 5


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
                self.wizard.ranged_attack(
                    self.wizard.target.position, self.wizard.explosion_image
                )

        else:
            self.wizard.velocity = self.wizard.target.position - self.wizard.position
            if self.wizard.velocity.length() > 0:
                self.wizard.velocity.normalize_ip()
                self.wizard.velocity *= self.wizard.maxSpeed

    def check_conditions(self):
        if self.wizard.current_hp <= self.wizard.max_hp * 0.5:
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
        hostile_entities = [
            e for e in
            self.wizard.world.entities.values()
            if entity_is_in_radius(e, self.wizard, FLEE_RADIUS)
                and entity_is_hostile(e, self.wizard.team_id)
        ]

        # Dodge immediate threats
        immediate_threats = [
            e for e in hostile_entities
            if entity_is_immediate_threat(e, self.wizard)
        ]
        if immediate_threats:
            print("fleeing from:", [x.name for x in immediate_threats])


        # Set flee targets
        self.wizard.flee_targets = immediate_threats

        # Calculate the flee direction from all the threats
        final_direction = Vector2(0, 0)
        for e in immediate_threats:
            final_direction += dodge_imm_threat_vec(e, self.wizard)

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
