from collections import defaultdict
from pathlib import Path
from typing import Sequence

import numpy as np
import pandas as pd
from pandas.tseries.frequencies import to_offset
from pandas.tseries.offsets import BusinessHour


COLUMN_DTYPES = defaultdict(lambda x: np.float64)
COLUMN_DTYPES['volume'] = np.int32
COLUMN_INDEX_MAP = {
    2: 'open',
    3: 'high',
    4: 'low',
    5: 'close',
    6: 'volume'
}
DEFAULT_FREQ = '1Min'
DEFAULT_TIMEZONE = 'America/New_York'


def load_csv_data(csv_file: Path) -> pd.DataFrame:
    """ Loads OHLCV data from a CSV with columns [date, time, open, high, low,
        close, volume], resamples, and pads NaN values.
    """
    df = pd.read_csv(
        csv_file,
        header=None,
        index_col='timestamp',
        parse_dates={'timestamp': [0,1]},
        infer_datetime_format=True
    )
    df.rename(COLUMN_INDEX_MAP, axis='columns', inplace=True)
    df = df.tz_localize(DEFAULT_TIMEZONE, ambiguous='infer').tz_convert('UTC')
    df = upsample(df, DEFAULT_FREQ)
    df = df.astype(COLUMN_DTYPES)
    return df


def upsample(data: pd.DataFrame, freq: str) -> pd.DataFrame:
    data = data.resample(freq).fillna(None)
    data['volume'] = data['volume'].fillna(value=0)
    data['close'] = data['close'].fillna(method='ffill')
    for column in ['open', 'high', 'low']:
        data[column] = data[column].fillna(value=data['close'])
    return data


def downsample(data: pd.DataFrame, freq: str) -> pd.DataFrame:
    return data.resample(freq).agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
