import pygame
import random
import math
import matplotlib.pyplot as plt
import numpy as np

# --- 1. CONSTANTE GLOBALE ȘI INIȚIALIZARE ---
WIDTH, HEIGHT = 1200, 800
SIM_AREA_WIDTH = 1000  # Zona de joc principală
SIM_AREA_HEIGHT = 800
FPS = 60

# Culori
BACKGROUND_COLOR = (15, 15, 25)
PREY_COLOR = (0, 255, 200)
PREDATOR_COLOR = (255, 50, 50)
FOOD_COLOR = (100, 255, 100)
OBSTACLE_COLOR = (50, 50, 70)
TEXT_COLOR = (220, 220, 220)
UI_BG = (30, 30, 50)

# Parametri de Echilibru FIXAȚI pentru coexistență stabilă
PREY_BASE_SPEED = 2.0
PREDATOR_CHASE_SPEED = 4.0
PREDATOR_ROAM_SPEED = 1.5
PREY_METABOLISM = 0.01
PREDATOR_METABOLISM = 0.2
FOOD_ENERGY_GAIN = 80.0
PRED_ENERGY_GAIN = 90.0

# Reguli de reproducere (Setate conform cerințelor)
PREY_REPRO_THRESHOLD = 0.70  # Energia > 70% din maxim
PRED_REPRO_MIN_PREY = 18  # Prăzi necesare pentru Predator
REPRO_COOLDOWN = 150  # Cooldown pradă (timesteps)
PRED_REPRO_COOLDOWN = 1200  # Cooldown prădător (timesteps)
MATE_TIMER = 40  # Timp petrecut împreună
AGENT_SEPARATION_DIST = 15  # Distanța minimă de separare între orice agent

# Populații inițiale
INIT_PREY = 120
INIT_PRED = 10
INIT_FOOD = 90
INIT_OBSTACLES = 4

# Setari Flocking
SEPARATION_RADIUS = 30
COHESION_RADIUS = 80
ALIGNMENT_RADIUS = 80

# Inițializare Pygame
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Ecosistem Dinamic & Stabil")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("Consolas", 14, bold=True)
TITLE_FONT = pygame.font.SysFont("Arial", 18, bold=True)


# --- 2.  History & Obstacle & Food ---

class HistoryManager:
    def __init__(self):
        self.time_steps = []
        self.prey_pop = []
        self.pred_pop = []
        self.frame_count = 0

    def log(self, prey_count, pred_count):
        if self.frame_count % 30 == 0:
            self.time_steps.append(self.frame_count)
            self.prey_pop.append(prey_count)
            self.pred_pop.append(pred_count)
        self.frame_count += 1

    def show_final_plots(self):
        if not self.time_steps: return
        try:
            plt.figure(figsize=(10, 6))
            plt.plot(self.time_steps, self.prey_pop, label='Prada ', color='cyan', alpha=0.8)
            plt.plot(self.time_steps, self.pred_pop, label='Prădător ', color='red', alpha=0.8)
            plt.title('Analiză Stabilitate Ecosistem')
            plt.xlabel('Timp (Frame-uri)')
            plt.ylabel('Populație')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.show()
        except Exception as e:
            print(f"Eroare la generarea graficului: {e}")


class Obstacle:
    def __init__(self):
        self.position = pygame.math.Vector2(random.uniform(50, SIM_AREA_WIDTH - 50),
                                            random.uniform(50, SIM_AREA_HEIGHT - 50))
        self.radius = random.randint(30, 70)

    def draw(self): pygame.draw.circle(screen, OBSTACLE_COLOR, (int(self.position.x), int(self.position.y)),
                                       self.radius)


class Food:
    def __init__(self):
        self.position = pygame.math.Vector2(random.uniform(20, SIM_AREA_WIDTH - 20),
                                            random.uniform(20, SIM_AREA_HEIGHT - 20))
        self.energy_value = FOOD_ENERGY_GAIN

    def draw(self): pygame.draw.circle(screen, FOOD_COLOR, (int(self.position.x), int(self.position.y)), 3)


# --- 3. CLASA AGENT (DE BAZĂ) ---

