"""Read-only access to data/db/forecast.sqlite (written by cricstat-models, P1).

Same contract as the serving DB: the models job writes forecast.sqlite.new, checks it and
os.replace()s it, so the file is opened immutable and reopened when its inode changes. A missing
file only makes the forecast endpoints answer 503; the rest of the API is unaffected.
"""
from db_logic.repository.db import ServingDB
from shared.exceptions import NoData, NoForecast


class ForecastDB(ServingDB):
    def conn(self):
        try:
            return super().conn()
        except NoData:
            raise NoForecast("no forecast yet (the predictor job hasn't written one)") from None
