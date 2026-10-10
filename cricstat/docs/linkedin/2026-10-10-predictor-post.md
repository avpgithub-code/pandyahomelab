# LinkedIn post — ODI World Cup 2027 predictor launch (2026-10-10)

Image: `2026-10-10-predictor-card.png` (1200 × 627, our own graphic; numbers from forecast as of 7 Oct 2026).

🏏 Who lifts the ODI World Cup in South Africa next November? My model's answer is live, and I'd love to hear yours.

Right now: India 23.2%, South Africa 19.6%, New Zealand 17.5%. South Africa ranks 4th on strength but is 2nd favourite, because most of their matches are at home.

pandyahomelab.com/cricket/predictor/

What's under the hood:
▸ Ratings: cricstat Elo, our own team rating built from every men's ODI since 2002 (not the ICC ranking). Settings tuned on 2,016 combinations, always on data from before the period being tested, so no peeking at the answers.
▸ Simulation: the tournament is played 50,000 times in the published 2027 format (Qualifier, Super Series, groups, Super 7, semis, final), with rain-offs at each host's measured rate and a year's worth of rating uncertainty.
▸ Backtests: on 900 ODIs since 2019, each predicted before it was played, it beats a simpler win-rate model and a coin flip (log loss 0.605 vs 0.662 vs 0.693), and it's well calibrated (slope 0.97: when it says 70%, about 70% happens). Before the 2019 World Cup, England (the eventual champions) were its top pick.
▸ MLOps: MLflow model registry with five promotion gates, a daily forecast after the data refresh, and approval-gated deploys to a home NAS.
▸ Fair by design: one model for every team, no hand adjustments. Cricsheet withholds Afghanistan's matches in protest over Afghan women's cricket, so their results come from a reviewed list, and that's disclosed on the page.
▸ Every number is explained on the methodology page: pandyahomelab.com/cricket/methodology/

Next: a machine-learning challenger that also sees squads, then a deep-learning model trained on 11.6 million deliveries. Whichever is best calibrated takes over the live forecast.

👇 Your turn: who's your pick for 2027, and does the model have it right? Comment below. And if you try the predictor, tap 👍 on the page or tell me what you'd add next. Every piece of feedback shapes the next release.

A statistical estimate for fun and learning, not betting advice.
The story behind it (2011, 2023 and the 2027 hope): https://lnkd.in/g255uDz4
#MachineLearning #MLOps #DataScience #Python #Cricket #CWC27