class Agent:
    def __init__(self, color, metabolism, max_energy):
        self.position = pygame.math.Vector2(random.uniform(0, SIM_AREA_WIDTH), random.uniform(0, SIM_AREA_HEIGHT))
        self.velocity = pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        self.color = color
        self.original_color = color
        self.trail = []

        self.energy = max_energy * 0.7
        self.max_energy = max_energy
        self.metabolism = metabolism

        self.state = "plimbare"
        self.mate_target = None
        self.mating_timer = 0
        self.reproduction_cooldown = 0
        self.avoid_radius = 45
        self.current_speed = 0

    def update_physics(self, obstacles, all_agents):
        self.energy -= self.metabolism
        self.reproduction_cooldown = max(0, self.reproduction_cooldown - 1)

        if self.state == "reproducere": return

        # 0. Separare de alți agenți (Prevenire suprapunere, inclusiv Prădători)
        separation_force = pygame.math.Vector2(0, 0)
        for other in all_agents:
            if other is self: continue
            dist = self.position.distance_to(other.position)
            if dist < AGENT_SEPARATION_DIST and dist > 0:
                diff = self.position - other.position
                separation_force += diff.normalize() * (1 / dist) * 2  # Forță mai mică dar constantă

        # 1. Evitare Obstacole (FORȚĂ MAI MARE)
        avoid = pygame.math.Vector2(0, 0)
        safe_distance = 35

        for obs in obstacles:
            dist = self.position.distance_to(obs.position)
            # Dacă intră în obstacol → îl împingem afară
            penetration = (obs.radius + 5) - dist
            if penetration > 0:
                # Împingere directă afară
                push = (self.position - obs.position).normalize() * (penetration * 1.5)
                self.position += push

            # Zona de evitare (mult mai largă)
            avoid_dist = obs.radius + safe_distance
            if dist < avoid_dist:
                diff = self.position - obs.position
                force = (avoid_dist - dist) / avoid_dist  # Scade lin cu distanța
                avoid += diff.normalize() * force * 2.2  # Forță mai mare

        if avoid.length() > 0:
            self.velocity += avoid

        # 2. Evitare Margini
        margin = 50
        turn_force = 0.1
        if self.position.x < margin: self.velocity.x += turn_force
        if self.position.x > SIM_AREA_WIDTH - margin: self.velocity.x -= turn_force
        if self.position.y < margin: self.velocity.y += turn_force
        if self.position.y > SIM_AREA_HEIGHT - margin: self.velocity.y -= turn_force

        # Aplică forța de separare
        self.velocity += separation_force * 0.5

        # 3. Aplicare Mișcare
        if self.velocity.length_squared() > 0:
            self.velocity = self.velocity.normalize()
        else:
            self.velocity = pygame.math.Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize() * 0.1

        self.position += self.velocity * self.current_speed

        self.position.x = max(0, min(self.position.x, SIM_AREA_WIDTH))
        self.position.y = max(0, min(self.position.y, SIM_AREA_HEIGHT))

        # 4. Trail
        self.trail.append(self.position.copy())
        if len(self.trail) > 6: self.trail.pop(0)

    def handle_reproduction(self, partners, repro_cost, cooldown_time):
        child = None
        if self.state == "reproducere":
            self.mating_timer -= 1
            self.color = (255, 255, 255)

            if self.mate_target not in partners or self.mate_target.energy <= 0 or self.mate_target.state != "reproducere":
                self.reset_state(0, 0)

            elif self.mating_timer <= 0:
                child = self.spawn()
                self.reset_state(repro_cost, cooldown_time)

        return child

    def reset_state(self, repro_cost, cooldown_time):
        self.state = "plimbare"
        self.energy = max(0, self.energy - repro_cost)
        self.reproduction_cooldown = cooldown_time
        self.color = self.original_color
        if self.mate_target:
            self.mate_target.energy = max(0, self.mate_target.energy - repro_cost)
            self.mate_target.reproduction_cooldown = cooldown_time
            self.mate_target.color = self.mate_target.original_color
        self.mate_target = None

    def spawn(self):
        return None

    def _find_nearest(self, lst, r):
        nearby = [e for e in lst if self.position.distance_to(e.position) < r]
        return min(nearby, key=lambda e: self.position.distance_to(e.position)) if nearby else None


# --- 4. CLASA PREY (PRADĂ) ---

