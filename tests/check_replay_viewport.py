"""Check captures taken at the same paused replay frame before and after stats hotkeys."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops


# The stats panels belong in this part of the right-hand HUD, above the minimap.
STATS_REGION = (0.74, 0.29, 0.98, 0.53)
MIN_STATS_CHANGE = 0.12
MAX_ROSTER_OFFSET = 0.015


def read_stats_region(path, expected_size):
    with Image.open(path) as image:
        if image.size != expected_size:
            raise ValueError(f"{path.name}: expected {expected_size}, got {image.size}")
        width, height = image.size
        left, top, right, bottom = STATS_REGION
        box = (round(left * width), round(top * height),
               round(right * width), round(bottom * height))
        return image.crop(box).convert("RGB").resize((96, 54))


def changed_fraction(before, after):
    difference = ImageChops.difference(before, after).convert("L")
    return sum(difference.histogram()[24:]) / (difference.width * difference.height)


def check_capture(directory, filename, case, expected_clock, expected_bans):
    frame = json.loads((directory / f"{filename}-base.json").read_text(encoding="utf-8"))
    if frame["clock"] != expected_clock:
        raise ValueError(f"{filename}: expected clock {expected_clock}, got {frame['clock']}")
    size = tuple(case["size"])
    width, _ = size
    roster = sorted(case["roster_centers_x"])
    # For this capture, rects must be mapped to screenshot pixels before comparison.
    # Allow either directly measured centers or receipts that use the same units.
    kda = case.get("kda_centers_x")
    if kda is None:
        bitmap_width = frame.get("canvas", [width])[0]
        kda = [(left + box_width / 2) * width / bitmap_width
               for left, _, box_width, _ in frame["kda"]]
    kda = sorted(kda)
    if len(roster) != 12 or any(not 0 <= x < width for x in roster):
        raise ValueError(f"{filename}: invalid roster anchors")
    failures = []
    if len(kda) != 12:
        failures.append(f"expected 12 K/D/A labels, got {len(kda)}")
    else:
        deviation = max(abs(actual - expected) for actual, expected in zip(kda, roster))
        spread = f"{sum(x < width / 2 for x in kda)}/{sum(x >= width / 2 for x in kda)}"
        print(f"  K/D/A left/right {spread}; max offset {deviation / width:.1%}")
        if deviation / width > MAX_ROSTER_OFFSET:
            failures.append("K/D/A is offset from the roster")
    if not case["right_team_visible"]:
        failures.append("right team name is missing")
    if case["right_bans_complete"] != expected_bans:
        failures.append(f"right BAN icons: {case['right_bans_complete']}/{expected_bans} fully visible")
    if not case["objective_timers_visible"]:
        failures.append("objective timers are missing")

    base, damage, graph = [
        read_stats_region(directory / f"{filename}-{state}.jpg", size)
        for state in ("base", "damage", "graph")
    ]
    for label, before, after in (("damage table", base, damage),
                                 ("soul graph", base, graph),
                                 ("table to graph", damage, graph)):
        change = changed_fraction(before, after)
        print(f"  {label}: {change:.1%} of the stats region changed")
        if change < MIN_STATS_CHANGE:
            failures.append(f"no visible change for {label}")
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_set", type=Path)
    parser.add_argument("cases", nargs="*")
    args = parser.parse_args()
    data = json.loads(args.capture_set.read_text(encoding="utf-8"))
    cases = args.cases or list(data["cases"])
    passed = True
    for name in cases:
        print(name)
        failures = check_capture(args.capture_set.parent, name, data["cases"][name],
                                 data["clock"], data["right_bans_expected"])
        if failures:
            passed = False
            print("  FAIL: " + "; ".join(failures))
        else:
            print("  PASS")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
