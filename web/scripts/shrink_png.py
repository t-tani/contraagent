"""Shrink screenshots in place: half the device scale, then a 256-colour palette.

    uv run --with pillow python web/scripts/shrink_png.py FILE.png ...

`screenshots.mjs` calls it after a capture. A capture at device scale 2, scaled
down with a Lanczos filter, keeps text sharper than one taken at scale 1.
"""

import sys
from pathlib import Path

from PIL import Image

SCALE = 0.75  # of the captured size: 2x captures become 1.5x, crisp on a high-density screen


def shrink(path: Path) -> None:
    before = path.stat().st_size
    with Image.open(path) as im:
        rgb = im.convert("RGB")
    size = (round(rgb.width * SCALE), round(rgb.height * SCALE))
    small = rgb.resize(size, Image.Resampling.LANCZOS)
    small.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)
    print(f"{path.name}: {size[0]}x{size[1]}, {before // 1024} KiB -> {path.stat().st_size // 1024} KiB")  # noqa: T201


if __name__ == "__main__":
    for name in sys.argv[1:]:
        shrink(Path(name))
