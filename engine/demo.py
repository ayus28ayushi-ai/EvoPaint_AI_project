"""Run the engine alone (no Pygame, no other domain): hill climbing paints a target and saves a picture.

Usage: python -m engine.demo [image_path] [theme_id] [evaluations]
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from PIL import Image

from algorithms.hill_climbing import HillClimbing
from contracts.definitions import ShapeConfig
from engine import create_problem

log = logging.getLogger("engine.demo")


def main(argv: list | None = None) -> None:
    """Paint for N evaluations and save out/engine_demo.png (target | painting)."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    a = list(sys.argv[1:] if argv is None else argv)
    path = a[0] if a else "samples/images/circle_square.png"
    theme = a[1] if len(a) > 1 else "full_color"
    total = int(a[2]) if len(a) > 2 else 20000
    problem = create_problem(path, ShapeConfig(), theme, seed=1)
    algo, t0 = HillClimbing(problem, seed=1), time.perf_counter()
    for chunk in range(10):
        s = algo.advance(total // 10)
        log.info("evals %6d  shapes %3d  similarity %.2f%%  accepted %d", s.evaluations,
                 problem.shape_count(s.state), s.similarity, s.accepted_total)
    log.info("%.2f s, %.3f ms per evaluation", time.perf_counter() - t0, (time.perf_counter() - t0) / total * 1000)
    out = Path("out")
    out.mkdir(exist_ok=True)
    sheet = Image.new("RGB", (1024, 512))
    sheet.paste(problem.target_image(512), (0, 0))
    sheet.paste(problem.render(s.best_state, 512), (512, 0))
    sheet.save(out / "engine_demo.png")
    log.info("saved %s", out / "engine_demo.png")


if __name__ == "__main__":
    main()
