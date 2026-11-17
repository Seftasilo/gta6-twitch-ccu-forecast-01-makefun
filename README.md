# GTA VI Twitch CCU forecast — make.fun entry

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Seftasilo/gta6-twitch-ccu-forecast-01-makefun/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Seftasilo/gta6-twitch-ccu-forecast-01-makefun/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts how many people watch Grand Theft Auto VI live on Twitch in each
hour of its release day (2026-11-19 UTC), from everything recorded up to
the end of the day's first hour, as five quantiles per hour.

## How it works

`main.py` (Python 3.13, standard library only, no network, deterministic)
reads every `*.in` case in `$MAKEFUN_INPUT_DIR` (default `/input`) and
writes one `<id>.out` per case to `$MAKEFUN_OUTPUT_DIR` (default `/output`).

Each case ships 40-odd past big-game launches ("comparables") with their
full release-day hourly Twitch curves. A launch's day shape depends
strongly on how big its first hour already is: launches that open huge
stay roughly flat, launches that open tiny explode later in the day as
timezones wake up. So for the target case the program takes the 8
comparable launches whose hour-1 print is closest in log space to the
target's hour-1 print, and forecasts each later hour as the target's
hour-1 print times the neighbours' mean log-ratio for that hour. The
spread for an hour is the neighbours' standard deviation of that
log-ratio, so the 5%/95% band is honest about how much launch shapes
disagree. Everything is computed at run time from the case file itself.

## Local validation

Leave-one-out over the 37 complete comparable launches in the kit
(predict each launch's release day from its hour-1 print, using the
other 36 launches):

| model | mean pinball loss | typical miss | 90% coverage |
|---|---|---|---|
| house baseline (flat at hour-1 print) | 0.930 | 213% | 0.624 |
| this entry (kNN k=8, mean log-ratio) | 0.416 | 90% | 0.881 |

Restricted to big launches (hour-1 print ≥ 100k viewers — the regime
GTA VI will almost surely be in): this entry 0.226 vs baseline 0.261.
The house baseline scores 0.387 on the four practice cases; this entry
is designed to beat it on the final by conditioning the day shape on
the opening hour's size instead of assuming the count stays flat.

## Run locally

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=kit/gta6-twitch-ccu-forecast-01-kit/input \
MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Each run takes well under a second per case; two runs on the same case
produce byte-identical output.

## Files

- `main.py` — the entry (the only program file)
- `LICENSE` — MIT, SPDX identifier on the first line
- `.makefun/owner.json` — payout wallet
