"""Stand-ins for everyone else's code, so M3 can build and demo the whole UI alone.

None of this is shipped logic: it only imitates the contract (Section 6) closely enough
that the real session, engine and media modules can replace it without UI changes.
Uses Pillow and NumPy only (no Pygame), so it is also usable from tests.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

from PIL import Image, ImageDraw

from ui.compat import ActionSpec, ParamSpec, get, make_command  # noqa: F401  (make_command re-used by demos)

SHAPES = [("circle", "Circle"), ("ellipse", "Ellipse"), ("triangle", "Triangle"),
          ("rectangle", "Rectangle"), ("rotated_rectangle", "Rotated rectangle"),
          ("pentagon", "Pentagon"), ("line", "Line")]


# ------------------------------------------------------------------ algorithm catalogue
@dataclass
class AlgorithmInfo:
    id: str
    display_name: str
    description: str
    param_specs: list = field(default_factory=list)
    action_specs: list = field(default_factory=list)


def _step():
    return ParamSpec("step_scale", "Step size", "float", 0.01, 1.0, 0.3, 0.01, "log", "algorithm",
                     "How big each random change is.")


PAINTING_SPECS = [
    ParamSpec("shape_limit", "Shape limit", "int", 10, 1000, 300, 10, "linear", "painting",
              "Maximum number of shapes."),
    ParamSpec("max_shape_size", "Max shape size", "float", 0.05, 0.8, 0.5, 0.01, "linear",
              "painting", "Largest allowed shape."),
    ParamSpec("informed_colors", "Informed colors", "bool", 0, 1, 1, 1, "linear", "painting",
              "New shapes copy the target color at their position."),
]


def fake_list_algorithms() -> list:
    return [
        AlgorithmInfo("hill_climbing", "Hill Climbing", "Keeps a change only if it helps.", [_step()]),
        AlgorithmInfo("stochastic_hc", "Stochastic Hill Climbing", "Tries a batch, picks a random improver.",
                      [_step(), ParamSpec("batch_size", "Batch size", "int", 2, 20, 5, 1, "linear", "algorithm",
                                          "Neighbors tried per step.")]),
        AlgorithmInfo("simulated_annealing", "Simulated Annealing", "Accepts worse moves while hot.",
                      [_step(),
                       ParamSpec("start_temperature_scale", "Start temperature", "float", 0.1, 5.0, 1.0, 0.1,
                                 "log", "algorithm", "Multiplier on the calibrated start temperature."),
                       ParamSpec("cooling_rate", "Cooling rate", "float", 0.9990, 0.99999, 0.9995, 0.00001,
                                 "log", "algorithm", "Closer to 1 cools slower.")],
                      [ActionSpec("reheat", "Reheat", "Raise the temperature again.")]),
        AlgorithmInfo("iterative_hc", "Iterative Hill Climbing", "Hill climbing with random restarts.",
                      [_step(), ParamSpec("restart_after", "Restart after", "int", 50, 5000, 500, 50,
                                          "linear", "algorithm",
                                          "Evaluations without improvement before a restart.")],
                      [ActionSpec("restart", "Restart", "Force a restart now.")]),
    ]


def fake_list_shape_types() -> list:
    return list(SHAPES)


_SWATCHES = {
    "full_color": [(231, 76, 60), (241, 196, 15), (46, 204, 113), (52, 152, 219), (155, 89, 182)],
    "black_white": [(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)],
    "sepia": [(59, 42, 26), (112, 80, 48), (176, 138, 92), (240, 224, 190)],
    "neon": [(0, 240, 255), (255, 46, 151), (57, 255, 20), (255, 230, 0), (140, 60, 255)],
    "pastel": [(255, 179, 186), (255, 223, 186), (186, 255, 201), (186, 225, 255), (218, 186, 255)],
    "ocean": [(4, 30, 60), (20, 90, 140), (46, 196, 182), (200, 245, 250)],
    "sunset": [(60, 20, 90), (200, 40, 80), (255, 122, 69), (255, 209, 102)],
    "retro_8bit": [(26, 28, 44), (93, 39, 93), (177, 62, 83), (239, 125, 87), (255, 205, 117), (167, 240, 112)],
}


def fake_palette_swatches(theme_id: str) -> list:
    return list(_SWATCHES.get(theme_id, _SWATCHES["full_color"]))


# ------------------------------------------------------------------ null media
class _Null:
    """Accepts any method call and does nothing (stand-in for audio and effects)."""
    def __getattr__(self, name):
        return lambda *a, **k: None


def fake_get_audio():
    return _Null()


def fake_get_effects():
    return _Null()


def fake_new_recorder(session):
    return _Null()


def fake_save_run(record, recorder) -> str:
    return get(record, "run_id", "fake-run")


# ------------------------------------------------------------------ fake session
class FakeSession:
    """Plays believable curves for 1 to 4 panels and obeys every Command (Contract 6.3)."""

    # (curve speed as a fraction of the run budget, final ceiling) so the algorithms look
    # different in the demo while still finishing inside the budget
    _CURVES = {"hill_climbing": (0.11, 90.0), "stochastic_hc": (0.08, 91.5),
               "simulated_annealing": (0.15, 96.5), "iterative_hc": (0.12, 93.0)}

    def __init__(self, run_config):
        self.config = run_config
        self._algos = {a.id: a for a in fake_list_algorithms()}
        self._rng = random.Random(get(run_config, "seed", 1))
        self._elapsed = 0.0
        self._status = "running"
        self._events: list = []
        self._leader = None
        self._last_ranks: dict = {}
        self.panels = []
        for index, pc in enumerate(get(run_config, "panels", [])):
            algo = self._algos.get(get(pc, "algorithm_id"), fake_list_algorithms()[0])
            params = {s.name: s.default for s in list(algo.param_specs) + PAINTING_SPECS}
            params.update(get(pc, "algorithm_params", {}) or {})
            params.update(get(pc, "painting_params", {}) or {})
            tau_fraction, ceiling = self._CURVES.get(algo.id, (0.1, 90.0))
            tau = tau_fraction * get(run_config, "max_evaluations", 200000)
            self.panels.append(SimpleNamespace(
                index=index, algo=algo, params=params, speed=float(get(pc, "speed", 1000)),
                evals=0.0, penalty=0.0, similarity=0.0, best=0.0, tau=tau, ceiling=ceiling,
                accepted=0, proposed=0, worse=0, finished=False, history=[], next_point=0,
                milestones={}, injections=[], circles=[], rng=random.Random(100 + index)))

    # --- time ---------------------------------------------------------------------
    def tick(self, seconds: float) -> None:
        if self._status != "running":
            return
        self._elapsed += seconds
        budget = get(self.config, "max_evaluations", 200000)
        for p in self.panels:
            if p.finished:
                continue
            gained = p.speed * seconds
            p.evals = min(p.evals + gained, budget)
            p.proposed += int(gained)
            p.accepted += int(gained * 0.2)
            step = max(float(p.params.get("step_scale", 0.3)), 0.01)
            progress = 1 - math.exp(-p.evals * (0.7 + step) / p.tau)
            p.penalty *= 0.9993 ** max(gained, 1)                      # injected shapes get cleaned up
            wobble = 0.0
            if p.algo.id == "simulated_annealing":                     # annealing visibly wiggles when hot
                heat = 0.9995 ** (p.evals / 40) * 6 * float(p.params.get("start_temperature_scale", 1))
                wobble = p.rng.random() * heat
                p.worse += int(gained * 0.04 * min(heat / 3, 1))
            p.similarity = max(0.0, p.ceiling * progress - p.penalty - wobble)
            p.best = max(p.best, p.similarity)
            if p.evals >= p.next_point:                                # record a history point
                p.history.append(self._point(p))
                p.next_point = p.evals + max(150, budget / 900)
            for level in (80, 90, 95):
                if p.best >= level and level not in p.milestones:
                    p.milestones[level] = (int(p.evals), self._elapsed)
                    self._event("milestone_reached", p.index, level=level)
            if p.evals >= budget:
                p.finished = True
                self._event("panel_finished", p.index, reason="budget")
        self._update_leader()
        if all(p.finished for p in self.panels):
            self._status = "finished"
            self._event("run_finished", None, reason="budget")

    def _point(self, p) -> dict:
        return {"evaluations": int(p.evals), "elapsed_seconds": self._elapsed,
                "similarity": p.similarity, "best_similarity": p.best,
                "cost": (255 * (1 - p.similarity / 100)) ** 2,
                "acceptance_rate": 0.2, "extras": {}}

    def _event(self, kind: str, panel, **payload) -> None:
        ev = {"type": kind, "panel": panel, "evaluations": int(self.panels[panel].evals) if panel is not None else 0,
              "elapsed_seconds": self._elapsed}
        ev.update(payload)
        self._events.append(ev)

    def _update_leader(self) -> None:
        board = self.leaderboard()
        if board and board[0]["panel_index"] != self._leader and any(p.best > 5 for p in self.panels):
            if self._leader is not None:
                self._event("leader_changed", board[0]["panel_index"], old_panel=self._leader,
                            new_panel=board[0]["panel_index"])
            self._leader = board[0]["panel_index"]

    # --- commands -----------------------------------------------------------------
    def send(self, command) -> None:
        kind = get(command, "type")
        payload = get(command, "payload", {}) or {}
        if kind == "pause" and self._status == "running":
            self._status = "paused"
        elif kind == "resume" and self._status == "paused":
            self._status = "running"
        elif kind == "finish":
            self._status = "finished"
            self._event("run_finished", None, reason="user")
        elif kind == "set_speed":
            self.panels[payload["panel"]].speed = float(payload["speed"])
        elif kind == "set_param":
            p = self.panels[payload["panel"]]
            old = p.params.get(payload["name"])
            p.params[payload["name"]] = payload["value"]
            self._event("param_changed", p.index, name=payload["name"], old_value=old, new_value=payload["value"])
        elif kind == "trigger_action":
            p = self.panels[payload["panel"]]
            if payload["action"] == "reheat":
                p.worse += 50
            elif payload["action"] == "restart":
                p.penalty += 10
                p.similarity = max(0.0, p.similarity - 10)
        elif kind == "inject":
            targets = payload.get("panels", "all")
            for p in self.panels:
                if targets == "all" or p.index in targets:
                    before = p.similarity
                    p.penalty += 10 + p.rng.random() * 4
                    p.similarity = max(0.0, p.similarity - p.penalty)
                    p.best = p.similarity                              # best restarts after injection
                    self._event("shapes_injected", p.index, count=payload.get("count", 50),
                                cost_before=before, cost_after=p.similarity)

    # --- queries ------------------------------------------------------------------
    def snapshot(self, panel: int):
        p = self.panels[panel]
        return SimpleNamespace(panel_index=panel, algorithm_id=p.algo.id, iteration=int(p.evals),
                               evaluations=int(p.evals), similarity=p.similarity, best_similarity=p.best,
                               cost=(255 * (1 - p.similarity / 100)) ** 2, proposed_total=p.proposed,
                               accepted_total=p.accepted, worse_accepted_total=p.worse,
                               extras={"temperature": 0.9995 ** (p.evals / 40)} if p.algo.id == "simulated_annealing" else {},
                               elapsed_seconds=self._elapsed)

    def history(self, panel: int, max_points: int = 2000) -> list:
        return self.panels[panel].history[-max_points:]

    def leaderboard(self) -> list:
        order = sorted(self.panels, key=lambda p: (-p.best, p.index))
        rows = []
        for rank, p in enumerate(order, start=1):
            previous = self._last_ranks.get(p.index, rank)
            rows.append({"rank": rank, "panel_index": p.index, "algorithm_id": p.algo.id,
                         "best_similarity": p.best, "evaluations": int(p.evals),
                         "rank_change": previous - rank, "finished": p.finished,
                         "milestones": dict(p.milestones)})
        self._last_ranks = {r["panel_index"]: r["rank"] for r in rows}
        return rows

    def poll_events(self) -> list:
        events, self._events = self._events, []
        return events

    def panel_info(self, panel: int) -> dict:
        p = self.panels[panel]
        return {"algorithm_id": p.algo.id, "param_values": dict(p.params),
                "param_specs": list(p.algo.param_specs) + PAINTING_SPECS,
                "action_specs": list(p.algo.action_specs), "speed": p.speed, "throttled": False}

    def status(self) -> str:
        return self._status

    def finish(self):
        self._status = "finished"
        return SimpleNamespace(run_id=time.strftime("%Y%m%d-%H%M%S") + f"-{get(self.config, 'seed', 0)}",
                               config=self.config)

    def render(self, panel: int, size) -> Image.Image:
        """Draw a progressively more detailed picture so the demo looks alive."""
        side = size if isinstance(size, int) else size[0]
        p = self.panels[panel]
        img = Image.new("RGB", (side, side), (235, 235, 235))
        draw = ImageDraw.Draw(img, "RGBA")
        target = lambda u, v: (int(255 * u), int(120 + 80 * math.sin(v * 3)), int(255 * (1 - v)))   # fake photo colors
        want = min(int(p.evals / 250), 300)
        while len(p.circles) < want:                                   # add circles over time, never remove
            p.circles.append((p.rng.random(), p.rng.random(), p.rng.random()))
        for u, v, r in p.circles:
            size_frac = 0.03 + 0.25 * r * (1 - len(p.circles) / 400)
            c = target(u, v)
            draw.ellipse([(u - size_frac) * side, (v - size_frac) * side,
                          (u + size_frac) * side, (v + size_frac) * side], fill=c + (170,))
        return img
