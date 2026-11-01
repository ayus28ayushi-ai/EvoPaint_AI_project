"""Pure layout maths (no Pygame): where every region of the screen goes.

Everything returns plain (x, y, width, height) tuples so it can be unit-tested without a
window. Screens convert them to pygame.Rect. The window is a fixed 1280 x 800 canvas
(Pygame scales it for us), which keeps the layout simple and predictable.
"""
from __future__ import annotations

WINDOW_SIZE = (1280, 800)
MARGIN = 12
TOP_BAR_H = 56
SIDEBAR_W = 410
LEADERBOARD_H = 210
HELP_H = 120


def run_regions(size=WINDOW_SIZE) -> dict:
    """Regions of the run screen: top bar, panel grid, chart, and the right sidebar."""
    w, h = size
    body_y = TOP_BAR_H + MARGIN
    body_h = h - body_y - MARGIN
    main_w = w - SIDEBAR_W - 3 * MARGIN
    panels_h = int(body_h * 0.60)
    side_x = w - SIDEBAR_W - MARGIN
    return {
        "top_bar": (0, 0, w, TOP_BAR_H),
        "panels": (MARGIN, body_y, main_w, panels_h),
        "chart": (MARGIN, body_y + panels_h + MARGIN, main_w, body_h - panels_h - MARGIN),
        "leaderboard": (side_x, body_y, SIDEBAR_W, LEADERBOARD_H),
        "controls": (side_x, body_y + LEADERBOARD_H + MARGIN, SIDEBAR_W,
                     body_h - LEADERBOARD_H - HELP_H - 2 * MARGIN),
        "help": (side_x, body_y + body_h - HELP_H, SIDEBAR_W, HELP_H),
    }


def setup_regions(size=WINDOW_SIZE) -> dict:
    """Regions of the setup screen: global settings on the left, panel cards on the right."""
    w, h = size
    left_w = 344
    return {
        "left": (16, 16, left_w, h - 32),
        "cards": (16 + left_w + 16, 16, w - left_w - 48, h - 32),
    }


def panel_grid(count: int, region, gap: int = 10) -> list:
    """Split `region` into `count` (1 to 4) equal cells: 1 big, 2 side by side,
    3 in a row, 4 as a 2 x 2 grid."""
    x, y, w, h = region
    if count <= 1:
        return [(x, y, w, h)]
    if count in (2, 3):
        cell_w = (w - gap * (count - 1)) // count
        return [(x + i * (cell_w + gap), y, cell_w, h) for i in range(count)]
    cell_w, cell_h = (w - gap) // 2, (h - gap) // 2
    return [(x + (i % 2) * (cell_w + gap), y + (i // 2) * (cell_h + gap), cell_w, cell_h)
            for i in range(4)]


def panel_inner(rect, header: int = 30, footer: int = 24):
    """Inside one panel cell: (header_rect, square_image_rect, footer_rect)."""
    x, y, w, h = rect
    side = max(min(w, h - header - footer), 1)           # the painting is always square
    image = (x + (w - side) // 2, y + header, side, side)
    footer_rect = (x, y + header + side, w, footer)
    return (x, y, w, header), image, footer_rect


def rects_overlap(a, b) -> bool:
    """True when two (x, y, w, h) rectangles overlap."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def point_in(rect, pos) -> bool:
    x, y, w, h = rect
    return x <= pos[0] < x + w and y <= pos[1] < y + h
