"""Regenerate original PNG diagrams inside this case, never runtime truth labels.

Rectangle coordinates are exclusive on right and bottom. This development-only
script owns synthetic artwork. Runtime reads the resulting PNG bytes only.
"""

from pathlib import Path

from PIL import Image


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / "src" / "vision_language" / "scenes"
    destination.mkdir(parents=True, exist_ok=True)
    red, green, blue, gray = (255, 0, 0), (0, 180, 0), (0, 0, 255), (128, 128, 128)
    clear = [((8, 8, 24, 24), red), ((40, 8, 56, 24), green), ((72, 40, 88, 56), blue)]
    scenes = {
        "clear": clear,
        "occluded": [*clear, ((14, 5, 18, 28), gray)],
        "repeated": [((8, 8, 24, 24), red), ((40, 8, 56, 24), red), ((72, 40, 88, 56), blue)],
        "empty": [],
        "swapped": [((16, 40, 32, 56), green), ((64, 8, 80, 24), red)],
    }
    for name, rectangles in scenes.items():
        image = Image.new("RGB", (96, 72), (255, 255, 255))
        for bounds, color in rectangles:
            image.paste(color, bounds)
        image.save(destination / f"{name}.png", format="PNG", optimize=False)
        image.close()
    print(f"Generated {len(scenes)} original RGB PNG scenes in {destination}")


if __name__ == "__main__":
    main()
