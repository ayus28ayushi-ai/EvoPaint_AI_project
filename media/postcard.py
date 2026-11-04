"""Simple postcard generator (1080 x 1920)."""

from __future__ import annotations
from typing import Any
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920


def create_postcard(
    record: dict[str, Any],
    target_img: Image.Image,
    result_images: dict[int, Image.Image],
    winner_panel: int | None = None,
) -> Image.Image:
    """Build a basic postcard from a run record + images."""
    img = Image.new("RGB", (W, H), (30, 30, 40))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    # Title
    draw.text((40, 40), "Evolving an Image", fill=(220, 220, 255), font=font)
    draw.text((40, 70), str(record.get("created_at", ""))[:16], fill=(180, 180, 180), font=font)

    # Images
    size = 400
    target = target_img.convert("RGB").resize((size, size))
    img.paste(target, (40, 120))

    if winner_panel is not None and winner_panel in result_images:
        best = result_images[winner_panel]
    elif result_images:
        best = next(iter(result_images.values()))
    else:
        best = target_img
    result = best.convert("RGB").resize((size, size))
    img.paste(result, (40 + size + 40, 120))

    draw.text((40, 540), "Target", fill=(200, 200, 200), font=font)
    draw.text((40 + size + 40, 540), "Best Result", fill=(200, 200, 200), font=font)

    # Best score
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

    draw.text((40, 600), f"Top: {best_name}  {best_sim:.1f}%", fill=(255, 220, 100), font=font)

    # Basic info
    theme = record.get("config", {}).get("theme_id", "?")
    seed = record.get("config", {}).get("seed", "?")
    draw.text((40, 650), f"Theme: {theme}   Seed: {seed}", fill=(180, 180, 180), font=font)

    # Awards
    y = 700
    for award in (record.get("awards") or {}):
        draw.text((40, y), f"- {award}", fill=(180, 220, 180), font=font)
        y += 25

    draw.text((40, H - 40), "Evolving an Image - AI with Python", fill=(150, 150, 150), font=font)
    return img