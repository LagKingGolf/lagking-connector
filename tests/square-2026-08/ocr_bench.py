"""Score candidate Square OCR preprocessing against real screenshots.

WHY THIS EXISTS. A Square HE owner reported occasional misreads on 2026-08-07
and supplied screenshots of the connector's own Verify ROI dialog next to the
on-screen truth (see GROUND_TRUTH.md). The failures are digit substitutions
clustered on 9->8 and 6->5/0, which points at an under-resolved glyph rather
than at contrast. That is a hypothesis, and the connector's OCR currently works
well enough that shipping an unmeasured "fix" could easily make it worse.

So this harness measures instead of guessing: it crops the tile regions from the
fixtures, runs each candidate preprocessing variant through Tesseract with the
same `square.traineddata` the app uses, and scores against the known values.

RUN IT WHERE THE CONNECTOR RUNS (the Windows box / its venv) -- it needs
tesserocr, opencv and Pillow, which the connector already depends on:

    python tests/square-2026-08/ocr_bench.py

Output is a table of variant vs field accuracy. Adopt the winner in
src/screenshot_base.py; if nothing beats the baseline, the answer is retraining
square.traineddata on the new font, not preprocessing.

⚠️ The ROI boxes below were measured off these specific 1002x762 / 1073x763
screenshots, NOT read from a live settings file. If a crop is clipping, fix the
number here first -- a bad crop would be scored as a bad variant.
"""

from __future__ import annotations

import os
import sys

try:
    import cv2
    import numpy as np
    import tesserocr
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment guard
    sys.exit(
        f"missing dependency: {exc}\n"
        "Run this in the connector's environment (it already needs tesserocr, "
        "opencv-python and Pillow)."
    )

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))

# field -> (x, y, w, h) in the fixture's own pixel space, plus the truth.
# Boxes are the tile VALUE only, not its unit or caption row.
FIXTURES = [
    {
        "file": "square-1.png",
        "shot": 11,
        "rois": {
            "ball_speed": ((122, 638, 66, 40), "27.6"),
            "hla":        ((200, 638, 66, 40), "R5.4"),
            "vla":        ((283, 638, 68, 40), "27.3"),
            "spin_rate":  ((522, 638, 68, 40), "3410"),
            "spin_axis":  ((607, 638, 68, 40), "L20.1"),
        },
    },
    {
        "file": "square-2.png",
        "shot": 10,
        "rois": {
            "ball_speed": ((124, 633, 64, 40), "13.4"),
            "hla":        ((202, 633, 64, 40), "R2.5"),
            "vla":        ((285, 633, 66, 40), "34.8"),
            "spin_rate":  ((524, 633, 68, 40), "1887"),
            "spin_axis":  ((609, 633, 68, 40), "L26.1"),
        },
    },
    {
        "file": "square-3.png",
        "shot": 8,
        "rois": {
            "ball_speed": ((122, 637, 64, 40), "33.8"),
            "hla":        ((200, 637, 66, 40), "R9.7"),
            "vla":        ((283, 637, 68, 40), "23.5"),
            "spin_rate":  ((522, 637, 68, 40), "3286"),
            "spin_axis":  ((607, 637, 68, 40), "R4.9"),
        },
    },
]

WHITELIST = "0123456789.,LR-"


def crop(img: "np.ndarray", box: tuple[int, int, int, int]) -> "np.ndarray":
    x, y, w, h = box
    return img[y:y + h, x:x + w]


# --- candidate preprocessing variants ---------------------------------------
# Each takes a BGR crop and returns a PIL image ready for Tesseract.

def v_baseline(c):
    """What Square gets today: crop -> greyscale. Nothing else."""
    return Image.fromarray(np.uint8(c)).convert("L")


def _upscale(c, factor):
    h, w = c.shape[:2]
    return cv2.resize(c, (int(w * factor), int(h * factor)), interpolation=cv2.INTER_CUBIC)


def v_up2(c):
    return Image.fromarray(np.uint8(_upscale(c, 2))).convert("L")


def v_up3(c):
    return Image.fromarray(np.uint8(_upscale(c, 3))).convert("L")


def v_up4(c):
    return Image.fromarray(np.uint8(_upscale(c, 4))).convert("L")


def _binarize(pil_img, threshold=110):
    """Square draws light text on a dark tile; Tesseract wants black on white."""
    return pil_img.point(lambda p: 0 if p > threshold else 255)


def v_bin(c):
    return _binarize(Image.fromarray(np.uint8(c)).convert("L"))


def v_up3_bin(c):
    return _binarize(Image.fromarray(np.uint8(_upscale(c, 3))).convert("L"))


def v_up4_bin(c):
    return _binarize(Image.fromarray(np.uint8(_upscale(c, 4))).convert("L"))


VARIANTS = {
    "baseline (today)": v_baseline,
    "upscale x2": v_up2,
    "upscale x3": v_up3,
    "upscale x4": v_up4,
    "binarize": v_bin,
    "upscale x3 + binarize": v_up3_bin,
    "upscale x4 + binarize": v_up4_bin,
}


def normalise(s: str) -> str:
    """Compare like the app does: strip spaces and thousands separators."""
    return s.strip().replace(" ", "").replace(",", "").upper()


def run(psm, whitelist: bool):
    tessdata = os.path.join(REPO)
    results = {name: {"hit": 0, "total": 0, "misses": []} for name in VARIANTS}

    api = tesserocr.PyTessBaseAPI(psm=psm, lang="square", path=tessdata)
    if whitelist:
        api.SetVariable("tessedit_char_whitelist", WHITELIST)
    try:
        for fx in FIXTURES:
            path = os.path.join(HERE, fx["file"])
            bgr = cv2.imread(path)
            if bgr is None:
                print(f"  ! could not read {fx['file']}")
                continue
            for field, (box, truth) in fx["rois"].items():
                c = crop(bgr, box)
                for name, fn in VARIANTS.items():
                    api.SetImage(fn(c))
                    got = normalise(api.GetUTF8Text())
                    ok = got == normalise(truth)
                    results[name]["total"] += 1
                    if ok:
                        results[name]["hit"] += 1
                    else:
                        results[name]["misses"].append(
                            f"{fx['file']}:{field} want {truth} got {got or '(empty)'}"
                        )
    finally:
        api.End()
    return results


def main():
    print("Square OCR bench — fixtures from a Square HE owner, 2026-08-07")
    print("Truth is the on-screen tile row; see GROUND_TRUTH.md\n")
    for psm_name, psm in (("SINGLE_WORD (app default)", tesserocr.PSM.SINGLE_WORD),
                          ("SINGLE_LINE", tesserocr.PSM.SINGLE_LINE),
                          ("RAW_LINE", tesserocr.PSM.RAW_LINE)):
        for wl in (False, True):
            print(f"== psm={psm_name}  whitelist={'on' if wl else 'off'}")
            res = run(psm, wl)
            for name, r in sorted(res.items(), key=lambda kv: -kv[1]["hit"]):
                pct = (100.0 * r["hit"] / r["total"]) if r["total"] else 0.0
                print(f"   {name:<24} {r['hit']:>2}/{r['total']}  {pct:5.1f}%")
            best = max(res.items(), key=lambda kv: kv[1]["hit"])
            if best[1]["misses"]:
                print(f"   best still misses ({best[0]}):")
                for m in best[1]["misses"][:6]:
                    print(f"     - {m}")
            print()

    print("If NOTHING beats the baseline, preprocessing is not the problem and")
    print("square.traineddata needs retraining on the post-revamp font.")


if __name__ == "__main__":
    main()
