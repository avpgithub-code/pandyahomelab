---
title: I built a Cricket World Cup 2027 predictor on a home NAS, and backtested it honestly
published: false
description: Elo ratings, 50,000 tournament simulations and backtests on every men's ODI since 2019, running on a Celeron NAS with a pull-based CI/CD pipeline.
tags: machinelearning, python, datascience, mlops
---

The ODI Cricket World Cup 2027 starts in South Africa, Zimbabwe and Namibia in October 2027. I wanted to know who is likely to win, and I wanted a project that goes all the way from raw data to a live, public model. So I built **[cricstat](https://pandyahomelab.com/cricket/)**, a cricket statistics site with a **[World Cup 2027 predictor](https://pandyahomelab.com/cricket/predictor/)**, and it runs on a Synology NAS in my home.

This post covers the model, how I tested it, and the engineering around it, including the parts that didn't work out.

## The answer first

As of 14 October 2026, after 50,000 simulated tournaments:

| Team | cricstat Elo | Chance of winning |
|---|---|---|
| India | 1615 | 23.3% |
| South Africa | 1527 | 19.6% |
| New Zealand | 1588 | 17.5% |
| Australia | 1538 | 10.7% |
| Pakistan | 1521 | 8.7% |

South Africa has only the fourth-highest rating but is second favourite, because it plays most of its matches at home. That's the model doing its job, not a fan's bias: every team gets the same rules and there are no hand adjustments.

## The data

Everything comes from [Cricsheet](https://cricsheet.org), which publishes ball-by-ball data for about 23,000 matches as open data (ODC-BY). There's no API: you download zip files of JSON. A daily job on the NAS fetches the last 7 days of matches, upserts them by match ID, checks the data and only then swaps in the new database. If a check fails, the old database stays live and I get an email.

A few things I learned the hard way:

- **Match IDs aren't always numbers.** 25 of them look like `wi_...` (West Indies women's domestic games). Store IDs as text everywhere.
- **Every player statistic has to be derived** from the deliveries. Cricsheet gives you balls, not career averages, so I wrote a "golden figures" test set: known career numbers for real players that the build must reproduce.
- **Some data is deliberately missing.** Cricsheet withholds Afghanistan's men's matches in protest at how Afghan women's cricket has been treated. Afghanistan is in the 2027 World Cup, so the model uses a small reviewed list of 188 results from public sources for ratings only. The site explains this and links to Cricsheet's reasons.

Player names, birth dates and photos come from Wikidata and Wikimedia Commons (CC0 and credited free licences). That gives about 4,800 player pages and 176 team pages that search engines can read.

## The model: Elo, then simulation

The baseline is deliberately simple: an Elo rating for every men's ODI team, built from every match since 2002. After each match:

```python
expected_a = 1 / (1 + 10 ** (-(r_a - r_b + HOME * h) / 400))   # h = +1 home, -1 away, 0 neutral
r_a += K * margin_multiplier * (result_a - expected_a)       # win 1, tie 0.5, loss 0
```

The settings were chosen by grid search over 2,016 combinations, scored on log loss. Each backtest only used data from before the period it was tested on, so the model never saw the answers. The winners: K = 20, home advantage = 75 rating points, a margin-of-victory multiplier, and 5% regression toward the mean each 1 January.

Then the tournament itself is played 50,000 times in its published format: Qualifier, groups, Super 7, semi-finals and final. Each run also includes:

- **Rain:** each host's measured no-result rate (for example, 7.6% for ODIs in South Africa).
- **Uncertainty:** a random shift to every team's rating, sized from how much ratings really move over a year. A team rated 1615 today won't be exactly 1615 in a year, and pretending otherwise makes the odds too confident.

The simulation is vectorised numpy and takes seconds, even on a 4-core Celeron.

## Is it any good?

This is the part I cared about most. Before publishing, the model had to pass four automatic gates, all on matches it had never seen, plus a final sanity review by me where I wasn't allowed to change any number:

**1. Beat simple baselines on every men's ODI since 2019 (900 matches), each predicted before it was played.**

| Model | Log loss | Brier |
|---|---|---|
| Coin flip | 0.693 | 0.247 |
| Win rate (last 24 months + home/away) | 0.662 | 0.231 |
| **cricstat Elo** | **0.605** | **0.205** |

**2. Be calibrated:** when it says 70%, about 70% should happen. The calibration slope is 0.97 (1.0 is perfect). In the 0.7–0.8 bin, the average prediction was 75.0% and the favourites won 75.1% of 181 matches.

**3. Do at least as well as the win-rate model on real World Cup matches**, with ratings frozen the day before each tournament. On the 92 decided matches at the 2019 and 2023 World Cups it picked the winner 76% of the time; the win-rate model managed 62%.

**4. Replay check:** fed the real results of 2019 and 2023, the simulator must produce the real semi-finalists. It does.

And the result everyone asks about: before the 2019 World Cup, its top pick was **England (36%)**, who won. Before 2023, it had **India at 42%** and **Australia at 16%**. Australia won. Two tournaments prove very little either way, so the site reports them but doesn't use them as a gate.

## What it gets wrong

The [methodology page](https://pandyahomelab.com/cricket/methodology/) has a full "limits" section, but the main ones are:

- **It rates teams, not players.** It knows nothing about squads, injuries, retirements, the toss or the pitch. A team that rests its stars for a series looks weaker than it is.
- **It's weaker in 2026 so far:** 56% accuracy on 78 matches, against 69% over the whole test period. Small samples swing, but I'm watching it.
- **Net run rate isn't modelled**, because Elo doesn't predict margins. Teams level on points are split by wins, then at random. It barely changes the title odds, and the page says so.

That first limit is why the next step is a machine-learning challenger: gradient boosting on Elo difference, home advantage, form and squad strength built from the actual playing XIs. After that comes a deep-learning model trained on about 11.6 million deliveries. Whichever is best calibrated on the same backtests takes over the live forecast, and the comparison gets published either way.

## Running it on a NAS

The whole thing runs at home on a Synology NAS: Celeron J3455, 16 GB RAM, no GPU. One gotcha: the CPU has **no AVX**, so some prebuilt Python wheels crash with "illegal instruction" even though they install fine. Every image is now smoke-tested on the NAS itself, not just in CI.

The deploy pipeline:

- **CI (GitHub Actions):** lint, unit tests, metric-formula tests and schema tests on every push, then images built and pushed to GitHub Container Registry.
- **An approval gate** before anything is published.
- **Pull-based deploy:** a scheduled job on the NAS pulls the approved image, restarts the service, smoke-tests it and rolls back on failure. GitHub never needs a way into my network.
- **MLflow** logs every tuning run and backtest. The model registry only moves the "champion" alias when all four automatic gates pass.
- **A daily forecast** runs after the data refresh, so the odds move as teams play.

The site is served through a Cloudflare Tunnel, so there are no open ports at home. It sets no cookies and loads nothing from third parties.

## Try it

- Predictor: [pandyahomelab.com/cricket/predictor/](https://pandyahomelab.com/cricket/predictor/)
- How it works, with every number: [pandyahomelab.com/cricket/methodology/](https://pandyahomelab.com/cricket/methodology/)
- Code: [github.com/avpgithub-code/pandyahomelab](https://github.com/avpgithub-code/pandyahomelab) (cricstat is in `cricstat/`)

I'd like to hear what you'd add, or where you think the model is wrong. Comment here, or use the feedback button on the site.

_Match data from Cricsheet (cricsheet.org), used under the Open Data Commons Attribution License 1.0. Not affiliated with or endorsed by Cricsheet, the ICC or any cricket board. A statistical estimate for fun and learning, not betting advice._
