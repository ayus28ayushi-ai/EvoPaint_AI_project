"""The 'stock market' chart: one rising line per panel plus a ticker with live changes."""
from __future__ import annotations

import math

import pygame

from ui import chart_math as cm
from ui.compat import get
from ui.theme import draw_panel, draw_text, fit_text


class StockChart:
    def __init__(self):
        self.mode = "similarity"          # or "error" (hotkey C)
        self.series: dict = {}            # panel index -> list of history points
        self.names: dict = {}             # panel index -> short label
        self.markers: list = []           # dicts: type, panel, evaluations, level
        self._pulse = 0.0                 # drives the glowing dot at the end of each line

    def toggle_mode(self) -> None:
        self.mode = "error" if self.mode == "similarity" else "similarity"

    def update(self, dt: float) -> None:
        self._pulse += dt

    # ------------------------------------------------------------------ drawing
    def draw(self, surface, rect, skin, fonts) -> None:
        rect = pygame.Rect(rect)
        draw_panel(surface, skin, rect)
        title = "Similarity to target (%)" if self.mode == "similarity" else "Error (lower is better)"
        draw_text(surface, fonts, title, (rect.x + 14, rect.y + 8), 16, skin.text, bold=True)
        draw_text(surface, fonts, "press C to switch", (rect.right - 12, rect.y + 10), 13, skin.text_dim, "topright")

        plot = pygame.Rect(rect.x + 58, rect.y + 34, rect.width - 58 - 170, rect.height - 34 - 26)
        thinned = {p: cm.thin(pts, max(plot.width // 2, 2)) for p, pts in self.series.items() if pts}
        if not thinned:
            draw_text(surface, fonts, "Waiting for data...", plot.center, 16, skin.text_dim, "center")
            return

        values = [cm.value_of(pt, self.mode) for pts in thinned.values() for pt in pts]
        log = cm.use_log(values, self.mode)
        y_rng = cm.y_range(values, self.mode)
        if log:
            y_rng = (max(min(v for v in values if v > 0), 1e-6), max(values))
        x_max = max(float(get(pts[-1], "evaluations", 1)) for pts in thinned.values())
        x_rng = (0.0, max(x_max, 1.0))

        self._draw_grid(surface, plot, y_rng, x_rng, log, skin, fonts)
        surface.set_clip(plot)                                   # keep lines inside the plot box
        for panel, pts in thinned.items():
            color = skin.line_colors[panel % len(skin.line_colors)]
            pixels = [cm.to_pixel(float(get(pt, "evaluations", 0)), cm.value_of(pt, self.mode),
                                  plot, x_rng, y_rng, log) for pt in pts]
            if len(pixels) >= 2:
                pygame.draw.lines(surface, color, False, pixels, 2)
            glow = 4 + int(2 * math.sin(self._pulse * 6))        # pulsing dot = "live"
            pygame.draw.circle(surface, color, pixels[-1], max(glow, 3))
        self._draw_markers(surface, plot, thinned, x_rng, y_rng, log, skin, fonts)
        surface.set_clip(None)
        self._draw_ticker(surface, rect, thinned, skin, fonts)

    def _draw_grid(self, surface, plot, y_rng, x_rng, log, skin, fonts) -> None:
        if log:
            lo_exp, hi_exp = math.floor(math.log10(y_rng[0])), math.ceil(math.log10(y_rng[1]))
            ticks = [10.0 ** e for e in range(lo_exp, hi_exp + 1)]
        else:
            ticks = cm.nice_ticks(y_rng[0], y_rng[1], 4)
        for tick in ticks:
            if not (y_rng[0] <= tick <= y_rng[1]):
                continue
            _, y = cm.to_pixel(0, tick, plot, x_rng, y_rng, log)
            pygame.draw.line(surface, skin.grid, (plot.x, y), (plot.right, y))
            draw_text(surface, fonts, cm.format_count(tick) if tick >= 1000 else f"{tick:g}",
                      (plot.x - 8, y), 12, skin.text_dim, "midright")
        for i in range(5):                                       # x labels: evaluations
            x = plot.x + plot.width * i // 4
            draw_text(surface, fonts, cm.format_count(x_rng[1] * i / 4), (x, plot.bottom + 6), 12,
                      skin.text_dim, "midtop")
        pygame.draw.rect(surface, skin.panel_border, plot, 1)

    def _draw_markers(self, surface, plot, thinned, x_rng, y_rng, log, skin, fonts) -> None:
        for m in self.markers[-40:]:                             # only the most recent markers
            x, _ = cm.to_pixel(float(m["evaluations"]), 0, plot, x_rng, y_rng, log)
            if m["type"] == "shapes_injected":                   # dashed vertical line
                for y in range(plot.y, plot.bottom, 8):
                    pygame.draw.line(surface, skin.bad, (x, y), (x, min(y + 4, plot.bottom)))
                draw_text(surface, fonts, "inject", (x + 3, plot.y + 2), 11, skin.bad)
            elif m["type"] == "milestone_reached" and m["panel"] in thinned:
                pts = thinned[m["panel"]]
                near = min(pts, key=lambda p: abs(float(get(p, "evaluations", 0)) - m["evaluations"]))
                _, y = cm.to_pixel(0, cm.value_of(near, self.mode), plot, x_rng, y_rng, log)
                color = skin.line_colors[m["panel"] % len(skin.line_colors)]
                pygame.draw.circle(surface, skin.panel, (x, y), 6)
                pygame.draw.circle(surface, color, (x, y), 6, 2)
                draw_text(surface, fonts, f"{m['level']}%", (x, y - 12), 11, color, "midbottom", bold=True)

    def _draw_ticker(self, surface, rect, thinned, skin, fonts) -> None:
        """Right-hand column: name, latest value and the change over the last few seconds."""
        x0, y = rect.right - 160, rect.y + 40
        for panel in sorted(thinned):
            pts = self.series[panel]
            value, delta = cm.ticker_change(pts, self.mode, 5.0)
            good = delta >= 0 if self.mode == "similarity" else delta <= 0
            color = skin.line_colors[panel % len(skin.line_colors)]
            pygame.draw.rect(surface, color, (x0, y + 2, 5, 34), border_radius=2)
            draw_text(surface, fonts, fit_text(fonts, self.names.get(panel, f"Panel {panel + 1}"), 13, 140),
                      (x0 + 12, y), 13, skin.text_dim)
            text = f"{value:.1f}%" if self.mode == "similarity" else cm.format_count(value)
            draw_text(surface, fonts, text, (x0 + 12, y + 14), 18, skin.text, bold=True)
            arrow_color = skin.good if good else skin.bad
            ax, ay = x0 + 100, y + 25
            up = delta >= 0
            tri = [(ax - 5, ay + 4), (ax + 5, ay + 4), (ax, ay - 5)] if up else [(ax - 5, ay - 4), (ax + 5, ay - 4), (ax, ay + 5)]
            pygame.draw.polygon(surface, arrow_color, tri)
            draw_text(surface, fonts, f"{delta:+.1f}" if self.mode == "similarity" else f"{delta:+.0f}",
                      (ax + 10, ay), 13, arrow_color, "midleft")
            y += 44
