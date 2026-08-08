# START HERE — Square OCR misreads (open, 2026-08-07)

## Run this first

```
python tests/square-2026-08/ocr_bench.py
```

Needs the connector's own environment (tesserocr + opencv + Pillow). It takes
seconds. It prints a table of preprocessing variants and how many of the 15
known values each one reads correctly.

**Then:** take the winning variant, apply it to the Square branch in
`src/screenshot_base.py`, rebuild the exe, send it to the reporter.

If **no** variant beats `baseline (today)`, stop — preprocessing is not the
problem and `square.traineddata` needs retraining on Square's post-revamp font.
Do not ship a preprocessing change that did not win.

## Why it is not already fixed

A Square HE owner reported misreads on 2026-08-07 and sent screenshots of the
connector's own Verify ROI dialog beside the on-screen truth. The failures were
diagnosed but **no code was changed**, on purpose: the Mac this was worked on has
no Tesseract, so no candidate fix could be measured, and the connector's OCR
works well enough today that an unverified change could make it worse. The same
change is also worth sending upstream to springbok, which is not somewhere to
send a guess.

## What is already known

Full evidence in [GROUND_TRUTH.md](GROUND_TRUTH.md). The short version:

- The errors are **digit substitutions**, not garbage — clustered on **9 → 8**
  and **6 → 5/0**. Same field reads correctly on one shot and wrong on another.
- The tile digits are **~19 px cap height**; Tesseract wants ~30 px. In this thin
  font, 9-vs-8 and 6-vs-5 differ only by whether the lower bowl closes.
- The tiles are **light text on near-black**, and the Square path stops at
  greyscale — Tesseract gets inverted polarity.
- So two independent candidates: **upscale**, and **binarize + invert**. The
  bench crosses both.
- `src/screenshot_base.py` gates its threshold/invert/zoom preprocessing on
  `device_id == MLM2PRO`. **Square gets none of it.**

## Separate issues found in the same screenshots — do not conflate

1. `13.4 → 3.4` loses a **leading** digit while keeping the rest. That is a crop
   too tight on the left, not a glyph confusion. Check the Ball Speed ROI's left
   edge on its own.
2. All three analysis screenshots show a stray ROI box labelled `b Speed` in the
   **top-left corner**, far outside the tile row. Could be a duplicate ROI on the
   reporter's install, could be an editor artifact. **Ask him** rather than
   reasoning from it.

## Also worth knowing

- The reporter uses **Infinite Tees**, not GSPro. He reports it sends and expects
  identical data (built against the official Square–GSPro connector), just a
  different port.
- He confirmed the connector pausing on `club = putter` is **working as intended**
  — that was a question, not a bug.
- 🔴 He also said Square putts well on its own and he is unsure Square owners
  would want a second device for it. That matches the sim-putting research and is
  a positioning signal, not an OCR issue.
