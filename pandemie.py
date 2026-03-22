import pygame
import random
import math
import matplotlib.pyplot as plt
from collections import deque

# ---------------- CONFIGURARE ----------------
# Dimensiuni fereastra si zona de simulare
WIDTH, HEIGHT = 1200, 800
SIM_W, SIM_H = 800, HEIGHT
FPS = 60  # cadre pe secunda

# Culori pentru agenti si UI
BG = (18, 18, 28)          # fundal
SUSC_COLOR = (50, 200, 255) # susceptibili
INF_COLOR = (220, 60, 60)   # infectati
REC_COLOR = (130, 230, 120) # recuperati
DEAD_COLOR = (80, 80, 80)   # morti
UI_BG = (25, 25, 40)        # fundal UI
TEXT = (220, 220, 220)      # culoare text
QUAR_COLOR = (80, 80, 140, 80) # zona de carantina (translucida)

# Populatie
N_AGENTS = 160      # numar total agenti
INIT_INFECTED = 3   # infectati initial

# Miscare
BASE_SPEED = 1.2
GROUP_CHANCE = 0.002 # sansa sa se adune in grupuri mici
GROUP_FORCE = 0.05   # forta miscarii catre centru grup

# Parametri infectie (modificabili in runtime)
infection_prob_per_sec = 0.35
infection_radius = 12
contact_accumulate_time = 0.0
recovery_time = 30.0
recovery_success_prob = 0.3
mortality_on_failure = True
vaccination_decision_rate = 0.25
vaccination_success_prob = 0.9
vaccination_instant_rate = 0.0

# Zona de carantina
quarantine_enabled = True
quarantine_rect = pygame.Rect(SIM_W - 140, 40, 120, 240)
quarantine_accept_infected = True

# Istoric pentru grafice
history_step_interval = 6

# ---------------- INITIALIZARE PYGAME ----------------
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Minimalist SIR Simulator")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("Consolas", 14)
TITLE = pygame.font.SysFont("Arial", 18, bold=True)

# ---------------- CLASA AGENT ----------------
class Agent:
    def __init__(self):
        # Pozitia agentului pe harta
        self.pos = pygame.math.Vector2(random.uniform(20, SIM_W - 20),
                                       random.uniform(20, SIM_H - 20))
        # Directia initiala random
        angle = random.uniform(0, math.tau)
        self.vel = pygame.math.Vector2(math.cos(angle), math.sin(angle)) * BASE_SPEED
        self.state = "S"  # S - susceptibil, I - infectat, R - recuperat, D - mort
        self.infected_timer = 0.0  # timpul de cand agentul e infectat
        self.contact_time = {}     # tine minte timpul de contact cu agentii infectati
        self.quarantined = False   # daca agentul e izolat

    def update(self, dt, agents):
        # daca agentul e mort, nu face nimic
        if self.state == "D":
            return

        # daca agentul e in carantina, nu se misca
        if self.quarantined:
            pass
        else:
            # miscarea random si gruparea ocazionala
            if random.random() < GROUP_CHANCE:
                # gaseste vecini apropiati si se misca catre centrul lor
                neighbors = [a for a in agents if a is not self and self.pos.distance_to(a.pos) < 70]
                if neighbors:
                    center = sum((a.pos for a in neighbors), pygame.math.Vector2(0,0)) / len(neighbors)
                    dir_to_center = (center - self.pos)
                    if dir_to_center.length() > 0:
                        self.vel += dir_to_center.normalize() * GROUP_FORCE

            # mic jitter random ca miscarea sa nu fie perfect liniara
            jitter = pygame.math.Vector2(random.uniform(-0.4,0.4), random.uniform(-0.4,0.4))
            self.vel += jitter * 0.05

            # limiteaza viteza
            if self.vel.length() > BASE_SPEED*1.6:
                self.vel.scale_to_length(BASE_SPEED*1.6)
            if self.vel.length() < 0.4:
                self.vel.scale_to_length(0.4)

            # actualizeaza pozitia
            self.pos += self.vel

        # limite pentru a nu iesi din zona de simulare
        if self.pos.x < 2:
            self.pos.x = 2
            self.vel.x *= -0.8
        if self.pos.x > SIM_W - 2:
            self.pos.x = SIM_W - 2
            self.vel.x *= -0.8
        if self.pos.y < 2:
            self.pos.y = 2
            self.vel.y *= -0.8
        if self.pos.y > SIM_H - 2:
            self.pos.y = SIM_H - 2
            self.vel.y *= -0.8

        # update timer infectie
        if self.state == "I":
            self.infected_timer += dt

    def try_recover_or_die(self):
        # verificam daca agentul se poate recupera sau moare
        global recovery_success_prob, mortality_on_failure
        if random.random() < recovery_success_prob:
            self.state = "R"
            self.infected_timer = 0.0
            self.contact_time.clear()
            self.quarantined = False
            return "R"
        else:
            if mortality_on_failure:
                self.state = "D"
                self.infected_timer = 0.0
                self.contact_time.clear()
                self.quarantined = False
                return "D"
            else:
                self.infected_timer = 0.0
                return "I"

    def draw(self, surf):
        # alege culoarea in functie de stare
        if self.state == "S":
            col = SUSC_COLOR
            r = 4
        elif self.state == "I":
            col = INF_COLOR
            r = 5
        elif self.state == "R":
            col = REC_COLOR
            r = 4
        else:
            col = DEAD_COLOR
            r = 4
        # deseneaza cerc
        pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), r)
