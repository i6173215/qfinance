import io
from pathlib import Path
from typing import Iterable, Tuple, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec

from environment.dataset_utils import load_csv_data


class QFinanceEnvironment(object):
    actions = ['buy', 'sell', 'hold']

    def __init__(self,
                 ohlc_data: pd.DataFrame,
                 fee: float,
                 validation_percent: float,
                 n_folds: int,
                 replay_memory_start_size: int):
        self._full_data = ohlc_data
        self._current_state = 0
        self._current_position = None
        self._indicators = []

        self.fee = fee
        self.validation_percent = validation_percent
        self.n_folds = n_folds
        self.replay_memory_start_size = replay_memory_start_size

        self._orders = pd.DataFrame(columns=['timestamp', 'buy', 'sell'])
        self._orders.set_index('timestamp', inplace=True)

        total_length = len(self._full_data) - replay_memory_start_size
        train_percent_ratio = (1-self.validation_percent) / self.validation_percent
        self.fold_validation_length = int(total_length / (n_folds + train_percent_ratio))
        self.fold_train_length = int(self.fold_validation_length * train_percent_ratio)

    @classmethod
    def from_csv(cls, csv_path: str, **params):
        df = load_csv_data(Path(csv_path), upsample=False)
        return cls(df, **params)

    def replay_memories(self) -> pd.DataFrame:
        for _ in range(self.replay_memory_start_size):
            yield self.state

    def training_slices(self, epochs: int) -> Iterable[Tuple[Iterable, Iterable]]:
        for fold_i in range(self.n_folds):
            slice_start = fold_i * self.fold_validation_length
            def slice_epochs():
                for _ in range(epochs):
                    self._current_state = slice_start
                    yield ((self.state for _ in range(self.fold_train_length)),
                           (self.state for _ in range(self.fold_validation_length)))
            yield slice_epochs()

    def step(self, action_idx: int, track_orders: bool = False) -> float:
        action = self.actions[action_idx]
        start_state = self._full_data.iloc[self._current_state]
        self._next()
        end_state = self._full_data.iloc[self._current_state]

        if action == 'buy':
            if self._current_position is None:
                self._current_position == 'long'
                if track_orders:
                    self._orders[self.current_timestamp]['buy'] = self.last_price
                return self.period_return - self.fee
            if self._current_position == 'long':
                return self.period_return

        if action == 'sell':
            if self._current_position is None:
                return 0
            if self._current_position == 'long':
                if track_orders:
                    self._orders.iloc[-1]['sell'] = start_state['close']
                return -self.fee

        if action == 'hold':
            if self._current_position is None:
                return 0
            if self._current_position == 'long':
                return self.period_return

    @property
    def period_return(self):
        if self._current_state == 0:
            raise ValueError('Cannot calculate return in state 0')
        return (self._full_data.iloc[self._current_state]['close'] /
                self._full_data.iloc[self._current_state-1]['close']) - 1.0

    def order_returns(self):
        return self._orders['sell'] / self._orders['buy'] - 1.

    def plot(self,
             data_column: str = 'close',
             plot_indicators: bool = False,
             plot_orders: bool = True,
             save_to: Union[str, io.BufferedIOBase] = None) -> None:
        fig = plt.figure(figsize=(60, 30))
        ratios = [3] if not plot_indicators else [3] + ([1] * len(self._indicators))
        n_subplots = 1 if not plot_indicators else 1 + len(self._indicators)
        gs = gridspec.GridSpec(n_subplots, 1, height_ratios=ratios)

        # Plot long and short positions
        ax0 = fig.add_subplot(gs[0])
        ax0.set_title('Price ({})'.format(data_column))
        ax0.plot(self._data.index, self._data[data_column], 'black')

        if plot_orders:
            all_nan = self._orders.isnull().all(axis=0)
            if not all_nan['buy']:
                ax0.plot(self._orders.index, self._orders['buy'], color='k', marker='^', fillstyle='none')
            if not all_nan['sell']:
                ax0.plot(self._orders.index, self._orders['sell'], color='k', marker='v', fillstyle='none')

        if plot_indicators:
            for i, indicator in enumerate(self._indicators, start=1):
                ax_ind = fig.add_subplot(gs[i])
                indicator.plot(ax_ind)

        fig.autofmt_xdate()
        plt.tight_layout()

        if save_to:
            fig.savefig(save_to, format='png')
        else:
            plt.show()

    @property
    def state(self) -> np.ndarray:
        return self._full_data.iloc[self._current_state].values

    @property
    def n_state_factors(self) -> int:
        return len(self._full_data.iloc[0])

    @property
    def n_actions(self) -> int:
        return len(self.actions)

    def total_train_steps(self, epochs: int) -> int:
        return self.fold_train_length * self.n_folds * epochs

    @property
    def current_timestamp(self):
        return self._full_data.iloc[self._current_state]['timestamp']

    @property
    def last_price(self) -> float:
        return self._full_data.iloc[self._current_state]['close']

    def _next(self):
        self._current_state += 1
