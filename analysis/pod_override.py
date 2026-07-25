#!/usr/bin/env python3
"""
Pod-cycle override automation (Nightscout <-> Loop).

WHY THIS EXISTS
  Glucose grades systematically with Omnipod age (45d, 19 pods, compression-excluded):
      day 1  mean 105  TIR 91%  7.4% <70
      day 2  mean 114  TIR 95%  3.9% <70
      day 3  mean 118  TIR 97%  2.5% <70
  Bolus insulin is flat across pod days (43.1/43.8/43.8 U), so this is an ABSORPTION
  effect: a fresh site absorbs better (lows on day 1), an aged site absorbs worse
  (highs on day 3 - breakfast peaks 148 -> 185, 12% -> 55% over 180).

HOW IT WORKS  (no Loop code changes, no app rebuild)
  Loop -> Nightscout : pod changes are auto-logged as eventType "Site Change"
                       (enteredBy "loop://iPhone").
  Nightscout -> Loop : POST /api/v2/notifications/loop  (see lib/server/loop.js and
                       lib/api/notifications-v2.js on the deployed 2022-06 branch).
                       Nightscout turns this into an APNs push to the Loop app.
  This script closes the loop: read pod age, decide which EXISTING preset applies,
  and ask Loop to turn it on. Nothing new is invented - it presses the same button
  a human would.

  IMPORTANT - what actually crosses the wire. The APNs payload contains only:
      override-name              <- the preset NAME (data.reason)
      override-duration-minutes  <- data.duration
  It does NOT carry insulinNeedsScaleFactor or correctionRange. Those live in the
  presets ON THE PHONE. So this script cannot invent a dose adjustment; it can only
  name a preset the device already has. (Scale factors are shown below purely for
  documentation.) The preset name must match EXACTLY, emoji included.
  Note also: POSTing a treatment to /api/v1/treatments.json does NOT command Loop -
  it only writes a record. The notifications endpoint is the real path.

SAFETY DESIGN  (read before running --live)
  * THE DEVICE OWNS THE MAGNITUDE. The server names a preset; Loop applies whatever
    that preset is configured to do. The server cannot set a scale factor at all.
  * FAIL-SAFE BY EXPIRY. Overrides are issued with a short duration and refreshed.
    If this script dies, the network drops, or the host reboots, the override simply
    EXPIRES and therapy reverts to the normal profile. Nothing gets stuck on.
    (The APNs payload itself also expires after 5 minutes - a missed push is dropped,
    not queued.)
  * NEVER STACKS. If ANY override is already active - a user-set "Rage"/"Eating Soon"
    or one of ours - it does nothing. The human always wins, and our own override is
    simply left to run out before being renewed.
  * PRESET ALLOWLIST. Only names in ALLOWED_PRESETS may ever be sent.
  * STALE/FUTURE DATA -> NO ACTION. If the last Site Change is older than MAX_POD_AGE_H
    or in the future, it does nothing rather than guess.
  * DRY RUN BY DEFAULT. --live is required to send, plus a token in NS_TOKEN with the
    notifications:loop:push permission.

NOT MEDICAL ADVICE. This adjusts automated insulin delivery. Magnitudes here are a
conservative starting point derived from aggregates - they are NOT validated as safe
for an individual. Review with the care team, start with PHASE-1 only, and watch the
first cycles closely.

    python3 pod_override.py                 # dry run (default) - shows what it would do
    python3 pod_override.py --enable-day3   # also arm the day-3 (more insulin) side
    NS_TOKEN=... python3 pod_override.py --live
"""
import sys, os, json, urllib.request, urllib.parse, datetime

BASE = os.environ.get("NS_URL", "https://nightscout.cbrese.com")
TOKEN = os.environ.get("NS_TOKEN")
LIVE = "--live" in sys.argv
ENABLE_DAY3 = "--enable-day3" in sys.argv
VERBOSE = "--verbose" in sys.argv

# --- safety rails -----------------------------------------------------------
MAX_POD_AGE_H = 80                  # beyond this, assume an unlogged change -> no action
OVERRIDE_MINUTES = 60               # short: refreshed each run, expires if we die

# Only these preset names may ever be sent. They must exist in Loop on the phone,
# spelled exactly (emoji included). Anything not on this list is refused.
ALLOWED_PRESETS = {"↘️ Running a little Low", "↗️ Running a little High"}

# --- the policy (uses presets that already exist in this Loop) --------------
# Phase 1 (default): only the day-1 REDUCTION. Less insulin is the safer direction
# to test first, and day 1 carries the worst lows (7.4%).
# Phase 2 (--enable-day3): the day-3 increase. Riskier - adding insulin - so it is
# opt-in and should only be armed after phase 1 looks good.
# NOTE: `scale` is DOCUMENTATION ONLY - it is not sent and not enforced here. The
# real magnitude is whatever the preset is set to in Loop on the device.
POLICY = [
    # (age_from_h, age_to_h, preset_name,                 scale-on-device, phase)
    (12, 24, "↘️ Running a little Low", 0.9, 1),
    (48, MAX_POD_AGE_H, "↗️ Running a little High", 1.1, 2),
]


