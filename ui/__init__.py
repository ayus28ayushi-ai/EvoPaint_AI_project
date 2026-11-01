"""M3's interface package. The only public entry point is run_app() (Contract 4)."""


def run_app(start_screen: str = "home", payload=None, use_fakes: bool = False) -> None:
    """Open the window and run until the user quits."""
    from ui.app import App          # imported here so importing `ui` never needs Pygame
    App(start_screen, payload, use_fakes).run()


__all__ = ["run_app"]
