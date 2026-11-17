"""Hour-by-hour Twitch forecast for a big console launch day.

Idea
----
A launch's Twitch audience on its release day does not stay flat: it dips
in the small hours, then climbs as each region's midnight unlock arrives
(US east coast at 05:00 UTC, west coast at 08:00 UTC), peaks in the
late afternoon / evening UTC when the US is awake and Europe is home,
and eases off late at night.  How steep that climb is depends on the
launch: a game whose category was already busy before release (early
access, preload streams, a long hype tail) starts high in hour 1 and
moves modestly, while a game whose category was dead before release
explodes from a tiny hour 1.

This program therefore does not use one fixed curve.  For each case it
reads the `comparables` shipped inside the case file -- past big
launches with their full hourly curves -- and, for every forecast hour,
takes a similarity-weighted quantile of the log ratio
ln(viewers_h / viewers_1) across those launches.  A comparable counts
more when it resembles this case:

* its hour-1 count is close to this case's hour-1 count (log scale),
* its hour-1 count stands in the same relation to its own pre-release
  peak as this case's hour-1 count does to its pre-release peak
  (a launch already past its first wave vs. a fresh explosion),
* it is a console-only launch with a rolling midnight-local unlock,
  like this game (PS5 / Xbox Series, no PC at launch).

The weighted 5 / 25 / 50 / 75 / 95 percent quantiles of the log ratio
become this hour's five quantiles, anchored on the case's hour-1 print.
Tails are pulled 20% toward the median (the raw cross-launch spread
is wider than any single launch's plausible range) and the median is
smoothed over neighbouring hours so the curve cannot jump hour to hour
on sampling noise.  Everything is deterministic: no randomness, no
clock, no network, standard library only.
"""

import json
import math
import os
from datetime import datetime, timedelta

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
NORMAL_Z = (-1.6448536269514722, -0.6744897501960817, 0.0,
            0.6744897501960817, 1.6448536269514722)
HOURS = list(range(2, 25))

