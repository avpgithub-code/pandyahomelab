"""How much would tuning on the test matches have flattered test A?

Scores the same matches three ways: settings re-tuned each year on earlier matches (published),
settings tuned once on all history (the leak), and the settings that score best on the test
matches themselves (the worst case). Read-only: it writes nothing, and it replays only the matches
in the published report, so the first row must equal that report's log loss.

    sudo docker run --rm -i --network none --user 0 -v "$PWD/cricstat/data":/data:ro \
      -e CRICSTAT_DATA_DIR=/data -e CRICSTAT_SERVING_DB=/data/db/cricstat.sqlite \
      --entrypoint python3 cricstat-models:latest - < cricstat/tools/tuning_leak_check.py
"""
import csv
import glob
import json
import os

from application_logic.models import elo
from application_logic.services import backtest_service as bt, data_service
from shared.config import Config

cfg = Config()
report_dir = sorted(glob.glob(os.path.join(cfg.REPORT_DIR, "backtest-*")))[-1]
with open(os.path.join(report_dir, "report.json"), encoding="utf-8") as f:
    published = json.load(f)
with open(os.path.join(report_dir, "test_a_predictions.csv"), encoding="utf-8") as f:
    test_keys = {r["match_key"] for r in csv.DictReader(f)}

rows, _ = data_service.load_matches(cfg)
rows = [r for r in rows if r["start_date"] <= published["data"]["data_as_of"]]
members = bt.full_members(cfg.FULL_MEMBERS)

# Results that reached the database after the report are left out, so the replay matches it.
compiled = elo.compile_matches(rows, members)
replayed, _, _ = elo.run(compiled, elo.EloParams(20, 75, True, 0.05, 400))
late = {compiled.matches[i].key for i, _ in replayed
        if compiled.matches[i].date >= bt.TEST_FROM} - test_keys
rows = [r for r in rows if r["match_key"] not in late]
grid = bt.Grid(elo.compile_matches(rows, members))

test = [j for j, d in enumerate(grid.dates) if d >= bt.TEST_FROM]
years = sorted({grid.dates[j][:4] for j in test})


def score(pred, idx):
    return (sum(bt._ll(pred[j], grid.ys[j]) for j in idx) / len(idx),
            sum((pred[j] - grid.ys[j]) ** 2 for j in idx) / len(idx))


walk = {}
for year in years:
    g = grid.best(year + "-01-01")[0]
    walk.update({j: grid.probs[g][j] for j in test if grid.dates[j][:4] == year})
all_history = grid.best("9999-01-01")[0]
oracle = min(range(len(grid.params)), key=lambda g: score(grid.probs[g], test)[0])
fixed = {j: grid.probs[all_history][j] for j in test}
best = {j: grid.probs[oracle][j] for j in test}

gaps = [bt._ll(walk[j], grid.ys[j]) - bt._ll(fixed[j], grid.ys[j]) for j in test]
mean = sum(gaps) / len(gaps)
se = (sum((x - mean) ** 2 for x in gaps) / (len(gaps) - 1) / len(gaps)) ** 0.5

print("report %s, %d matches" % (os.path.basename(report_dir), len(test)))
print("re-tuned each year  log loss %.5f  Brier %.5f" % score(walk, test))
print("tuned on all history log loss %.5f  Brier %.5f  %s" % (score(fixed, test) + (grid.params[all_history],)))
print("best on test matches log loss %.5f  Brier %.5f  %s" % (score(best, test) + (grid.params[oracle],)))
print("gap to all history %.5f (standard error %.5f)" % (mean, se))
for year in years:
    idx = [j for j in test if grid.dates[j][:4] == year]
    print(year, len(idx), "%.5f %.5f" % (score(walk, idx)[0], score(fixed, idx)[0]))
