# Rapsodo MLM2PRO — Bluetooth setup

For `Rapsodo MLM2PRO BT`, the direct-Bluetooth entry.

> **Two entries, two mechanisms — pick deliberately.**
> `Rapsodo MLM2PRO BT` talks to the unit over Bluetooth. This page is about that.
> `Rapsodo MLM2PRO` is the phone-mirror route: you mirror the Rapsodo Range
> display to the PC and the connector reads that window with OCR. It needs no
> Bluetooth and none of the steps below. Most "how to connect your MLM2PRO"
> videos are about the mirror route.

## Why this connector, when Rapsodo has an official GSPro integration

It came later. Rapsodo's own GSPro integration handles full swings and carries
**no putting**. Wiring in a putting device is the reason to run a springbok-line
connector at all now, and it is why LagKing Connector exists.

That has a direct consequence for step 2 below.

## The sequence

1. **Rapsodo phone app → connect to the MLM2PRO.**
2. **Authorize a third-party app. Choose `Awesome Golf`, not `GSPro`.**
   The `GSPro` entry in that list is Rapsodo's own official integration. Picking
   it routes the unit to Rapsodo's path, which is the one without putting.
   This connector rides a different slot and forwards to GSPro itself.
3. **Disconnect from the MLM2PRO in the phone app.** The unit accepts one
   Bluetooth connection, so the phone has to let go before the PC can take it.
4. **In LagKing Connector**, select `Rapsodo MLM2PRO BT` and press Start.

Steps 1–3 happen entirely in Rapsodo's app. The connector has no visibility into
them and cannot do them for you — see below.

## What the connector actually does, and what it can't tell you

Traced from source 2026-08-01. Useful when something fails, because the error
messages are misleading about where the failure lives.

**The connector never performs, requests, or inspects the authorization.** It
writes an auth blob to the unit over Bluetooth and reads back a one-byte status.
There is no app-identity field anywhere in the request — the connector cannot
say "I am Awesome Golf". Whatever the authorization does, it happens between the
phone app, the unit, and Rapsodo, and the connector only learns the verdict.

**The unit decides, not Rapsodo's server.** The auth-failure branch fires on the
Bluetooth response and returns *before* the connector ever contacts
`mlm.rapsodo.com` (`mlm2pro_device.py:249-261` vs `:295-313`). So an
authorization error is not a network problem, and checking your internet will
not help.

**Internet is still required, on every single connection.** Once the unit says
yes, the connector fetches a token over HTTPS and writes it back to the unit.
There is no offline path and no cached-token path.

**There is no retry.** Any failure — including an unexpected disconnect
mid-round — tears the device down and needs a manual Start. Nothing reconnects
on its own.

### Error messages that mean something other than what they say

| What you see | What it actually means |
|---|---|
| `Your 3rd party authorisation expired on …, please re-authorise in the Rapsodo app` | The unit rejected the auth. Redo steps 1–3. It says "expired" even if you never authorized at all. |
| `… expired on Uknown` (sic) | You have never authorized. The date is a default zero, not a lapsed grant. |
| `No device found` after ~40 s | The unit was never seen advertising. Usually the phone still holds it, or the unit is asleep — the connector suggests looking for a steady red light, but only after the scan has already failed. |
| `Failed to update user token from web API` | The unit accepted you; the HTTPS fetch failed. This one *is* a network problem. |

### Settings that do nothing on this path

Altitude and temperature are hardcoded on the Bluetooth path — air pressure is
passed as `0.0` and temperature as 15 °C regardless of what you enter
(`mlm2pro_device.py:103`, `__get_initial_parameters`). Tuning them changes
nothing. This is upstream behaviour, not a LagKing change.

## What is not established

Stated plainly, because guessing here wastes someone's evening:

- **Whether `Awesome Golf` specifically is required.** It is what works in
  practice. The connector sends no app identity, so nothing in the source
  confirms whether another third-party slot would do just as well. Reported
  behaviour, not a verified mechanism.
- **What "disconnect" requires** — closing the app, force-quitting it, or
  turning off the phone's Bluetooth. Nothing specifies this. The practical
  requirement is that the phone releases the Bluetooth link.
- **How often you must re-authorize.** The unit reports an expiry date and the
  connector displays it, but it gates nothing locally, so the real cadence is
  unknown. Treat a sudden authorization error as "redo steps 1–3", not as a bug.
- **Whether the vendor key still works.** It dates from an upstream commit in
  2024 and no live request has been made from this fork. If Rapsodo has rotated
  it, the symptom is the web-API failure in the table above.

None of the above has been exercised against a real unit from this fork. It is a
source trace plus reported field behaviour.

## Known interaction with LagKing putting

If **auto-start is on** and the putting system is **LagKing**, the connector
starts a second Bluetooth scan at launch, alongside the MLM2PRO scan, on the
same adapter.

This is a LagKing change: upstream defaults putting to `None`, which made the
auto-start call a no-op. Our default is `LagKing`, so it now actually scans.
Whether two concurrent scans interfere on Windows is **untested**.

If the MLM2PRO becomes hard to find at launch, turn off auto-start and press the
two Start buttons yourself — launch monitor first, putting second. Please report
it if you hit this; it is the one thing here we would need to fix rather than
document.
