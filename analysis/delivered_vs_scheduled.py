#!/usr/bin/env python3
"""Delivered-vs-scheduled basal by hour, beside glucose outcomes for the same hour.

WHY: a scheduled rate only matters if Loop is actually delivering it. On 2026-09-05 an
afternoon basal cut (11:00 1.25->0.95) was withdrawn after this view showed Loop already
suspending 77-84% of hours 12-15 and delivering 0.13-0.21 U/hr — the lows were occurring
with basal ALREADY off, so trimming the schedule would have been close to a no-op.

READ IT THIS WAY:
  %of sch near 100 + lows  -> the scheduled rate is the problem; trim it.
  %of sch low + %suspd high + lows -> Loop is pinned at the floor with nothing left.
    The driver is elsewhere (meal dose, activity, unlogged Afrezza). Trimming won't help.
  Caveat: under dosingStrategy=automaticBolus, Loop ADDS insulin as automatic boluses, not
  as raised temp basals — so delivered basal is one-directional here and %of sch reads low
  across the board by design. Compare hours to each other, not to 100%.

Edit SCHED to match the live profile before trusting the % column.

    python3 delivered_vs_scheduled.py
"""
import sys, json, urllib.request, urllib.parse, datetime, statistics as st
from collections import defaultdict as dd
BASE="https://nightscout.cbrese.com/api/v1"; TZ=-7*3600*1000
def fetch(p,q):
    with urllib.request.urlopen(f"{BASE}/{p}?"+urllib.parse.urlencode(q),timeout=90) as r: return json.load(r)
SCHED=[(0,1.20),(2,1.00),(4.5,1.35),(9.5,1.80),(11,1.25),(16,1.80),(17,1.70),(18,1.35),(20,2.40),(22.5,1.70)]
def sched_at(h):
    r=SCHED[0][1]
    for t,v in SCHED:
        if h>=t: r=v
    return r
def ld(ms): return datetime.datetime.utcfromtimestamp((ms+TZ)/1000)
def ms_of(x):
    if x.get("mills"): return x["mills"]
    try: return int(datetime.datetime.fromisoformat(x["created_at"].replace("Z","+00:00")).timestamp()*1000)
    except Exception: return None
# window: last N days ending at the most recent local midnight (default 7).
# Pass --today to include the current partial day.
DAYS=next((int(x) for x in sys.argv[1:] if x.isdigit()), 7)
_now=datetime.datetime.now(datetime.timezone.utc)
_end=_now if "--today" in sys.argv else (_now+datetime.timedelta(milliseconds=TZ)).replace(
    hour=0,minute=0,second=0,microsecond=0)-datetime.timedelta(milliseconds=TZ)
b=int(_end.timestamp()*1000); a=b-DAYS*86400000
t=fetch("treatments.json",{"find[created_at][$gte]":
    datetime.datetime.utcfromtimestamp((a-86400000)/1000).strftime("%Y-%m-%dT%H:%M:%S.000Z"),"count":20000})
tb=sorted((ms_of(x),x) for x in t if x.get("eventType")=="Temp Basal" and ms_of(x))
# minute-resolution delivered rate
deliv=dd(list)  # hour -> list of (minutes, rate)
for i,(ms,x) in enumerate(tb):
    if ms<a or ms>=b: continue
    rate=x.get("rate", x.get("absolute"))
    if rate is None: continue
    dur=x.get("duration") or 0
    nxt=tb[i+1][0] if i+1<len(tb) else ms+dur*60000
    end=min(ms+dur*60000, nxt)
    cur=ms
    while cur<end:
        h=ld(cur).hour
        step=min(end-cur, (60-ld(cur).minute)*60000 - ld(cur).second*1000)
        step=max(step,60000)
        deliv[h].append((min(step,end-cur)/60000.0, float(rate)))
        cur+=step
# glucose by hour, same window
e=fetch("entries.json",{"find[date][$gte]":a,"find[date][$lt]":b,"count":80000})
bg=dd(list)
for x in e:
    if x.get("type")=="sgv" and x.get("sgv"): bg[ld(x["date"]).hour].append(x["sgv"])
print(f"{ld(a):%a %m/%d} - {ld(b-1):%a %m/%d}  ({DAYS}d)")
print(f"{'hr':>3} {'sched':>6} {'deliv':>6} {'%of sch':>7} {'%suspd':>7} | {'mean':>5} {'<70':>5} {'<54':>5} {'n':>5}")
for h in range(24):
    d=deliv.get(h,[])
    tot=sum(m for m,_ in d); u=sum(m*r/60 for m,r in d)
    dr=u/(tot/60) if tot else 0
    zero=100*sum(m for m,r in d if r<0.01)/tot if tot else 0
    s=sched_at(h)
    v=bg.get(h,[])
    if not v: continue
    mark=" <<<" if 100*sum(1 for x in v if x<70)/len(v)>=15 else ""
    print(f"{h:3d} {s:6.2f} {dr:6.2f} {100*dr/s:6.0f}% {zero:6.0f}% | {st.mean(v):5.0f} "
          f"{100*sum(1 for x in v if x<70)/len(v):4.1f}% {100*sum(1 for x in v if x<54)/len(v):4.1f}% {len(v):5d}{mark}")
