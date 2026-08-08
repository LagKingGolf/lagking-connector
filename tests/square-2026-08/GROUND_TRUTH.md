# Square OCR regression fixtures — 2026-08-07

Six screenshots from a **Square HE** owner (Reddit/email: zubblwump), captured
against the LagKing fork on 2026-08-07. Three of them are the connector's own
**Verify ROI Results** dialog overlaid on Square's ANALYSIS view, which makes
them a direct read-vs-truth comparison — the on-screen tile row is the ground
truth, the dialog is what OCR produced.

Reported symptom: *"Occasionally a few misreads on nearly all measurements, but
did seem to pick it up a little better in analysis mode."* His hypothesis:
*"I wonder if the springbok OCR file for square needs updating since the square
software was revamped a couple months ago."*

## The evidence

| File | Shot | Field | On screen | OCR read | |
|---|---|---|---|---|---|
| square-1.png | 11 | Ball Speed | **27.6** | **27.0** | ✗ |
| square-1.png | 11 | Spin Rate | **3,410** | **3630.0** | ✗ |
| square-1.png | 11 | Spin Axis | L20.1 | −20.1 | ✓ |
| square-1.png | 11 | HLA | R5.4 | 5.4 | ✓ |
| square-1.png | 11 | VLA | 27.3 | 27.3 | ✓ |
| square-2.png | 10 | Ball Speed | **13.4** | **3.4** | ✗ |
| square-2.png | 10 | Spin Rate | 1,887 | 1887.0 | ✓ |
| square-2.png | 10 | Spin Axis | **L26.1** | **−25.1** | ✗ |
| square-2.png | 10 | HLA | R2.5 | 2.5 | ✓ |
| square-2.png | 10 | VLA | 34.8 | 34.8 | ✓ |
| square-3.png | 8 | Ball Speed | 33.8 | 33.8 | ✓ |
| square-3.png | 8 | Spin Rate | **3,286** | **3385.0** | ✗ |
| square-3.png | 8 | Spin Axis | **R4.9** | **4.8** | ✗ |
| square-3.png | 8 | HLA | **R9.7** | **8.7** | ✗ |
| square-3.png | 8 | VLA | 23.5 | 23.5 | ✓ |

`square-4/5/6.png` are the **putting practice** mode (BALL SPD · DIRECTION ·
TOTAL · to HOLE tiles) and the full-screen green. They are not OCR fixtures —
they document why putting mode is unusable for full shot data, which is a
separate finding (that mode exposes only ball speed and HLA).

## What the errors actually look like

**Digit substitutions, not garbage.** No field returns nonsense; each returns a
plausible number with one or two digits wrong. Clustered on:

- **9 → 8** — `R9.7 → 8.7`, `4.9 → 4.8`
- **6 → 5** — `L26.1 → −25.1`, `3,2**86** → 3,3**85**`
- **6 → 0** — `27.6 → 27.0`

VLA is correct in all three. The same field reads correctly on one shot and
wrong on another (Ball Speed: right on shot 8, wrong on 10 and 11), so this is
not a misplaced ROI for those fields.

**That is the signature of a font-model mismatch**, which matches the reporter's
hypothesis: `square.traineddata` predates Square's software revamp.

**One error is a different bug.** `13.4 → 3.4` loses a *leading* digit while
keeping the rest — that is a crop that is too tight on the left, not a glyph
confusion. Worth checking the Ball Speed ROI's left edge independently.

⚠️ **Also visible in all three analysis screenshots:** a small ROI box labelled
`b Speed` sitting in the **top-left corner** of the capture, far outside the
tile row. Either a stray duplicate ROI or an artifact of the ROI editor — worth
confirming with the reporter before drawing conclusions from it.

## Why the fix is not obviously "add thresholding"

`src/screenshot_base.py` applies its threshold/invert/de-space preprocessing and
its zoom **only when `device_id == MLM2PRO`**. Square gets crop → greyscale →
OCR, with no binarisation and no upscale.

Adding contrast handling is tempting, but the observed failures are glyph
confusions, and thresholding does not change glyph shape. **Upscaling** is the
better-founded candidate: Tesseract's models expect roughly a 30 px cap height,
Square's tile digits are well under that, and adjacent-digit confusion (9/8,
6/5) is the classic symptom of under-resolved glyphs. MLM2PRO already gets a
zoom path; Square gets none.

So: measure before changing. `ocr_bench.py` in this folder does that.
