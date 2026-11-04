from __future__ import annotations
from pathlib import Path
from typing import Any
from PIL import Image

from .gallery import make_run_folder_name, save_run_folder
from .postcard import create_postcard
from .timelapse import TimelapseRecorder


def save_run(record: Any, recorder: TimelapseRecorder | None = None) -> str:
    """Build GIFs and postcard, store everything. Returns run_id."""
    if hasattr(record, "to_dict"):
        data = record.to_dict()
    elif hasattr(record, "__dict__"):
        data = {
            "run_id": getattr(record, "run_id", None),
            "created_at": getattr(record, "created_at", ""),
            "contract_version": getattr(record, "contract_version", "1.0"),
            "config": getattr(record, "config", {}),
            "outcomes": getattr(record, "outcomes", {}),
            "awards": getattr(record, "awards", {}),
            "events": getattr(record, "events", []),
            "history": getattr(record, "history", {}),
        }
    else:
        data = dict(record)

    config = data.get("config", {})
    seed = config.get("seed", 0)
    run_id = data.get("run_id") or make_run_folder_name(seed)
    data["run_id"] = run_id

    # images
    target_img = Image.new("RGB", (512, 512), (40, 40, 60))
    result_images = {0: target_img.copy()}
    if hasattr(record, "images"):
        imgs = record.images
        if "target" in imgs:
            target_img = imgs["target"]
        for k, v in imgs.items():
            if k.startswith("result_"):
                try:
                    result_images[int(k.split("_")[1])] = v
                except Exception:
                    pass

    winner = (data.get("winners") or {}).get("best_final")
    postcard = create_postcard(data, target_img, result_images, winner)

    panel_gifs, combined = {}, None
    if recorder:
        panel_gifs, combined = recorder.build_gifs(Path("out") / "tmp_gifs")

    history_csvs = {}
    if hasattr(record, "history"):
        for pidx, points in (record.history or {}).items():
            lines = ["evaluations,similarity,cost"]
            for pt in (points or [])[:200]:
                lines.append(f"{getattr(pt,'evaluations',0)},{getattr(pt,'similarity',0)},{getattr(pt,'cost',0)}")
            history_csvs[int(pidx)] = "\n".join(lines)

    save_run_folder(
        run_id=run_id,
        record_data=data,
        target_img=target_img,
        result_images=result_images,
        shape_dicts=getattr(record, "shapes", None),
        history_csvs=history_csvs,
        timelapse_gifs=panel_gifs,
        combined_gif=combined,
        postcard_img=postcard,
    )
    return run_id