# ---------------- SIMULATIE ----------------
# cream toti agentii
agents = [Agent() for _ in range(N_AGENTS)]

# alegem random cativa initial infectati
for a in random.sample(agents, INIT_INFECTED):
    a.state = "I"
    a.infected_timer = 0.0

# functie pentru vaccinare initiala conform ratei de decizie si succes
def apply_initial_vaccination():
    global vaccination_decision_rate, vaccination_success_prob
    for a in agents:
        if a.state == "S" and random.random() < vaccination_decision_rate:
            if random.random() < vaccination_success_prob:
                a.state = "R"  # agentul devine imun

apply_initial_vaccination()

# ---------------- ISTORIC ----------------
# clasa care tine evidenta numarului de S, I, R, D pentru grafice
class History:
    def __init__(self):
        self.t = []  # timp
        self.s = []  # susceptibili
        self.i = []  # infectati
        self.r = []  # recuperati
        self.d = []  # morti
        self.frame = 0

    def log(self):
        # logam doar la fiecare history_step_interval cadre ca sa nu fie prea mare lista
        if self.frame % history_step_interval == 0:
            self.t.append(self.frame / FPS)
            self.s.append(sum(1 for a in agents if a.state == "S"))
            self.i.append(sum(1 for a in agents if a.state == "I"))
            self.r.append(sum(1 for a in agents if a.state == "R"))
            self.d.append(sum(1 for a in agents if a.state == "D"))
        self.frame += 1

history = History()

# flaguri pentru pauza si rulare
paused = False
running = True

# ---------------- SCENARII RAPIDE ----------------
def set_scenario_all_die():
    global recovery_success_prob, mortality_on_failure
    recovery_success_prob = 0.0
    mortality_on_failure = True

def set_scenario_some_survive():
    global recovery_success_prob, mortality_on_failure
    recovery_success_prob = 0.65
    mortality_on_failure = True

# setam un scenariu default unde unii supravietuiesc
set_scenario_some_survive()

# ---------------- VACCINARE RAPIDA ----------------
# vaccinam un procent din susceptibili instant
def vaccinate_fraction(frac):
    susc = [a for a in agents if a.state == "S"]
    n = int(len(susc) * frac)
    for a in random.sample(susc, n):
        if random.random() < vaccination_success_prob:
            a.state = "R"

