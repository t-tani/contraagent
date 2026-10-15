"""Make screenshots small, losslessly: every pixel stays as captured.

    uv run --with pyoxipng --with pillow python web/scripts/optimize_images.py \
        --stack OUT.png GAP PART.png PART.png ... --webp A.png ... --png B.png ...

`--stack OUT GAP PART...` puts the parts one under the other into OUT, GAP CSS px (at
device scale 2) of the first part's background colour between them, every pixel as
captured, and removes the parts;
it comes first and may repeat. Each file after `--png` is optimized in place (oxipng);
each after `--webp` becomes a lossless WebP file beside it (`A.webp`), and the PNG is
removed. `screenshots.mjs` calls it after a capture.
"""

import sys
from pathlib import Path

import oxipng  # pyright: ignore[reportMissingImports]  # pyoxipng, given by `uv run --with`
from PIL import Image  # pyright: ignore[reportMissingImports]  # given by `uv run --with`


def stack(out: Path, gap_css: int, parts: list[Path]) -> None:
    gap = 2 * gap_css  # the parts are captured at device scale 2
    images = [Image.open(p).convert("RGB") for p in parts]
    width = max(im.width for im in images)
    height = sum(im.height for im in images) + gap * (len(images) - 1)
    canvas = Image.new("RGB", (width, height), images[0].getpixel((1, 1)))
    y = 0
    for im in images:
        canvas.paste(im, (0, y))
        y += im.height + gap
    canvas.save(out)
    for p in parts:
        p.unlink()


def to_webp(path: Path) -> Path:
    out = path.with_suffix(".webp")
    with Image.open(path) as im:
        im.save(out, lossless=True, quality=100, method=6)
    path.unlink()
    return out


def main(argv: list[str]) -> None:
    mode, group = "--png", []
    for arg in [*argv, "--end"]:
        if arg.startswith("--"):
            if mode == "--stack" and group:
                stack(Path(group[0]), int(group[1]), [Path(p) for p in group[2:]])
            mode, group = arg, []
            continue
        if mode == "--stack":
            group.append(arg)
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
