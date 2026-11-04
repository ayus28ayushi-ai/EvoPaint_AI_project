"""Simple postcard generator (1080 x 1920). Larger text, less empty space."""

from __future__ import annotations
from typing import Any
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920


def _font(size: int = 28):
    """Try a readable system font, fall back to default."""
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "FreeSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def create_postcard(
    record: dict[str, Any],
    target_img: Image.Image,
    result_images: dict[int, Image.Image],
    winner_panel: int | None = None,
) -> Image.Image:
    """Build a clear postcard from a run record + images."""
    img = Image.new("RGB", (W, H), (28, 28, 38))
    draw = ImageDraw.Draw(img)
    title_f = _font(42)
    label_f = _font(28)
    body_f = _font(26)
    small_f = _font(22)

    # Title
    draw.text((50, 40), "Evolving an Image", fill=(230, 230, 255), font=title_f)
    draw.text((50, 95), str(record.get("created_at", ""))[:19], fill=(160, 160, 180), font=small_f)

    # Images – larger, side by side
    size = 460
    gap = 40
    x0, y0 = 50, 150
    target = target_img.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    img.paste(target, (x0, y0))

    if winner_panel is not None and winner_panel in result_images:
        best = result_images[winner_panel]
    elif result_images:
        best = next(iter(result_images.values()))
    else:
        best = target_img
    result = best.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    img.paste(result, (x0 + size + gap, y0))

    draw.text((x0, y0 + size + 12), "Target", fill=(200, 200, 210), font=label_f)
    draw.text((x0 + size + gap, y0 + size + 12), "Best Result", fill=(200, 200, 210), font=label_f)

    # Score block
    best_sim = 0.0
    best_name = "?"
    outcomes = record.get("outcomes") or {}
    panels = record.get("config", {}).get("panels", [])
    for idx, out in outcomes.items():
        sim = out.get("final_similarity", 0) if isinstance(out, dict) else 0
        if sim > best_sim:
            best_sim = sim
            try:
                best_name = panels[int(idx)].get("algorithm_id", "?")
            except Exception:
                pass

    y = y0 + size + 70
    draw.text((50, y), f"Top: {best_name}   {best_sim:.1f}%", fill=(255, 220, 100), font=label_f)
    y += 45

    theme = record.get("config", {}).get("theme_id", "?")
    seed = record.get("config", {}).get("seed", "?")
    draw.text((50, y), f"Theme: {theme}    Seed: {seed}", fill=(180, 180, 195), font=body_f)
    y += 45

    # Awards
    awards = record.get("awards") or {}
    if awards:
        draw.text((50, y), "Awards:", fill=(180, 220, 180), font=body_f)
        y += 36
        for award in awards:
            draw.text((70, y), f"• {award}", fill=(180, 220, 180), font=body_f)
            y += 34

    # Footer
    draw.text((50, H - 55), "Evolving an Image  ·  AI with Python", fill=(140, 140, 155), font=small_f)
    return img