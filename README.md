# makefun-gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Xutep/makefun-gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Xutep/makefun-gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Forecasts, hour by hour, how many people watch Grand Theft Auto VI live on Twitch on its release day (19 Nov 2026, UTC), from the first hour's viewer count. For each of hours 2–24 it writes five quantiles (5%, 25%, 50%, 75%, 95%) of that hour's concurrent viewers.

How it works: instead of one fixed curve, the forecaster reads the past big launches shipped inside each case (`comparables`) and, per hour, takes a similarity-weighted quantile of the log ratio ln(viewers_h / viewers_1) across them. A past launch counts more when its hour-1 count is close to this case's, when its hour-1 count stands in the same relation to its own pre-release peak, and when it is a console-only launch with a rolling midnight-local unlock like GTA VI. Tails are pulled 20% toward the median and the median is smoothed over neighbouring hours. Deterministic, standard library only, no network, no model calls.

Validation (leave-one-out over the 37 comparable launches in the kit): mean pinball loss 0.40 vs 0.93 for the flat house baseline; on the four GTA-like launches (console-only, rolling unlock, hour-1 ≥ 20,000) 0.18 vs 0.30 for the baseline. The house baseline scores 0.387 on the practice cases.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` case in the input directory and writes one `*.out` forecast per case to the output directory. With neither variable set it reads `/input` and writes `/output`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=ajkq5baq&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
