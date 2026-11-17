"""Forecast GTA VI launch-day Twitch viewers, hour by hour.

Reads every ``*.in`` case in $MAKEFUN_INPUT_DIR (default /input) and writes
one ``<id>.out`` forecast per case to $MAKEFUN_OUTPUT_DIR (default /output).

Method (stdlib only, deterministic, no network):
  Each case ships 40-odd past big-game launches ("comparables") with their
  full release-day hourly Twitch curves.  A launch's day shape depends
  strongly on how big its first hour already is: launches that open huge
  stay roughly flat, launches that open tiny explode later in the day as
  timezones wake up.  So for the target case we take the k = 8 comparable
  launches whose hour-1 print is closest in log space to the target's
  hour-1 print, and forecast each later hour as the target's hour-1 print
  times the neighbours' mean log-ratio for that hour.  The spread for an
  hour is the neighbours' standard deviation of that log-ratio, so the
  5%/95% band is honest about how much launch shapes disagree.
  Everything is computed at run time from the case file itself, so the
  same program works on the practice cases and on the final case.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

Z_VALUES = (-1.645, -0.674, 0.0, 0.674, 1.645)
K_NEIGHBOURS = 8
MIN_SPREAD = 0.15
MAX_SPREAD = 1.5
MAX_VIEWERS = 1_000_000_000


def parse_time(text):
    """Parse an ISO-8601 UTC timestamp like 2026-11-19T00:00:00Z."""
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def hour_of(row_time, day_start):
    """UTC hour index (1..24) of a timestamp inside the release day."""
    delta = (row_time - day_start).total_seconds() / 3600.0
    if 0.0 <= delta < 24.0:
        return int(delta) + 1
    return None


def extract_curve(comparable):
    """Return {hour: viewers} for hours 1..24 of a comparable's release day.

    Returns None when the launch lacks a usable hour-1 print or any hour
    of the day (e.g. the target game's own pre-release history, whose
    release day has not happened yet).
    """
    try:
        day_start = parse_time(comparable["day_start"])
    except (KeyError, TypeError, ValueError):
        return None
    by_hour = {}
    for row in comparable.get("hourly") or []:
        try:
            when = parse_time(row["from"])
            viewers = float(row["viewers"])
        except (KeyError, TypeError, ValueError):
            continue
        hour = hour_of(when, day_start)
        if hour is not None and hour not in by_hour:
            by_hour[hour] = max(viewers, 1.0)
    if len(by_hour) != 24:
        return None
    if by_hour[1] < 1.0:
        return None
    return by_hour


def baseline_quantiles(p1, hour):
    """House-style flat forecast, used only when no comparables exist."""
    spread = 0.15 * math.sqrt(hour - 1)
    return [
        round(max(1.0, p1 * math.exp(z * spread)), 2) for z in Z_VALUES
    ]


def forecast_case(case):
    """Return the {"hours": [...]} forecast object for one case."""
    known = case.get("known") or []
    p1 = None
    if known:
        try:
            p1 = float(known[0]["viewers"])
        except (KeyError, TypeError, ValueError):
            p1 = None
    if p1 is None or p1 < 1.0:
        p1 = 1.0

    # Collect usable comparable release-day curves, deduplicated by name.
    seen = set()
    curves = []
    for comp in case.get("comparables") or []:
        name = comp.get("name")
        if name in seen:
            continue
        seen.add(name)
        curve = extract_curve(comp)
        if curve is not None:
            curves.append(curve)

    hours = []
    if not curves:
        for hour in range(2, 25):
            hours.append({"hour": hour, "q": baseline_quantiles(p1, hour)})
        return {"hours": hours}

    log_p1 = math.log(p1)
    neighbours = sorted(
        curves, key=lambda c: abs(math.log(c[1]) - log_p1)
    )[:K_NEIGHBOURS]

    for hour in range(2, 25):
        log_ratios = [
            math.log(c[hour] / c[1]) for c in neighbours
        ]
        centre = sum(log_ratios) / len(log_ratios)
        if len(log_ratios) > 1:
            mean = centre
            variance = sum((x - mean) ** 2 for x in log_ratios) / len(
                log_ratios
            )
            spread = math.sqrt(variance)
        else:
            spread = MIN_SPREAD
        spread = min(max(spread, MIN_SPREAD), MAX_SPREAD)
        quantiles = []
        for z in Z_VALUES:
            value = p1 * math.exp(centre + z * spread)
            value = min(max(value, 1.0), MAX_VIEWERS)
            quantiles.append(round(value, 2))
        # Enforce non-decreasing quantiles after rounding.
        for i in range(1, len(quantiles)):
            if quantiles[i] < quantiles[i - 1]:
                quantiles[i] = quantiles[i - 1]
        hours.append({"hour": hour, "q": quantiles})
    return {"hours": hours}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(output_dir, exist_ok=True)

    case_files = sorted(
        name for name in os.listdir(input_dir) if name.endswith(".in")
    )
    for name in case_files:
        case_id = name[:-3]
        out_path = os.path.join(output_dir, case_id + ".out")
        try:
            with open(os.path.join(input_dir, name), "r", encoding="utf-8") as fh:
                case = json.load(fh)
            forecast = forecast_case(case)
        except Exception:
            # Never leave a case without a valid-shaped output: fall back
            # to a flat forecast at the best-effort hour-1 print (1 if
            # even that cannot be read). A weak forecast still beats an
            # invalid case, which scores as if every quantile were the
            # hour-1 print and forfeits any prize.
            p1 = 1.0
            try:
                with open(os.path.join(input_dir, name), "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                p1 = max(float((raw.get("known") or [{}])[0].get("viewers", 1) or 1), 1.0)
            except Exception:
                pass
            forecast = {
                "hours": [
                    {"hour": h, "q": baseline_quantiles(p1, h)}
                    for h in range(2, 25)
                ]
            }
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(forecast, fh, separators=(",", ":"))
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
