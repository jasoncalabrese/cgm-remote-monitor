#!/usr/bin/env python3
"""
Check the glucose response to basal changes, with CGM-sensor warmup filtering.

Dexcom day-1 readings (and especially the first hours) are often jumpy/falsely low
and shouldn't drive basal decisions. This script pulls fresh CGM + treatments,
auto-detects each Sensor Start, and excludes a warmup window after it. A device-type
change (e.g. G6 -> G7), detected from the entries `device` field, gets a longer,
labeled exclusion because the first session on a new sensor line tends to be noisier.

It reports each target window (overnight 00:00-04:00, dawn 04:00-07:00,
midday 11:00-16:00, evening 20:00-24:00) BOTH raw and warmup-excluded, vs the
90-day baseline, so you can tell real glucose patterns from sensor artifact.

    python3 check_response.py [lookback_days]   # default 8
"""
import sys, json, urllib.request, urllib.parse, statistics as st, datetime
from collections import defaultdict as dd

BASE = "https://nightscout.cbrese.com/api/v1"
TZ = -7 * 3600 * 1000                  # local = UTC-7 (ETC/GMT+7, no DST)
LOOKBACK_DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
SENSOR_WARMUP_H = 24                   # exclude this long after a normal new sensor
DEVICE_SWITCH_WARMUP_H = 48           # longer exclusion when the sensor LINE changes (G6->G7)

# 90-day pre-change baseline per window (%<70 etc.); see REPORT.md.
BASELINE = {
    "overnight 00-04": {"hours": (0, 1, 2, 3),       "lo70": 12.5, "lo54": 2.9},
    "dawn 04-07":      {"hours": (4, 5, 6),           "lo70": 4.2,  "lo54": 0.5},
    "midday 11-16":    {"hours": (11, 12, 13, 14, 15), "lo70": 11.6, "lo54": 3.0},
    "evening 20-24":   {"hours": (20, 21, 22, 23),    "lo70": 4.9,  "lo54": 0.6},
}


def fetch(path, params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=90) as r:
        return json.load(r)


