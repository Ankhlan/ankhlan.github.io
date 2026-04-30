"""crop_photo.py — produce a face-prominent square crop of the about photo.

Reads E:/workshop/resume/photo.jpg (full original), crops to a face-centered
square, writes assets/img/photo.jpg in this repo.

The original is a portrait; the face is in roughly the upper-center. We crop
to a centered square then shift the crop window upward to land the face near
the visual center of the result.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SOURCE = Path("E:/workshop/resume/photo.jpg")
DEST = REPO / "assets" / "img" / "photo.jpg"

# Tunables — measured from the original photo (994x994 with subject in
# the lower-center). Adjust if the source photo is replaced.
TARGET_PX = 480          # output edge length (page renders at ~200px)
FACE_CX_FRAC = 0.54      # face center, x as fraction of width
FACE_CY_FRAC = 0.65      # face center, y as fraction of height
EDGE_FRAC = 0.62         # crop edge as fraction of the shorter side
                         #   smaller = tighter face crop


def main() -> int:
    img = Image.open(SOURCE)
    w, h = img.size
    print(f"source: {SOURCE.name}  {w}x{h}")

    edge = int(min(w, h) * EDGE_FRAC)
    cx = int(w * FACE_CX_FRAC)
    cy = int(h * FACE_CY_FRAC)

    left = cx - edge // 2
    top = cy - edge // 2
    right = left + edge
    bottom = top + edge

    # Clamp to image bounds without changing edge length.
    if left < 0:        right -= left;  left = 0
    if top < 0:         bottom -= top;  top = 0
    if right > w:       left -= (right - w);   right = w
    if bottom > h:      top -= (bottom - h);   bottom = h
    left = max(left, 0)
    top = max(top, 0)

    crop = img.crop((left, top, right, bottom))
    if crop.size[0] > TARGET_PX:
        crop = crop.resize((TARGET_PX, TARGET_PX), Image.LANCZOS)

    DEST.parent.mkdir(parents=True, exist_ok=True)
    crop.save(DEST, format="JPEG", quality=88, optimize=True, progressive=True)
    print(f"wrote:  {DEST.relative_to(REPO)}  {crop.size[0]}x{crop.size[1]}  "
          f"(crop box {left},{top} -> {right},{bottom})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
