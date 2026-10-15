"""Optimize screenshots in place, losslessly: every pixel stays as captured.

    uv run --with pyoxipng python web/scripts/optimize_png.py FILE.png ...

`screenshots.mjs` calls it after a capture.
"""

import sys
from pathlib import Path

import oxipng  # pyright: ignore[reportMissingImports]  # pyoxipng, given by `uv run --with`


def main(names: list[str]) -> None:
    for name in names:
        path = Path(name)
        before = path.stat().st_size
        oxipng.optimize(path, level=4, strip=oxipng.StripChunks.safe())
        print(f"{path.name}: {before // 1024} KiB -> {path.stat().st_size // 1024} KiB")  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1:])