def api_get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def parse_ts(x):
    for k in ("created_at", "timestamp"):
        v = x.get(k)
        if v:
            try:
                return datetime.datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
    if x.get("mills"):
        return datetime.datetime.fromtimestamp(x["mills"] / 1000, datetime.timezone.utc)
    return None


def latest_site_change(lookback_h=120):
    since = (now_utc() - datetime.timedelta(hours=lookback_h)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    rows = api_get("/api/v1/treatments.json",
                   {"find[eventType]": "Site Change", "find[created_at][$gte]": since, "count": 50})
    stamped = [(parse_ts(r), r) for r in rows]
    stamped = [(t, r) for t, r in stamped if t]
    return max(stamped, key=lambda z: z[0]) if stamped else (None, None)


def active_override(lookback_h=12):
    """Return (override_doc, expires_at) if one is currently active, else (None, None)."""
    since = (now_utc() - datetime.timedelta(hours=lookback_h)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    rows = api_get("/api/v1/treatments.json",
                   {"find[eventType]": "Temporary Override", "find[created_at][$gte]": since,
                    "count": 100})
    best = None
    for r in rows:
        t = parse_ts(r)
        dur = r.get("duration")
        if not t or not isinstance(dur, (int, float)):
            continue
        exp = t + datetime.timedelta(minutes=float(dur))
        if exp > now_utc() and (best is None or exp > best[1]):
            best = (r, exp)
    return best if best else (None, None)


def desired_state(age_h):
    for lo, hi, preset, scale, phase in POLICY:
        if phase == 2 and not ENABLE_DAY3:
            continue
        if lo <= age_h < hi:
            return dict(preset=preset, scale=scale)
    return None


def issue_override(state):
    """Ask Loop to turn on a preset, via the APNs push endpoint.

    Only `reason` (preset name) and `duration` reach the device; see module docstring.
    """
    preset = state["preset"]
    if preset not in ALLOWED_PRESETS:
        print(f"  REFUSING: preset {preset!r} is not in ALLOWED_PRESETS")
        return
    body = {
        "eventType": "Temporary Override",
        "reason": preset,                  # -> APNs 'override-name'
        "duration": OVERRIDE_MINUTES,      # -> APNs 'override-duration-minutes'
        "enteredBy": "pod-cycle-automation",
        "notes": "pod-age automation",
    }
    if not LIVE:
        print(f"  DRY RUN - would POST {BASE}/api/v2/notifications/loop")
        print("   ", json.dumps(body, ensure_ascii=False))
        return
    if not TOKEN:
        print("  REFUSING: --live given but NS_TOKEN is not set.")
        return
    req = urllib.request.Request(
        f"{BASE}/api/v2/notifications/loop?token={urllib.parse.quote(TOKEN)}",
        data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            print(f"  SENT to Loop (HTTP {r.status})")
    except urllib.error.HTTPError as ex:
        print(f"  FAILED (HTTP {ex.code}): {ex.read().decode()[:200]}")


def main():
    print(f"pod-cycle override | {now_utc():%Y-%m-%d %H:%M} UTC | "
          f"{'LIVE' if LIVE else 'DRY RUN'} | day3 {'ARMED' if ENABLE_DAY3 else 'off'}")
    t, sc = latest_site_change()
    if not t:
        print("  no Site Change found in lookback window -> NO ACTION")
        return
    age_h = (now_utc() - t).total_seconds() / 3600
    print(f"  last pod change: {t:%Y-%m-%d %H:%M} UTC  (age {age_h:.1f}h)")
    if age_h < 0:
        print("  pod change timestamp is in the FUTURE -> NO ACTION"); return
    if age_h > MAX_POD_AGE_H:
        print(f"  pod age exceeds {MAX_POD_AGE_H}h (likely an unlogged change) -> NO ACTION"); return

    # Yield to ANY active override, ours or a human's. Loop reports overrides back
    # under its own enteredBy ("Loop" / "Loop (via remote command)"), so ownership
    # isn't reliably distinguishable - and it doesn't need to be: if one is running,
    # there is nothing to do. Ours simply lapses and is renewed on a later run.
    cur, exp = active_override()
    if cur:
        remaining = (exp - now_utc()).total_seconds() / 60
        print(f"  active override: '{cur.get('reason')}' by {cur.get('enteredBy','?')}, "
              f"{remaining:.0f}m left -> YIELD, no action")
        return

    want = desired_state(age_h)
    if not want:
        print("  pod age is in a neutral window -> NO ACTION (any prior override expires on its own)")
        return
    print(f"  target preset: {want['preset']}  for {OVERRIDE_MINUTES}m "
          f"(device-side scale ~x{want['scale']})")
    issue_override(want)


if __name__ == "__main__":
    main()