# ---------------- LOOP PRINCIPAL ----------------
frame = 0
while running:
    dt = clock.get_time() / 1000.0 if clock.get_time() > 0 else 1.0 / FPS

    # ---------------- EVENIMENTE ----------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_SPACE:
                paused = not paused  # pauza/resume
            elif event.key == pygame.K_UP:
                infection_prob_per_sec = min(1.0, infection_prob_per_sec + 0.02)
            elif event.key == pygame.K_DOWN:
                infection_prob_per_sec = max(0.0, infection_prob_per_sec - 0.02)
            elif event.key == pygame.K_RIGHT:
                recovery_success_prob = min(1.0, recovery_success_prob + 0.05)
            elif event.key == pygame.K_LEFT:
                recovery_success_prob = max(0.0, recovery_success_prob - 0.05)
            elif event.key == pygame.K_t:
                recovery_time = max(0.5, recovery_time - 1.0)
            elif event.key == pygame.K_g:
                recovery_time = min(60.0, recovery_time + 1.0)
            elif event.key == pygame.K_q:
                quarantine_enabled = not quarantine_enabled

    if not paused:
        # ---------------- UPDATE AGENTI ----------------
        for a in agents:
            a.update(dt, agents)

        # ---------------- INFECTIE ----------------
        # fiecare susceptibil verifica vecinii infectati
        for s in [a for a in agents if a.state == "S"]:
            # stergem contactele cu cei care nu mai sunt in raza
            keys_to_del = [inf_agent for inf_agent in s.contact_time
                           if s.pos.distance_to(inf_agent.pos) > infection_radius]
            for k in keys_to_del:
                del s.contact_time[k]

            # gasim infectati in apropiere
            near_infected = [inf for inf in agents if inf.state == "I"
                             and s.pos.distance_to(inf.pos) <= infection_radius]
            for inf in near_infected:
                s.contact_time.setdefault(inf, 0.0)
                s.contact_time[inf] += dt

                # calculam probabilitatea infectarii instant
                base = infection_prob_per_sec
                if random.random() < 1 - (1 - base) ** dt:
                    s.state = "I"
                    s.infected_timer = 0.0
                    s.contact_time.clear()
                    break

        # ---------------- RECUPERARE / MOARTE ----------------
        for inf in [a for a in agents if a.state == "I"]:
            # daca e in zona de carantina, izoleaza
            if quarantine_enabled and quarantine_rect.collidepoint(int(inf.pos.x), int(inf.pos.y)):
                inf.quarantined = True
            if not quarantine_enabled:
                inf.quarantined = False

            # daca timpul de infectie e peste recovery_time, incercam recuperarea
            if inf.infected_timer >= recovery_time:
                inf.try_recover_or_die()

    # ---------------- RENDERING ----------------
    screen.fill(BG)
    pygame.draw.rect(screen, (30, 30, 40), (0, 0, SIM_W, SIM_H))

    # zona de carantina
    if quarantine_enabled:
        s = pygame.Surface((quarantine_rect.width, quarantine_rect.height), pygame.SRCALPHA)
        s.fill(QUAR_COLOR)
        screen.blit(s, (quarantine_rect.x, quarantine_rect.y))
        pygame.draw.rect(screen, (120, 120, 170), quarantine_rect, 1)
        screen.blit(FONT.render("Quarantine", True, TEXT), (quarantine_rect.x + 6, quarantine_rect.y + 6))

    # desenam toti agentii
    for a in agents:
        a.draw(screen)

    # panou UI lateral
    panel_x = SIM_W + 8
    pygame.draw.rect(screen, UI_BG, (panel_x - 6, 6, WIDTH - panel_x - 2, HEIGHT - 12))
    x, y = panel_x, 12
    screen.blit(TITLE.render("SIR Minimalist Controls", True, (255,255,255)), (x,y))
    y += 28
    screen.blit(FONT.render(f"UP/DOWN  : infection_prob_per_sec = {infection_prob_per_sec:.3f}", True, TEXT), (x,y)); y+=18
    screen.blit(FONT.render(f"LEFT/RIGHT: recovery_success_prob = {recovery_success_prob:.2f}", True, TEXT), (x,y)); y+=18
    screen.blit(FONT.render(f"T / G    : recovery_time (s) = {recovery_time:.1f}", True, TEXT), (x,y)); y+=18
    screen.blit(FONT.render(f"Q        : quarantine ON={quarantine_enabled}", True, TEXT), (x,y)); y+=18

    # afisam numarul de agenti pe stari
    y += 6
    s_ct = sum(1 for a in agents if a.state == "S")
    i_ct = sum(1 for a in agents if a.state == "I")
    r_ct = sum(1 for a in agents if a.state == "R")
    d_ct = sum(1 for a in agents if a.state == "D")
    screen.blit(FONT.render(f"Susceptible: {s_ct}", True, SUSC_COLOR), (x,y)); y+=18
    screen.blit(FONT.render(f"Infected   : {i_ct}", True, INF_COLOR), (x,y)); y+=18
    screen.blit(FONT.render(f"Recovered  : {r_ct}", True, REC_COLOR), (x,y)); y+=18
    screen.blit(FONT.render(f"Dead       : {d_ct}", True, DEAD_COLOR), (x,y)); y+=18

    pygame.display.flip()

    history.log()
    frame += 1
    clock.tick(FPS)

# ---------------- EXIT SI GRAFICE ----------------
pygame.quit()

if history.t:
    # plot SIR in timp
    plt.figure(figsize=(10,5))
    plt.plot(history.t, history.s, label='Susceptible', color=(0.2,0.7,1.0))
    plt.plot(history.t, history.i, label='Infected', color=(0.9,0.2,0.2))
    plt.plot(history.t, history.r, label='Recovered', color=(0.3,0.9,0.3))
    plt.plot(history.t, history.d, label='Dead', color=(0.45,0.45,0.45))
    plt.xlabel("Time (s)")
    plt.ylabel("Count")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.title("SIR Simulation over time")
    plt.tight_layout()

    # calculam rata de infectare aproximativa
    import numpy as np
    times = np.array(history.t)
    infected = np.array(history.i)
    if len(times) > 2:
        dt = np.diff(times)
        di = np.diff(infected)
        rate = di/dt
        plt.figure(figsize=(10,3))
        plt.plot(times[1:], rate, label='dI/dt (approx)', color='orange')
        plt.axhline(0, color='black', linewidth=0.4)
        plt.xlabel("Time (s)")
        plt.ylabel("New infected / s")
        plt.title("Approx Infection Rate")
        plt.grid(alpha=0.25)
        plt.tight_layout()

    plt.show()
else:
    print("No history recorded.")
