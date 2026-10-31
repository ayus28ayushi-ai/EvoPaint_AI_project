from datetime import datetime
from pathlib import Path
from PIL import Image

from media.gallery import list_runs, save_run_folder
from media.postcard import create_postcard


def main() -> None:
    print("=== Media demo ===")
    target = Image.new("RGB", (512, 512), (30, 60, 100))
    r0 = Image.new("RGB", (512, 512), (80, 40, 120))
    r1 = Image.new("RGB", (512, 512), (20, 140, 90))

    record = {
        "run_id": "demo_run",
        "created_at": datetime.now().isoformat(),
        "contract_version": "1.0",
        "config": {"theme_id": "neon", "seed": 42, "panels": [{"algorithm_id": "hill_climbing"}, {"algorithm_id": "simulated_annealing"}]},
        "outcomes": {"0": {"final_similarity": 87.4}, "1": {"final_similarity": 92.1}},
        "awards": {"marathoner": 1, "sprinter": 0},
    }

    print("Creating postcard...")
    postcard = create_postcard(record, target, {0: r0, 1: r1}, winner_panel=1)
    Path("out").mkdir(exist_ok=True)
    postcard.save("out/demo_postcard.png")
    print("  -> out/demo_postcard.png")

    print("Saving gallery entry...")
    folder = save_run_folder(
        run_id="demo_2026-10-30_42",
        record_data=record,
        target_img=target,
        result_images={0: r0, 1: r1},
        postcard_img=postcard,
    )
    print(f"  -> {folder}")

    print("\nGallery runs:")
    for r in list_runs():
        print(f"  - {r['run_id']}")
    print("\nDone.")


if __name__ == "__main__":
    main()