class Prey(Agent):
    def __init__(self):
        super().__init__(color=PREY_COLOR, metabolism=PREY_METABOLISM, max_energy=150.0)
        self.vision_radius = 120

    def spawn(self):
        return Prey()

    def update(self, context):
        preds, preys, foods, obstacles, flocking_enabled = context

        all_agents = preys + preds  # Toți agenții sunt necesari pentru separare
        self.update_physics(obstacles, all_agents)

        if self.energy <= 0: return None, False

        child = self.handle_reproduction(preys, 45.0, REPRO_COOLDOWN)
        if self.state == "reproducere": return child, True

        self.current_speed = PREY_BASE_SPEED

        # 1. FUGA (Prioritate Absolută)
        nearest_pred = self._find_nearest(preds, self.vision_radius)
        if nearest_pred:
            self.state = "fuga"
            self.current_speed = PREY_BASE_SPEED * 1.8
            diff = self.position - nearest_pred.position
            if diff.length() > 0: self.velocity += diff.normalize() * 0.5

            if flocking_enabled: self.apply_flocking(preys, sep_only=True)

        # 2. CĂUTARE DE RESURSE / IMPERECHERE
        else:
            # Flocking
            if flocking_enabled:
                self.apply_flocking(preys, sep_only=False)
                neighbors = len(
                    [p for p in preys if p is not self and self.position.distance_to(p.position) < COHESION_RADIUS])
                if neighbors > 0: self.current_speed += min(neighbors * 0.05, 1.0)

            # Foame (sub 50% energie)
            if self.energy < self.max_energy * 0.5:
                self.state = "foame"
                food = self._find_nearest(foods, 200)
                if food: self._seek(food.position, 0.3)

            # Reproducere (peste prag)
            elif self.energy > self.max_energy * PREY_REPRO_THRESHOLD and self.reproduction_cooldown == 0:
                self.state = "cautare_mate"
                mate = self._find_mate(preys)
                if mate:
                    self._seek(mate.position, 0.3)
                    if self.position.distance_to(mate.position) < 10:
                        self._start_mating(mate, preys)

            # Plimbare
            else:
                self.state = "plimbare"

        return child, True

    def apply_flocking(self, preys, sep_only):
        sep, ali, coh = pygame.math.Vector2(0, 0), pygame.math.Vector2(0, 0), pygame.math.Vector2(0, 0)
        count = 0
        for o in preys:
            if o is self: continue
            d = self.position.distance_to(o.position)
            if d < COHESION_RADIUS:
                count += 1
                if d < SEPARATION_RADIUS and d > 0:
                    diff = self.position - o.position
                    if diff.length() > 0: sep += diff.normalize() / d
                if not sep_only:
                    ali += o.velocity
                    coh += o.position

        if count > 0:
            if not sep_only:
                if ali.length() > 0: ali = (ali / count).normalize()
                coh_dir = (coh / count) - self.position
                if coh_dir.length() > 0: coh = coh_dir.normalize()

            if sep.length() > 0: sep = sep.normalize()
            self.velocity += (sep * 1.5 + ali * 0.8 + coh * 0.6) * 0.15
        return count

    def _seek(self, target_pos, force_multiplier):
        diff = target_pos - self.position
        if diff.length() > 0: self.velocity += diff.normalize() * force_multiplier

    def _find_mate(self, lst):
        repro_energy = self.max_energy * PREY_REPRO_THRESHOLD
        nearby = [p for p in lst if
                  p is not self and p.state == "cautare_mate" and p.energy > repro_energy and p.reproduction_cooldown == 0 and self.position.distance_to(
                      p.position) < self.vision_radius]
        return min(nearby, key=lambda p: self.position.distance_to(p.position)) if nearby else None

    def _start_mating(self, p, preys):
        if p.state == "cautare_mate" and p in preys:
            self.state = "reproducere";
            self.mating_timer = MATE_TIMER;
            self.mate_target = p
            p.state = "reproducere";
            p.mating_timer = MATE_TIMER;
            p.mate_target = self

    def draw(self):
        if len(self.trail) > 1: pygame.draw.lines(screen, self.color, False, [(int(p.x), int(p.y)) for p in self.trail],
                                                  1)
        pygame.draw.circle(screen, self.color, (int(self.position.x), int(self.position.y)), 4)

        bar_ratio = self.energy / self.max_energy
        bar_color = (0, 255, 0) if bar_ratio > 0.5 else (255, 165, 0) if bar_ratio > 0.2 else (255, 0, 0)
        pygame.draw.rect(screen, (50, 50, 50), (int(self.position.x) - 5, int(self.position.y) - 10, 10, 2))
        pygame.draw.rect(screen, bar_color,
                         (int(self.position.x) - 5, int(self.position.y) - 10, int(10 * bar_ratio), 2))


