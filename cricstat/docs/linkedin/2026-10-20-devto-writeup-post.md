# LinkedIn post — dev.to write-up of the predictor (2026-10-20)

Link card: the dev.to article (its cover image becomes the card). No separate image.

---

How do you know if a prediction model is any good? You test it on matches it has never seen.

I wrote up how I built and tested my Cricket World Cup 2027 predictor, including the parts it gets wrong:

▸ cricstat Elo ratings from every men's ODI, then the tournament simulated 50,000 times
▸ Backtested on 900 ODIs since 2019, each predicted before it was played: log loss 0.605 vs 0.662 for a simpler model and 0.693 for a coin flip
▸ Calibrated: when it says 75%, the favourite won 75% of the time
▸ Honest limits: it rates teams, not players, and it's been weaker in 2026 so far
▸ All of it runs on a home NAS, with CI/CD, MLflow promotion gates and a daily forecast

Next: a machine-learning challenger that sees squads. Whichever model is better calibrated takes over.

Full write-up on DEV 👇
https://dev.to/architpandya/i-built-a-cricket-world-cup-2027-predictor-on-a-home-nas-and-backtested-it-honestly-38l0

Who's your pick for 2027? And if you build models: how do you backtest yours?

#MachineLearning #MLOps #DataScience #Python #Cricket #CWC27
