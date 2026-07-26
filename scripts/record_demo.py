"""Capture a silent demo GIF of the signhook UI (Stripe then Twilio Sign & Send).

Prereq:
  docker compose up
  pip install playwright pillow imageio
  playwright install chromium

Usage:
  python scripts/record_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs"
FRAMES_DIR = OUT_DIR / "_demo_frames"
OUT_GIF = OUT_DIR / "demo.gif"
UI = "http://localhost:3000"


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
    images = []
    for path in frame_paths:
        img = Image.open(path).convert("P", palette=Image.ADAPTIVE, colors=128)
        images.append(img)
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

        frames += hold(page, "01_home", 1600)

        provider = page.locator("select").nth(0)
        provider.select_option(label="Stripe")
        page.wait_for_timeout(900)
        frames += hold(page, "02_stripe", 1000)

        page.locator('input[type="password"]').fill("whsec_smoke_stripe")
        frames += hold(page, "03_secret", 900)

        page.get_by_role("button", name="Sign & Send").click()
        page.wait_for_selector("text=Status 200", timeout=30_000)
        page.wait_for_selector("text=signature_verified")
        frames += hold(page, "04_stripe_ok", 2600)

        provider.select_option(label="Twilio")
        page.wait_for_timeout(1000)
        page.locator('input[type="password"]').fill("auth_smoke_twilio")
        frames += hold(page, "05_twilio", 800)

        page.get_by_role("button", name="Sign & Send").click()
        page.wait_for_selector("text=Status 200", timeout=30_000)
        frames += hold(page, "06_twilio_ok", 2200)

        browser.close()

    print(f"Assembling {len(frames)} frames -> {OUT_GIF}")
    assemble_gif(frames, OUT_GIF)
    kb = OUT_GIF.stat().st_size // 1024
    print(f"Wrote {OUT_GIF} ({kb} KB)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