# --- 5. CLASA PREDATOR (PRĂDĂTOR) ---

class Predator(Agent):
    def __init__(self):
        super().__init__(color=PREDATOR_COLOR, metabolism=PREDATOR_METABOLISM, max_energy=100.0)
        self.prey_eaten_count = 0
        self.reproduction_cooldown = 0

    def spawn(self):
        return Predator()

    def update(self, context):
        prey_list, pred_list, obstacles = context

        all_agents = pred_list + prey_list  # Toți agenții sunt necesari pentru separare
        self.update_physics(obstacles, all_agents)

        if self.energy <= 0: return None, False

        nearest_prey = self._find_nearest(prey_list, 250)
        self.current_speed = PREDATOR_ROAM_SPEED

        # 1. VÂNĂTOARE (Forță mare și constantă de căutare)
        if nearest_prey:
            self.state = "alearga"
            self.current_speed = PREDATOR_CHASE_SPEED
            self._seek(nearest_prey.position, 0.6)

        # 2. PATRULARE (Dacă nu vede pradă)
        else:
            self.state = "plimbare"

        return None, True

    def _seek(self, target_pos, force_multiplier):
        diff = target_pos - self.position
        if diff.length() > 0: self.velocity += diff.normalize() * force_multiplier

    def draw(self):
        if len(self.trail) > 1: pygame.draw.lines(screen, self.color, False, [(int(p.x), int(p.y)) for p in self.trail],
                                                  1)

        angle = self.velocity.angle_to(pygame.math.Vector2(1, 0))
        pts = [pygame.math.Vector2(14, 0), pygame.math.Vector2(-7, -7), pygame.math.Vector2(-7, 7)]
        rot_pts = [self.position + p.rotate(-angle) for p in pts]
        pygame.draw.polygon(screen, self.color, rot_pts)

        # Bara de energie
        bar_ratio = self.energy / self.max_energy
        bar_color = (0, 255, 0) if bar_ratio > 0.5 else (255, 165, 0) if bar_ratio > 0.2 else (255, 0, 0)
        pygame.draw.rect(screen, (50, 50, 50), (int(self.position.x) - 5, int(self.position.y) - 10, 10, 2))
        pygame.draw.rect(screen, bar_color,
                         (int(self.position.x) - 5, int(self.position.y) - 10, int(10 * bar_ratio), 2))


# --- 6. SIMULAREA PROPRIU-ZISĂ ---

