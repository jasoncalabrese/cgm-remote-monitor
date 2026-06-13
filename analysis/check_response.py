#!/usr/bin/env python3
"""
Check the glucose response to the Step-1 basal change (live on Loop 2026-06-13 06:48 UTC).
Pulls fresh CGM entries since the cutover and compares the two TARGET windows
(overnight 00:00-04:00 and midday 11:00-16:00, local UTC-7) against the pre-change
90-day baseline.

Run a day or more after the change for meaningful data:
    python3 check_response.py
"""
import json, urllib.request, statistics as st, datetime
from collections import defaultdict as dd

BASE = "https://nightscout.cbrese.com/api/v1"
TZ = -7 * 3600 * 1000
CUTOVER_MS = int(datetime.datetime(2026, 6, 13, 6, 48, tzinfo=datetime.timezone.utc).timestamp() * 1000)

# Pre-change baseline (from 90-day pull; see REPORT.md). %<70 in each target window.
BASELINE = {
    "overnight 00:00-04:00": {"mean": 109, "lo70": 11.0, "lo54": 2.9},  # last-30d pre-change was worse (~13%)
    "midday 11:00-16:00":    {"mean": 105, "lo70": 11.6, "lo54": 3.0},
}


def lh(ms):
    return int(((ms + TZ) // 3600000) % 24)


def fetch_entries(since_ms):
    url = f"{BASE}/entries.json?find[date][$gte]={since_ms}&count=50000"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def dedup(entries):
    bk = dd(list)
    for x in entries:
        if x.get("type") == "sgv" and x.get("sgv"):
            bk[round(x["date"] / 300000)].append(x["sgv"])
    return sorted((b * 300000, sum(v) / len(v)) for b, v in bk.items())


def window_stats(seq, hours):
    v = [g for ms, g in seq if lh(ms) in hours]
    if not v:
        return None
    return {
        "n": len(v),
        "mean": st.mean(v),
        "lo70": 100 * sum(1 for x in v if x < 70) / len(v),
        "lo54": 100 * sum(1 for x in v if x < 54) / len(v),
        "tir": 100 * sum(1 for x in v if 70 <= x <= 180) / len(v),
    }


def main():
    seq = dedup(fetch_entries(CUTOVER_MS))
    if not seq:
        print("No data since cutover yet — wait for an overnight/midday to pass.")
        return
    hrs = (seq[-1][0] - CUTOVER_MS) / 3600000
    nights = max(1, int(hrs / 24) + 1)
    print(f"Since change: {hrs:.1f} h elapsed, {len(seq)} readings (~{nights} night(s) of data)\n")
    targets = {"overnight 00:00-04:00": (0, 1, 2, 3), "midday 11:00-16:00": (11, 12, 13, 14, 15)}
    print(f"{'window':22s} {'n':>4} {'mean':>5} {'%<70':>6} {'%<54':>6} {'TIR':>5}   vs baseline %<70")
    for name, hours in targets.items():
        s = window_stats(seq, hours)
        if not s:
            continue
        b = BASELINE[name]
        arrow = "improved" if s["lo70"] < b["lo70"] - 1 else ("worse" if s["lo70"] > b["lo70"] + 1 else "~same")
        print(f"{name:22s} {s['n']:4d} {s['mean']:5.0f} {s['lo70']:5.1f}% {s['lo54']:5.1f}% {s['tir']:4.0f}%   "
              f"{b['lo70']:.1f}% -> {s['lo70']:.1f}%  ({arrow})")
    print("\nGoal: %<70 toward <4%, %<54 toward <1%. Small sample early — trend over several days.")


if __name__ == "__main__":
    main()
