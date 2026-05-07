from sklearn.datasets import fetch_california_housing
import pandas as pd
from sklearn.model_selection import train_test_split
from typing import List, Tuple


class LocalDataLoader:
    FEATURE_COLS = [
        "MedInc", "HouseAge", "AveRooms", "AveBedrms",
        "Population", "AveOccup", "Latitude", "Longitude",
    ]
    TARGET_COL = "MedHouseVal"

    def load(self) -> pd.DataFrame:
        data = fetch_california_housing(as_frame=True)
        return data.frame

    def get_feature_names(self) -> List[str]:
        return self.FEATURE_COLS

    def split(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
        X = df[self.FEATURE_COLS]
        y = df[self.TARGET_COL]
        return train_test_split(X, y, test_size=test_size, random_state=random_state)
