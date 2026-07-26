"""Capture a silent demo GIF: Use inbox → Sign & Send → PASS → Run checks.

Prereq: API + UI running (defaults localhost:3000 / API from NEXT_PUBLIC).

  backend\\.venv\\Scripts\\python scripts\\record_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
FRAMES_DIR = OUT_DIR / "_demo_frames"
OUT_GIF = OUT_DIR / "demo.gif"
UI = os.environ.get("DEMO_UI_URL", "http://localhost:3000").rstrip("/")


def shot(page, name: str) -> Path:
    path = FRAMES_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return path


def hold(page, prefix: str, ms: int, step: int = 400) -> list[Path]:
    files: list[Path] = []
    n = max(1, ms // step)
    for i in range(n):
        files.append(shot(page, f"{prefix}_{i:02d}"))
        page.wait_for_timeout(step)
    return files


def assemble_gif(frame_paths: list[Path], dest: Path, duration_ms: int = 350) -> None:
    images = [
        Image.open(path).convert("P", palette=Image.ADAPTIVE, colors=128)
        for path in frame_paths
    ]
    images[0].save(
        dest,
        save_all=True,
        append_images=images[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if FRAMES_DIR.exists():
        for f in FRAMES_DIR.iterdir():
            f.unlink()
    else:
        FRAMES_DIR.mkdir(parents=True)

    frames: list[Path] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        print(f"Opening {UI}")
        page.goto(UI, wait_until="networkidle", timeout=60_000)
        page.wait_for_selector("text=signhook")
        page.wait_for_function(
            """() => {
              const ta = document.querySelector('textarea');
              return ta && ta.value && ta.value.length > 40;
            }""",
            timeout=30_000,
        )

        frames += hold(page, "01_home", 1200)

        page.locator('input[type="password"]').fill("whsec_smoke_stripe")
        page.get_by_role("button", name="Use inbox").click()
        page.wait_for_timeout(600)
        frames += hold(page, "02_armed", 1000)

        page.get_by_role("button", name="Sign & Send").click()
        page.wait_for_selector("text=PASS", timeout=30_000)
        frames += hold(page, "03_pass", 2400)

        page.get_by_role("button", name="Run signature checks").click()
        page.wait_for_selector("text=Signature checks", timeout=60_000)
        page.wait_for_timeout(800)
        frames += hold(page, "04_checks", 2600)

        browser.close()

    print(f"Assembling {len(frames)} frames -> {OUT_GIF}")
    assemble_gif(frames, OUT_GIF)
    print(f"Wrote {OUT_GIF} ({OUT_GIF.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
