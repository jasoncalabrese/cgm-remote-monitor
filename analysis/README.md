# Nightscout T1D Analysis

90-day pull and pattern analysis of Type 1 diabetes data from
`https://nightscout.cbrese.com` (Nightscout v14.2.6, public-read — no token required).

## Contents

- `REPORT.md` — full analysis (TIR, overnight/dawn, post-meal, hypo risk windows).
- `analyze.py` — reproducible analysis script (reads `data/raw/`, prints all metrics).
- `data/raw/*.json.gz` — raw API responses (gzipped).

## How the data was pulled

```bash
BASE="https://nightscout.cbrese.com/api/v1"
START_MS=$(( $(date -u -d '90 days ago' +%s) * 1000 ))
START_ISO=$(date -u -d '90 days ago' +%Y-%m-%dT%H:%M:%S.000Z)

curl -s "$BASE/status.json"                                                          # confirm reachable + public-read
curl -s "$BASE/entries.json?find[date][\$gte]=$START_MS&count=50000"      -o entries.json
curl -s "$BASE/treatments.json?find[created_at][\$gte]=$START_ISO&count=50000" -o treatments.json
curl -s "$BASE/devicestatus.json?find[created_at][\$gte]=$START_ISO&count=100000" -o devicestatus.json
curl -s "$BASE/profile.json"                                                         -o profile.json
```

`status.json` reported `authDefaultRoles: "readable"`, confirming public read access,
so no API/read token was needed.

## Reproduce the analysis

```bash
python3 analyze.py
```

The script transparently reads either `*.json` or `*.json.gz`.

## Notes

- CGM has two overlapping sources (`share2` + native `Dexcom G6`); the script
  de-duplicates to 5-minute mean buckets before computing statistics.
- Timezone is `ETC/GMT+7` → local time = **UTC−7** (Arizona/MST). Entries are stored
  in UTC; the script shifts by −7h for any time-of-day analysis.
- **Not medical advice** — observational patterns only.
