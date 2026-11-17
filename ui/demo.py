import argparse

from ui import run_app
from ui.compat import PanelConfig, RunConfig, ShapeConfig


def quick_run_config() -> RunConfig:
    """A ready-made race of all four algorithms, for testing the run screen quickly."""
    names = ["hill_climbing", "stochastic_hc", "simulated_annealing", "iterative_hc"]
    return RunConfig(target_path="", theme_id="neon", shape_config=ShapeConfig(), seed=7,
                     max_evaluations=60000,
                     panels=[PanelConfig(algorithm_id=n, speed=2500.0) for n in names])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the UI with fake backends")
    parser.add_argument("--screen", default="home", choices=["home", "setup", "run"])
    args = parser.parse_args()
    payload = {"run_config": quick_run_config()} if args.screen == "run" else None
    run_app(args.screen, payload, use_fakes=True)
