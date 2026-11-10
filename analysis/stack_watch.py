#!/usr/bin/env python3
"""Nudge on insulin stacking: notify shortly after a manual correction, BEFORE the repeat.

WHY THIS EXISTS
  Repeat dosing is the strongest predictor of severe lows in this dataset. Over 63 days,
  683 manual boluses >=0.5U (10.8/day), and the gap to the next one has a 25th percentile
  of NINE MINUTES:
      within 15 min  33% of all manual boluses are a repeat
      within 20 min  38%  - 260 doses carrying 401U = 6.4 U/day, 18% of manual insulin
      of those 260, 216 (83%) are correction-only, not meal-related
      67% of severe-low episodes are preceded by a repeat-dose pair
  The composite ritual is 🤬 Rage + fake carbs + manual bolus in the same minute, repeated
  5-16 minutes later - the second dose landing before the first is visible on CGM. Four
  separate settings changes shrink each dose; none of them touches the repeat.

WHAT IT DOES
  Watches treatments. When a manual bolus >=MIN_U lands and the window is NOT meal-adjacent,
  it waits NUDGE_AFTER_MIN and sends ONE Pushover message carrying the two numbers that are
  invisible at the moment of the second press: what was just given, and how long until it
  can be judged. Then it stays quiet for that episode.

  It is a speed bump, not a gate. It cannot block a bolus, does not write to Nightscout, and
  touches no therapy setting. The worst case is an ignored notification.

MODES
    python3 stack_watch.py                 # observe only - prints what it WOULD send
    python3 stack_watch.py --live          # also sends Pushover
    python3 stack_watch.py --backtest 63   # replay history: how often would it have fired?

  Run --backtest first, then --live only once the rate looks tolerable. A nudge that fires
  more than a couple of times a day will be muted, and a muted nudge is worse than none.

DEPLOYMENT (same droplet as Nightscout, reusing its Pushover env)
    */5 * * * * nightscout NS_URL=http://127.0.0.1:1337 \
      PUSHOVER_API_TOKEN=... PUSHOVER_USER_KEY=... \
      /usr/bin/python3 /opt/stack_watch.py --live >> /var/log/stack-watch.log 2>&1

  Nightscout already defines PUSHOVER_API_TOKEN and PUSHOVER_USER_KEY; point this at the
  same values, or at a different PUSHOVER_USER_KEY to send to someone else. Stdlib only.
  STATE_FILE stops a nudge repeating for the same bolus across runs; losing it causes at
  most one duplicate.

NOT MEDICAL ADVICE. This sends a message. It never doses.
"""
import sys, os, json, time, urllib.request, urllib.parse, datetime

BASE = os.environ.get("NS_URL", "https://nightscout.cbrese.com")
TOKEN = os.environ.get("NS_TOKEN")
PO_TOKEN = os.environ.get("PUSHOVER_API_TOKEN")
PO_USER = os.environ.get("PUSHOVER_USER_KEY")
STATE_FILE = os.environ.get("STACK_WATCH_STATE", "/tmp/stack_watch_state.json")

LIVE = "--live" in sys.argv
BACKTEST = next((int(a) for i, a in enumerate(sys.argv)
                 if i and sys.argv[i - 1] == "--backtest" and a.isdigit()), None)

# Tuned on 63 days. Candidates measured, as fires/day | followed by a repeat | followed by
# a severe low within 5h:
#   >=0.5U, not meal-adjacent          3.44 | 42% | 25%
#   >=1.0U + BG<180                    2.90 | 40% | 25%
#   >=1.5U + BG<180 + Rage active      1.92 | 45% | 25%   <- chosen
#   >=1.0U + BG<160 + Rage active      1.27 | 35% | 20%
# Chosen for staying under ~2/day (the mute threshold) at the best precision available.
# RAISE MIN_U or lower BG_MAX if it still gets muted; the cost is missing smaller stacks.
MIN_U = 1.5             # the composite ritual doses 2.0-2.6U; micro-corrections are noise
DETECT_U = 0.5          # boluses collected for REPEAT detection. Must stay below MIN_U: the
                        # repeat is often smaller than the dose that triggered the nudge, and
                        # filtering the pool at MIN_U hides those (it under-reported the
                        # backtest's catch rate as 24% when the true figure is 45%).
BG_MAX = 180            # correcting a genuine 250 repeatedly is defensible; 130 is not
REQUIRE_RAGE = True     # keys on the composite ritual (Rage + fake carbs + bolus, one minute)
NUDGE_AFTER_MIN = 7     # fire before the p25 repeat gap of 9 min, after the dose has settled
MEAL_G = 25             # a real meal nearby means splitting a meal dose, not stacking
MEAL_WINDOW_MIN = 45
QUIET_MIN = 90          # at most one nudge per episode


def api_get(path, params=None):
    url = f"{BASE}{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def now_ms():
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)