def lh(ms):
    return int(((ms + TZ) // 3600000) % 24)


def ld(ms):
    return datetime.datetime.utcfromtimestamp((ms + TZ) / 1000)


def ms_of(x):
    if x.get("mills"):
        return x["mills"]
    try:
        return int(datetime.datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def device_family(s):
    """Map a device string to a sensor line. Ignores the Loop 'share' bridge."""
    if not s:
        return None
    u = s.upper()
    if "G7" in u:
        return "G7"
    if "G6" in u:
        return "G6"
    return None  # share2 / unknown -> not a family signal


def detect_family_changes(entries):
    """Return list of (ms, old_family, new_family) where the sensor line changed."""
    fam_pts = sorted((x["date"], device_family(x.get("device")))
                     for x in entries if x.get("type") == "sgv" and device_family(x.get("device")))
    changes, cur = [], None
    for ms, fam in fam_pts:
        if cur is not None and fam != cur:
            changes.append((ms, cur, fam))
        cur = fam
    return changes, (fam_pts[-1][1] if fam_pts else None)


def sensor_starts(treatments, lo, hi):
    """Deduped Sensor Start/Change times within [lo, hi] (drops junk far-dated entries)."""
    raw = sorted(ms_of(x) for x in treatments
                 if x.get("eventType") in ("Sensor Start", "Sensor Change")
                 and ms_of(x) and lo <= ms_of(x) <= hi)
    out = []
    for ms in raw:
        if not out or ms - out[-1] > 3600000:   # collapse starts within 1h
            out.append(ms)
    return out


def build_exclusions(starts, fam_changes):
    """(start_ms, end_ms, label) warmup intervals; longer+labeled for device switches."""
    excl = []
    for s in starts:
        switch = next((c for c in fam_changes if abs(c[0] - s) <= 3 * 3600000), None)
        if switch:
            excl.append((s, s + DEVICE_SWITCH_WARMUP_H * 3600000,
                         f"{switch[1]}->{switch[2]} switch ({DEVICE_SWITCH_WARMUP_H}h)"))
        else:
            excl.append((s, s + SENSOR_WARMUP_H * 3600000, f"new sensor ({SENSOR_WARMUP_H}h)"))
    # Catch a family change with no matching Sensor Start event, too.
    for ms, old, new in fam_changes:
        if not any(abs(ms - s) <= 3 * 3600000 for s in starts):
            excl.append((ms, ms + DEVICE_SWITCH_WARMUP_H * 3600000,
                         f"{old}->{new} switch, no Sensor Start ({DEVICE_SWITCH_WARMUP_H}h)"))
    return excl


def excluded(ms, excl):
    return any(a <= ms < b for a, b, _ in excl)


def stats(vv):
    return dict(n=len(vv), mean=st.mean(vv),
                lo70=100 * sum(1 for v in vv if v < 70) / len(vv),
                lo54=100 * sum(1 for v in vv if v < 54) / len(vv),
                tir=100 * sum(1 for v in vv if 70 <= v <= 180) / len(vv))


def main():
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    since = now - LOOKBACK_DAYS * 86400000
    entries = fetch("entries.json", {"find[date][$gte]": since, "count": 30000})
    treatments = fetch("treatments.json",
                       {"find[created_at][$gte]": ld(since + 7 * 3600000).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                        "count": 10000})
    sgv = [x for x in entries if x.get("type") == "sgv" and x.get("sgv")]
    if not sgv:
        print("No CGM data in window yet.")
        return

    lo, hi = min(x["date"] for x in sgv), max(x["date"] for x in sgv)
    fam_changes, cur_fam = detect_family_changes(entries)
    starts = sensor_starts(treatments, lo, hi)
    excl = build_exclusions(starts, fam_changes)

    print(f"=== Response check: last {LOOKBACK_DAYS}d ({ld(lo):%b %d} -> {ld(hi):%b %d}) ===")
    print(f"Current sensor line: {cur_fam or 'unknown'}")
    if fam_changes:
        for ms, o, n in fam_changes:
            print(f"  ! device change {o} -> {n} at {ld(ms):%a %b %d %H:%M}")
    print(f"Sensor starts detected: {len(starts)}" +
          ("".join(f"\n  - {ld(s):%a %b %d %H:%M}" for s in starts) if starts else ""))
    if excl:
        print("Warmup windows excluded:")
        for a, b, lab in excl:
            print(f"  - {ld(a):%b %d %H:%M} -> {ld(b):%b %d %H:%M}  [{lab}]")

    # dedup to 5-min buckets
    bk = dd(list)
    for x in sgv:
        bk[round(x["date"] / 300000)].append(x["sgv"])
    seq = sorted((b * 300000, sum(v) / len(v)) for b, v in bk.items())
    clean = [(ms, v) for ms, v in seq if not excluded(ms, excl)]

    print(f"\n{'window':16} {'baseline<70':>11} | {'RAW <70/<54':>14} | {'CLEAN <70/<54  TIR':>20}")
    for name, cfg in BASELINE.items():
        raw = [v for ms, v in seq if lh(ms) in cfg["hours"]]
        cln = [v for ms, v in clean if lh(ms) in cfg["hours"]]
        r, c = stats(raw), stats(cln) if cln else None
        cstr = f"{c['lo70']:4.1f}/{c['lo54']:4.1f}  {c['tir']:4.0f}%" if c else "  (all excluded)"
        flag = ""
        if c:
            d = c["lo70"] - cfg["lo70"]
            flag = " improved" if d < -1 else (" worse" if d > 1 else " ~same")
        print(f"{name:16} {cfg['lo70']:10.1f}% | {r['lo70']:6.1f}/{r['lo54']:4.1f}   | {cstr:>20}{flag}")

    # per-night overnight, flagging warmup-affected nights
    print("\nPer-night 00:00-06:00 (clean unless flagged):")
    nights = dd(list)
    for ms, v in seq:
        if lh(ms) < 6:
            nights[ld(ms).date()].append((ms, v))
    for d in sorted(nights):
        arr = nights[d]
        warm = any(excluded(ms, excl) for ms, _ in arr)
        vals = [v for _, v in arr]
        tag = "  <-- WARMUP (ignore)" if warm else ""
        print(f"  {d}  min {min(vals):3.0f}  mean {st.mean(vals):4.0f}  %<70 "
              f"{100*sum(1 for v in vals if v<70)/len(vals):4.1f}{tag}")

    print("\nGoal: %<70 <4%, %<54 <1%. Use the CLEAN column; ignore warmup-flagged nights.")
    if cur_fam == "G7":
        print("Note: now on G7 — first session(s) may still read differently; watch the trend, not one night.")


if __name__ == "__main__":
    main()
