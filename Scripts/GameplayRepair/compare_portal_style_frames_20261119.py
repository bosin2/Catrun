"""Measure matched portal renders and camera-locked sparks, using Pillow and NumPy.

Pass the existing DepartureFrames or Stage2ArrivalFrames report.json paths to
--compare. For actual spark differences, pass the new paired capture report to
--motion. Metrics are reported on stdout and leave the input images untouched.
"""

import argparse
import json
import math
from pathlib import Path
import re

import numpy as np
from PIL import Image


ANCHORS = {"stage1": (101., -493.9189189189189, 89.2), "stage2": (1375., 3983., 90.)}


def payload(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render_rows(report, stage):
    if stage == "stage2":
        return {row["frame"]: row["capture"] for row in report["frames"]}
    return {row["frame"]: row["image"] for row in report["samples"] if "image" in row}


def camera_state(stage, row):
    if stage == "stage1":
        return row["camera_location"], row["camera_rotation"], row["fov"], False
    numbers = re.findall(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", row["rotation"])
    assert len(numbers) == 3, row["rotation"]
    return row.get("position", row.get("location")), list(map(float, numbers)), row["ortho_width"], True


def portal_region(state, center, size):
    location, rotation, lens, ortho = state
    width, height = size
    pitch, yaw, roll = map(math.radians, rotation)
    forward = np.array((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)))
    base_right = np.array((-math.sin(yaw), math.cos(yaw), 0.))
    base_up = np.cross(forward, base_right)
    right = base_right * math.cos(roll) + base_up * math.sin(roll)
    up = base_up * math.cos(roll) - base_right * math.sin(roll)
    points = []
    for x in (-63., 63.):
        for y in (-32., 3.):
            for z in (-92., 102.):
                delta = np.array(center) + (x, y, z) - location
                depth = delta @ forward
                if not ortho and depth < 1.:
                    continue
                scale = lens / 2 if ortho else depth * math.tan(math.radians(lens) / 2)
                sx = width * (0.5 + 0.5 * (delta @ right) / scale)
                sy = height / 2 - width * 0.5 * (delta @ up) / scale
                points.append((sx, sy))
    if not points:
        return None
    x, y = zip(*points)
    region = (max(0, int(min(x))), max(0, int(min(y))),
              min(width, math.ceil(max(x))), min(height, math.ceil(max(y))))
    return region if region[2] - region[0] > 4 and region[3] - region[1] > 4 else None


def image_pair(a, b, camera, center):
    with Image.open(a) as left, Image.open(b) as right:
        assert left.size == right.size, (left.size, right.size)
        roi = portal_region(camera, center, left.size)
        if roi:
            return roi, np.asarray(left.convert("RGB").crop(roi)), np.asarray(right.convert("RGB").crop(roi))
    return None, None, None


def metrics(data):
    pixels = data.reshape((-1, 3)).astype(np.float32) / 255
    highs = pixels.max(axis=1)
    lows = pixels.min(axis=1)
    saturation = (highs - lows) / np.maximum(highs, 1e-5)
    luma = pixels @ np.array((0.2126, 0.7152, 0.0722))
    blue_cyan = (pixels[:, 2] > pixels[:, 0] + 0.10) & (highs > 0.40) & (saturation > 0.35)
    return {
        "blue_cyan_fraction": float(blue_cyan.mean()),
        "near_white_fraction": float((lows >= 0.96).mean()),
        "luma_p95": float(np.quantile(luma, 0.95)),
        "color_saturation_median": float(np.median(saturation[blue_cyan])) if blue_cyan.any() else None,
    }


def compare(stage, before, after, frame_numbers):
    old, new = render_rows(payload(before), stage), render_rows(payload(after), stage)
    rows = []
    key = "image" if stage == "stage2" else "path"
    for frame in frame_numbers:
        prior, current = old[frame], new[frame]
        camera = camera_state(stage, prior)
        latest = camera_state(stage, current)
        assert camera[3] == latest[3] and all(
            np.allclose(first, second, atol=0.002, rtol=0) for first, second in zip(camera[:3], latest[:3])
        ), (stage, frame, "camera changed", camera, latest)
        roi, old_pixels, new_pixels = image_pair(prior[key], current[key], camera, ANCHORS[stage])
        if roi is None:
            rows.append({"frame": frame, "portal_region_visible": False})
            continue
        rows.append({"frame": frame, "roi_xyxy": roi, "before": metrics(old_pixels), "after": metrics(new_pixels),
                     "before_image": prior[key], "after_image": current[key]})
    return {"stage": stage, "frames": rows}


def motion(report_path):
    report = payload(report_path)
    assert report["completed"], report.get("error", report["frames"])
    camera = camera_state("stage2", report["camera"])
    position = report["portal"]["location"]
    center = (*position[:2], position[2] + 90)
    rows, masks = [], []
    for frame in report["frames"]:
        roi, absent, present = image_pair(frame["hidden"], frame["visible"], camera, center)
        assert roi, "Portal did not project into the image."
        gain = present.astype(np.int16) - absent.astype(np.int16)
        mask = (gain[:, :, 1] >= 10) | (gain[:, :, 2] >= 14)
        rows.append({"world_seconds": frame["world_seconds"], "brightened_pixels": int(mask.sum()),
                     "peak_rgb_gain": int(gain.max()), "roi_xyxy": roi,
                     "on_image": frame["visible"], "off_image": frame["hidden"]})
        masks.append(mask)
    for index, (first, second) in enumerate(zip(masks, masks[1:]), start=1):
        union = np.count_nonzero(first | second)
        rows[index]["changed_fraction_of_illuminated_pixels"] = (
            float(np.count_nonzero(first ^ second) / union) if union else None
        )
    return {"samples": rows, "portal": report["portal"],
            "scope": "Rendered differences from toggling the spark component at a fixed saved camera."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare", action="append", nargs=4, metavar=("STAGE", "BEFORE", "AFTER", "FRAMES"),
                        help="stage1 or stage2, report paths, and comma-separated frame numbers")
    parser.add_argument("--motion", help="report.json from paired spark captures")
    args = parser.parse_args()
    if not (args.compare or args.motion):
        parser.error("Pass --compare or --motion.")
    result = {"comparisons": [compare(stage, before, after, list(map(int, frames.split(","))))
                              for stage, before, after, frames in (args.compare or [])]}
    if args.motion:
        result["motion"] = motion(args.motion)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
