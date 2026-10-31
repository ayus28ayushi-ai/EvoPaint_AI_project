from __future__ import annotations
import json, shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from PIL import Image

GALLERY_ROOT = Path("gallery")
UPLOADS_ROOT = Path("uploads")


def make_run_folder_name(seed: int) -> str:
    return f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_{seed}"


def save_run_folder(
    run_id: str,
    record_data: dict[str, Any],
    target_img: Image.Image,
    result_images: dict[int, Image.Image],
    shape_dicts: dict[int, dict] | None = None,
    history_csvs: dict[int, str] | None = None,
    timelapse_gifs: dict[int, Path] | None = None,
    combined_gif: Path | None = None,
    postcard_img: Image.Image | None = None,
) -> Path:
    """Write one complete gallery entry. Returns the folder path."""
    GALLERY_ROOT.mkdir(parents=True, exist_ok=True)
    folder = GALLERY_ROOT / run_id
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "record.json").write_text(json.dumps(record_data, indent=2))

    target_img.convert("RGB").resize((512, 512)).save(folder / "target.png")

    for i, im in result_images.items():
        im.convert("RGB").resize((512, 512)).save(folder / f"result_{i}.png")
        if shape_dicts and i in shape_dicts:
            (folder / f"shapes_{i}.json").write_text(json.dumps(shape_dicts[i], indent=2))

    if history_csvs:
        for i, csv in history_csvs.items():
            (folder / f"history_{i}.csv").write_text(csv)

    if timelapse_gifs:
        for i, p in timelapse_gifs.items():
            if p.exists():
                shutil.copy(p, folder / f"timelapse_{i}.gif")
    if combined_gif and combined_gif.exists():
        shutil.copy(combined_gif, folder / "timelapse_combined.gif")

    if postcard_img:
        postcard_img.save(folder / "postcard.png")

    # thumbnail
    src = next(iter(result_images.values()), target_img)
    src.convert("RGB").resize((160, 160)).save(folder / "thumb.png")
    return folder


def list_runs() -> list[dict[str, Any]]:
    """Return run summaries, newest first. Skip damaged entries."""
    GALLERY_ROOT.mkdir(parents=True, exist_ok=True)
    runs = []
    for folder in sorted(GALLERY_ROOT.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        try:
            data = json.loads((folder / "record.json").read_text())
            runs.append({
                "run_id": folder.name,
                "folder": folder,
                "thumb": folder / "thumb.png" if (folder / "thumb.png").exists() else None,
                "created": data.get("created_at", folder.name),
                "theme_id": data.get("config", {}).get("theme_id", "full_color"),
            })
        except Exception:
            continue
    return runs


def load_run(run_id: str) -> dict[str, Any] | None:
    path = GALLERY_ROOT / run_id / "record.json"
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


def delete_run(run_id: str) -> bool:
    folder = GALLERY_ROOT / run_id
    if folder.exists():
        shutil.rmtree(folder)
        return True
    return False


def get_run_folder(run_id: str) -> Path | None:
    folder = GALLERY_ROOT / run_id
    return folder if folder.exists() else None