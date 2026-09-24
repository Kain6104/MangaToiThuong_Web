#!/usr/bin/env python3
"""Report alpha bounds for every frame of an animated WebP."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image


def main() -> None:
    path = Path(sys.argv[1])
    rows = []
    with Image.open(path) as image:
        width, height = image.size
        for index in range(getattr(image, "n_frames", 1)):
            image.seek(index)
            alpha = image.convert("RGBA").getchannel("A")
            bbox = alpha.getbbox()
            rows.append(
                {
                    "frame": index,
                    "bbox": list(bbox) if bbox else None,
                    "coverage": 0 if not bbox else round(((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / (width * height), 4),
                }
            )
    print(json.dumps({"path": str(path), "size": [width, height], "frames": rows}, indent=2))


if __name__ == "__main__":
    main()
