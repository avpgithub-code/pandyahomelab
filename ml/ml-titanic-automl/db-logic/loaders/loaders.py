import os
import seaborn as sns
import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split


class LocalDataLoader:
    TABLE_NAME = "titanic"
    FEATURE_COLS = ["pclass", "sex", "age", "sibsp", "parch", "fare", "embarked"]
    TARGET_COL = "survived"

    def __init__(self):
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://postgres:ml_postgres_dev_password@ml-postgres:5432/mldb"
        )
        self._engine = create_engine(db_url)

    def load(self) -> pd.DataFrame:
        if self._table_exists():
            return pd.read_sql(f"SELECT * FROM {self.TABLE_NAME}", self._engine)
        return self._download_and_persist()

    def _download_and_persist(self) -> pd.DataFrame:
        df = sns.load_dataset("titanic")
        df = self._clean(df)
        df.to_sql(self.TABLE_NAME, self._engine, if_exists="replace", index=False)
        return df

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df[self.FEATURE_COLS + [self.TARGET_COL]].copy()
        df["age"] = df["age"].fillna(df["age"].median())
        df["fare"] = df["fare"].fillna(df["fare"].median())
        df["embarked"] = df["embarked"].fillna("S")
        df = df.dropna()
        return df

    def _table_exists(self) -> bool:
        with self._engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables "
                "WHERE table_name = :t)"
            ), {"t": self.TABLE_NAME})
            return result.scalar()

    def get_feature_names(self):
        return self.FEATURE_COLS

    def split(self, df, test_size=0.2, random_state=42):
        X = df[self.FEATURE_COLS]
        y = df[self.TARGET_COL]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)
