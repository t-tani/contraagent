"""Make screenshots small, losslessly: every pixel stays as captured.

    uv run --with pyoxipng --with pillow python web/scripts/optimize_images.py --webp A.png ... --png B.png ...

Each file after `--png` is optimized in place (oxipng); each after `--webp` becomes a
lossless WebP file beside it (`A.webp`), and the PNG is removed. `screenshots.mjs`
calls it after a capture.
"""

import sys
from pathlib import Path

import oxipng  # pyright: ignore[reportMissingImports]  # pyoxipng, given by `uv run --with`
from PIL import Image  # pyright: ignore[reportMissingImports]  # given by `uv run --with`


def to_webp(path: Path) -> Path:
    out = path.with_suffix(".webp")
    with Image.open(path) as im:
        im.save(out, lossless=True, quality=100, method=6)
    path.unlink()
    return out


def main(argv: list[str]) -> None:
    mode = "--png"
    for arg in argv:
        if arg in ("--png", "--webp"):
            mode = arg
            continue
        path = Path(arg)
        before = path.stat().st_size
        if mode == "--png":
            oxipng.optimize(path, level=4, strip=oxipng.StripChunks.safe())
        else:
            path = to_webp(path)
        with Image.open(path) as im:
            size = f"{im.width}x{im.height}"
        print(f"{path.name}: {size}, {before // 1024} KiB -> {path.stat().st_size // 1024} KiB")  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1:])