class Simulation:
    def __init__(self):
        self.prey = [Prey() for _ in range(INIT_PREY)]
        self.preds = [Predator() for _ in range(INIT_PRED)]
        self.food = [Food() for _ in range(INIT_FOOD)]
        self.obstacles = [Obstacle() for _ in range(INIT_OBSTACLES)]
        self.history = HistoryManager()
        self.running = True

        self.food_rate = 9
        self.flocking_enabled = True  # Controlabil prin UI

    def run(self):
        while self.running:
            clock.tick(FPS)
            self.handle_input()
            self.manage_env()
            self.update_agents()
            self.check_collisions()
            self.render()

        pygame.quit()
        self.history.show_final_plots()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                # Adăugare Manuală (P/O/B/M)
                if event.key == pygame.K_p:
                    self.prey.append(Prey())
                elif event.key == pygame.K_o:
                    self.preds.append(Predator())
                elif event.key == pygame.K_b:
                    self.obstacles.append(Obstacle())
                elif event.key == pygame.K_m:
                    self.food.append(Food())

                # Flocking Toggle [F]
                elif event.key == pygame.K_f:
                    self.flocking_enabled = not self.flocking_enabled

    def manage_env(self):
        # Food Spawning
        if len(self.food) < 150 and random.randint(0, 100) < self.food_rate:
            self.food.append(Food())

    def update_agents(self):
        # Update Prey
        next_prey, babies = [], []
        for p in self.prey:
            context = (self.preds, self.prey, self.food, self.obstacles, self.flocking_enabled)
            child, alive = p.update(context)
            if alive: next_prey.append(p)
            if child: babies.append(child)
        self.prey = next_prey + babies

        # Update Preds
        next_pred = []
        for p in self.preds:
            context = (self.prey, self.preds, self.obstacles)
            child, alive = p.update(context)
            if alive: next_pred.append(p)
        self.preds = next_pred

        self.history.log(len(self.prey), len(self.preds))

    def check_collisions(self):
        new_preds = []

        # Eating Food
        for p in self.prey:
            if p.state == "reproducere": continue
            for f in self.food[:]:
                if p.position.distance_to(f.position) < 8:
                    self.food.remove(f);
                    p.energy = min(p.energy + f.energy_value, p.max_energy);
                    break

        # Eating Prey & Predator Simple Reproduction (după 10 prăzi)
        for pred in self.preds:
            for p in self.prey[:]:
                if pred.position.distance_to(p.position) < 12:
                    self.prey.remove(p)
                    pred.energy = min(pred.energy + PRED_ENERGY_GAIN, pred.max_energy)
                    pred.prey_eaten_count += 1

                    # Logica de reproducere (instantanee)
                    if pred.prey_eaten_count >= PRED_REPRO_MIN_PREY and pred.reproduction_cooldown == 0:
                        # Puiul apare la aceeași poziție (sau ușor deplasat)
                        new_pred = Predator()
                        new_pred.position = pred.position.copy()
                        new_preds.append(new_pred)

                        pred.prey_eaten_count = 0  # Resetare contor
                        pred.reproduction_cooldown = PRED_REPRO_COOLDOWN  # Aplică cooldown
                    break

        self.preds.extend(new_preds)

    def render(self):
        screen.fill(BACKGROUND_COLOR)
        pygame.draw.rect(screen, (30, 30, 45), (0, 0, SIM_AREA_WIDTH, SIM_AREA_HEIGHT), 1)

        for o in self.obstacles: o.draw()
        for f in self.food: f.draw()
        for p in self.prey: p.draw()
        for p in self.preds: p.draw()

        self.draw_ui()
        pygame.display.flip()

    def draw_ui(self):
        # Panou Control (dreapta)
        panel_rect = (SIM_AREA_WIDTH, 0, WIDTH - SIM_AREA_WIDTH, HEIGHT)
        pygame.draw.rect(screen, UI_BG, panel_rect)

        x_start = SIM_AREA_WIDTH + 10
        y_start = 15
        line_height = 20

        # Header
        screen.blit(TITLE_FONT.render("STATISTICI ECOSISTEM", True, (255, 255, 255)), (x_start, y_start))

        # Stats
        y = y_start + line_height + 5
        prey_color = PREY_COLOR if len(self.prey) > 20 else (255, 255, 0) if len(self.prey) > 5 else (255, 0, 0)
        pred_color = PREDATOR_COLOR if len(self.preds) > 5 else (255, 255, 0) if len(self.preds) > 1 else (255, 0, 0)

        screen.blit(FONT.render(f"Pradă : {len(self.prey)}", True, prey_color), (x_start, y));
        y += 15
        screen.blit(FONT.render(f"Prădător : {len(self.preds)}", True, pred_color), (x_start, y));
        y += 15
        screen.blit(FONT.render(f"Hrană : {len(self.food)}", True, FOOD_COLOR), (x_start, y));
        y += 20
        screen.blit(FONT.render(f"Timesteps: {self.history.frame_count}", True, TEXT_COLOR), (x_start, y));
        y += 20

        # Flocking Toggle Status
        flocking_status = "ON" if self.flocking_enabled else "OFF"
        flocking_color = (0, 255, 0) if self.flocking_enabled else (255, 100, 100)
        screen.blit(FONT.render(f"[F] Flocking: {flocking_status}", True, flocking_color), (x_start, y));
        y += 20

        # Controale Manuale
        screen.blit(TITLE_FONT.render("ADAUGĂ MANUAL", True, (255, 255, 255)), (x_start, y));
        y += line_height

        screen.blit(FONT.render("[P] Adaugă pradă", True, PREY_COLOR), (x_start, y));
        y += 15
        screen.blit(FONT.render("[O] Adaugă prădător", True, PREDATOR_COLOR), (x_start, y));
        y += 15
        screen.blit(FONT.render("[M] Adaugă hrană", True, FOOD_COLOR), (x_start, y));
        y += 15
        screen.blit(FONT.render("[B] Adaugă obstacol", True, OBSTACLE_COLOR), (x_start, y));
        y += 20


if __name__ == "__main__":
    sim = Simulation()
    sim.run()