def ms_of(x):
    if x.get("mills"):
        return x["mills"]
    try:
        return int(datetime.datetime.fromisoformat(
            x["created_at"].replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def load_treatments(hours):
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return api_get("/api/v1/treatments.json",
                   {"find[created_at][$gte]": since, "count": 20000})


def split(t):
    """manual boluses >=MIN_U, real meals, and Rage windows."""
    bol, meals, rage = [], [], []
    for x in t:
        m = ms_of(x)
        if not m:
            continue
        ins, carb = x.get("insulin"), x.get("carbs")
        if isinstance(ins, (int, float)) and ins >= DETECT_U and x.get("automatic") is not True:
            bol.append((m, float(ins)))
        if isinstance(carb, (int, float)) and carb >= MEAL_G:
            meals.append(m)
        if (x.get("eventType") == "Temporary Override" and "Rage" in str(x.get("reason", ""))
                and isinstance(x.get("duration"), (int, float))):
            rage.append((m, m + float(x["duration"]) * 60000))
    return sorted(bol), sorted(meals), sorted(rage)


def meal_adjacent(ms, meals):
    return any(abs(ms - x) <= MEAL_WINDOW_MIN * 60000 for x in meals)


def rage_active(ms, rage):
    return any(a - 2 * 60000 <= ms <= b for a, b in rage)


def suppressed(ms, u, bg, meals, rage):
    """Reason this dose should NOT be nudged, or None."""
    if u < MIN_U:
        return f"{u:.2f}U below the {MIN_U}U threshold"
    if meal_adjacent(ms, meals):
        return f"within {MEAL_WINDOW_MIN} min of a real meal (meal split)"
    if BG_MAX and (bg is None or bg > BG_MAX):
        return f"BG {bg if bg else '?'} above {BG_MAX} (a real high)"
    if REQUIRE_RAGE and not rage_active(ms, rage):
        return "no Rage override active (not the composite ritual)"
    return None


def bg_at(ms):
    """Most recent sgv at or before ms. One fetch, cached across a backtest."""
    if not hasattr(bg_at, "_seq"):
        since = ms - 90 * 86400000
        rows = api_get("/api/v1/entries.json",
                       {"find[date][$gte]": since, "count": 200000})
        bg_at._seq = sorted((r["date"], r["sgv"]) for r in rows
                            if r.get("type") == "sgv" and r.get("sgv"))
        bg_at._ts = [z[0] for z in bg_at._seq]
    import bisect as _b
    i = _b.bisect_right(bg_at._ts, ms) - 1
    return bg_at._seq[i][1] if 0 <= i < len(bg_at._seq) else None


def iob_now():
    """Loop's own IOB, if it is being uploaded. None rather than a guess."""
    try:
        for d in api_get("/api/v1/devicestatus.json", {"count": 3}):
            v = ((d.get("loop") or {}).get("iob") or {}).get("iob")
            if isinstance(v, (int, float)):
                return float(v)
    except Exception:
        pass
    return None


def message(units, mins_ago, iob):
    iob_txt = f" IOB {iob:.1f}U." if iob is not None else ""
    return (f"{units:.2f}U {mins_ago:.0f} min ago.{iob_txt} "
            f"It takes ~20 min to show on CGM - that dose is still working.")


def read_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def write_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except Exception as ex:
        print(f"  WARN: could not persist state ({ex}); a nudge may repeat once")


def send_pushover(text):
    if not (PO_TOKEN and PO_USER):
        print("  REFUSING: --live given but PUSHOVER_API_TOKEN / PUSHOVER_USER_KEY are not set")
        return
    body = urllib.parse.urlencode({
        "token": PO_TOKEN, "user": PO_USER, "message": text,
        "title": "Insulin still working", "priority": 0}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(
                "https://api.pushover.net/1/messages.json", data=body), timeout=30) as r:
            print(f"  SENT (HTTP {r.status})")
    except urllib.error.HTTPError as ex:
        print(f"  FAILED (HTTP {ex.code}): {ex.read().decode()[:200]}")


def backtest(days):
    t = load_treatments(days * 24)
    bol, meals, rage = split(t)
    fired = caught = 0
    last = 0
    for i, (ms, u) in enumerate(bol):
        if suppressed(ms, u, bg_at(ms), meals, rage) or ms - last < QUIET_MIN * 60000:
            continue
        fired += 1
        last = ms
        # did a repeat follow inside 20 min? i.e. would the nudge have had a target
        if any(ms < m2 <= ms + 20 * 60000 for m2, _ in bol[i + 1:i + 6]):
            caught += 1
    print(f"backtest over {days}d: {len(bol)} manual boluses >={DETECT_U}U "
          f"({len(bol)/days:.1f}/day), trigger threshold {MIN_U}U")
    print(f"  nudges that would fire : {fired}  ({fired/days:.2f}/day)")
    print(f"  of those, followed by a repeat inside 20 min: {caught} "
          f"({100*caught/max(fired,1):.0f}%)")
    print(f"  -> {fired/days:.2f} notifications/day. Above ~2/day expect it to be muted.")


def main():
    if BACKTEST:
        backtest(BACKTEST)
        return
    print(f"stack-watch | {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC | "
          f"{'LIVE' if LIVE else 'OBSERVE'}")
    t = load_treatments(6)
    bol, meals, rage = split(t)
    if not bol:
        print("  no manual boluses in the lookback -> nothing to do")
        return
    ms, u = bol[-1]
    age_min = (now_ms() - ms) / 60000
    if age_min < NUDGE_AFTER_MIN:
        print(f"  last bolus {u:.2f}U is {age_min:.0f} min old (< {NUDGE_AFTER_MIN}) -> too early")
        return
    if age_min > NUDGE_AFTER_MIN + 10:
        print(f"  last bolus {u:.2f}U is {age_min:.0f} min old -> window passed, no action")
        return
    why = suppressed(ms, u, bg_at(ms), meals, rage)
    if why:
        print(f"  {u:.2f}U suppressed: {why} -> no action")
        return
    state = read_state()
    if state.get("last_nudge_ms") and ms - state["last_nudge_ms"] < QUIET_MIN * 60000:
        print(f"  within {QUIET_MIN} min of the last nudge -> quiet period, no action")
        return
    text = message(u, age_min, iob_now())
    print(f"  NUDGE: {text}")
    if LIVE:
        send_pushover(text)
    else:
        print("  OBSERVE mode - not sent (pass --live to send)")
    state["last_nudge_ms"] = ms
    write_state(state)


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        print(f"  ERROR ({type(ex).__name__}): {ex} -> NO ACTION")
        sys.exit(1)