# Similarity kernel widths (in log units) and match bonuses.
LOG_COUNT_WIDTH = 1.0
LOG_PREPEAK_WIDTH = 1.0
CONSOLE_MATCH = 1.6
CONSOLE_MISMATCH = 0.625
ROLLING_MATCH = 1.4
ROLLING_MISMATCH = 1.0 / 1.4
TAIL_SHRINK = 0.8
BASELINE_SPREAD = 0.15


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def weighted_quantile(pairs, level):
    """Smallest value whose cumulative weight reaches `level` of the total."""
    ordered = sorted(pairs)
    total = sum(w for _, w in ordered)
    if total <= 0:
        return ordered[len(ordered) // 2][0]
    running = 0.0
    for value, weight in ordered:
        running += weight
        if running >= level * total:
            return value
    return ordered[-1][0]


def launch_features(day_start, hourly, platforms, unlock):
    """Features of one launch, from its hourly viewer series."""
    first = hourly.get(day_start)
    if not first or first <= 0:
        return None
    before = [v for t, v in hourly.items()
              if day_start - timedelta(hours=24) <= t < day_start and v > 0]
    peak_before = max(before) if before else 0
    text = (platforms or "").upper()
    return {
        "first": first,
        "pre_ratio": (first / peak_before) if peak_before else None,
        "console_only": "PC" not in text,
        "rolling": "midnight local" in (unlock or "").lower(),
    }


def similarity(target, other):
    """How much one past launch should count for this case (0..~3)."""
    weight = 1.0
    if other["first"] and target["first"]:
        gap = math.log(other["first"]) - math.log(target["first"])
        weight *= math.exp(-0.5 * (gap / LOG_COUNT_WIDTH) ** 2)
    if other["pre_ratio"] and target["pre_ratio"]:
        gap = math.log(other["pre_ratio"]) - math.log(target["pre_ratio"])
        weight *= math.exp(-0.5 * (gap / LOG_PREPEAK_WIDTH) ** 2)
    if other["console_only"] == target["console_only"]:
        weight *= CONSOLE_MATCH
    else:
        weight *= CONSOLE_MISMATCH
    if other["rolling"] == target["rolling"]:
        weight *= ROLLING_MATCH
    else:
        weight *= ROLLING_MISMATCH
    return weight


def baseline_quantiles(hour):
    """The flat house shape: median at hour 1, spread widening with time."""
    spread = BASELINE_SPREAD * math.sqrt(hour - 1)
    return [z * spread for z in NORMAL_Z]


def forecast_case(case):
    known = case.get("known") or []
    first_print = max(known[0].get("viewers", 0), 1) if known else 1

    day_start = parse_time(case["day_start"])
    hourly_before = {}
    for row in case.get("history_hourly") or []:
        try:
            hourly_before[parse_time(row["from"])] = row.get("viewers", 0)
        except (KeyError, ValueError):
            continue
    recent = [v for t, v in hourly_before.items()
              if day_start - timedelta(hours=24) <= t < day_start and v > 0]
    peak_before = max(recent) if recent else 0

    # This game: console-only, rolling midnight-local unlock.
    target = {
        "first": first_print,
        "pre_ratio": (first_print / peak_before) if peak_before else None,
        "console_only": True,
        "rolling": True,
    }

    # Log-ratio series of every comparable launch, weighted by similarity.
    series = []  # (weight, {hour: log ratio})
    for other in case.get("comparables") or []:
        if "Grand Theft Auto VI" in (other.get("name") or ""):
            continue  # the target's own pre-release history, not a launch
        hourly = {}
        for row in other.get("hourly") or []:
            try:
                hourly[parse_time(row["from"])] = row.get("viewers", 0)
            except (KeyError, ValueError):
                continue
        start = parse_time(other["day_start"])
        features = launch_features(start, hourly,
                                   other.get("platforms"), other.get("unlock"))
        if features is None:
            continue
        ratios = {}
        for hour in HOURS:
            value = hourly.get(start + timedelta(hours=hour - 1))
            if value and value > 0:
                ratios[hour] = math.log(value / features["first"])
        if len(ratios) < 12:
            continue
        series.append((similarity(target, features), ratios))

    rows = []
    medians = {}
    for hour in HOURS:
        pairs = [(ratios[hour], weight) for weight, ratios in series
                 if hour in ratios and weight > 0]
        if len(pairs) >= 3:
            quantiles = [weighted_quantile(pairs, level) for level in LEVELS]
        else:
            quantiles = baseline_quantiles(hour)
        median = quantiles[2]
        quantiles = [median + (q - median) * TAIL_SHRINK for q in quantiles]
        medians[hour] = median
        rows.append([hour, quantiles])

    # Smooth the median over neighbouring hours; carry the whole band.
    smoothed = {}
    for index, hour in enumerate(HOURS):
        neighbours = [medians[HOURS[j]] for j in range(max(0, index - 1),
                                                       min(len(HOURS), index + 2))]
        smoothed[hour] = sum(neighbours) / len(neighbours)
    out_rows = []
    for hour, quantiles in rows:
        shift = smoothed[hour] - quantiles[2]
        band = [quantiles[i] + shift for i in range(5)]
        band = sorted(max(-9.0, min(9.0, q)) for q in band)
        values = []
        for q in band:
            viewers = first_print * math.exp(q)
            viewers = max(1.0, min(1_000_000_000.0, viewers))
            values.append(round(viewers, 2))
        # Keep the five quantiles non-decreasing after rounding.
        for i in range(1, 5):
            values[i] = max(values[i], values[i - 1])
        out_rows.append({"hour": hour, "q": values})
    return {"hours": out_rows}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(output_dir, exist_ok=True)
    for name in sorted(os.listdir(input_dir)):
        if not name.endswith(".in"):
            continue
        with open(os.path.join(input_dir, name), "r", encoding="utf-8") as handle:
            case = json.load(handle)
        result = forecast_case(case)
        out_name = name[:-3] + ".out"
        with open(os.path.join(output_dir, out_name), "w",
                  encoding="utf-8") as handle:
            json.dump(result, handle, separators=(",", ":"))


if __name__ == "__main__":
    main()
