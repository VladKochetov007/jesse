# silent (pandas) warnings
import warnings
from typing import List, Any, Union, Dict, Optional

import numpy as np
import pandas as pd
from peewee import CharField, FloatField

import jesse.helpers as jh
from jesse.config import config
from jesse.routes import router
from jesse.services import metrics as stats
from jesse.services import selectors
from jesse.services.candle import is_bullish
from jesse.store import store
from jesse.models import Position

warnings.filterwarnings("ignore")


def positions() -> list:
    arr = []

    for r in router.routes:
        p: Position = r.strategy.position
        arr.append({
            'type': p.type,
            'strategy_name': p.strategy.name,
            'symbol': p.symbol,
            'leverage': p.leverage,
            'opened_at': p.opened_at,
            'qty': p.qty,
            'entry': p.entry_price,
            'current_price': p.current_price,
            'liq_price': p.liquidation_price,
            'pnl': p.pnl,
            'pnl_perc': p.pnl_percentage
        })

    return arr


def candles() -> dict:
    arr = {}
    candle_keys = []

    # add routes
    for e in router.routes:
        if e.strategy is None:
            return

        candle_keys.append({
            'exchange': e.exchange,
            'symbol': e.symbol,
            'timeframe': e.timeframe
        })

    # add extra_routes
    for e in router.extra_candles:
        candle_keys.append({
            'exchange': e[0],
            'symbol': e[1],
            'timeframe': e[2]
        })

    for k in candle_keys:
        try:
            c = store.candles.get_current_candle(k['exchange'], k['symbol'], k['timeframe'])
            key = jh.key(k['exchange'], k['symbol'], k['timeframe'])
            arr[key] = {
                'time': int(c[0] / 1000),
                'open': c[1],
                'close': c[2],
                'high': c[3],
                'low': c[4],
                'volume': c[5],
            }
        except IndexError:
            return
        except Exception:
            raise

    return arr


def livetrade():
    # TODO: for now, we assume that we trade on one exchange only. Later, we need to support for more than one exchange at a time
    # sum up balance of all trading exchanges
    starting_balance = 0
    current_balance = 0
    for e in store.exchanges.storage:
        starting_balance += store.exchanges.storage[e].starting_assets[jh.app_currency()]
        current_balance += store.exchanges.storage[e].assets[jh.app_currency()]
    starting_balance = round(starting_balance, 2)
    current_balance = round(current_balance, 2)

    # short trades summary
    if len(store.completed_trades.trades):
        df = pd.DataFrame.from_records([t.to_dict() for t in store.completed_trades.trades])
        total = len(df)
        winning_trades = len(df.loc[df['PNL'] > 0])
        losing_trades = len(df.loc[df['PNL'] < 0])
        pnl = round(df['PNL'].sum(), 2)
        pnl_perc = round((pnl / starting_balance) * 100, 2)
    else:
        pnl, pnl_perc, total, winning_trades, losing_trades = 0, 0, 0, 0, 0

    return {
        'started_at': str(store.app.starting_time),
        'current_time': str(jh.now_to_timestamp()),
        'started_balance': str(starting_balance),
        'current_balance': str(current_balance),
        'debug_mode': str(config['app']['debug_mode']),
        'count_error_logs': str(len(store.logs.errors)),
        'count_info_logs': str(len(store.logs.info)),
        'count_active_orders': str(store.orders.count_all_active_orders()),
        'open_positions': str(store.positions.count_open_positions()),
        'pnl': str(pnl),
        'pnl_perc': str(pnl_perc),
        'count_trades': str(total),
        'count_winning_trades': str(winning_trades),
        'count_losing_trades': str(losing_trades),
    }


def portfolio_metrics() -> dict:
    return stats.trades(store.completed_trades.trades, store.app.daily_balance)


def info() -> List[List[Union[str, Any]]]:
    array = []

    for w in store.logs.info[::-1][0:5]:
        array.append(
            [
                jh.timestamp_to_time(w['time'])[11:19],
                f"{w['message'][:70]}.." if len(w['message']) > 70 else w['message']
            ])
    return array


def watch_list() -> Optional[Any]:
    # only support one route
    if len(router.routes) > 1:
        return None

    strategy = router.routes[0].strategy

    # don't if the strategy hasn't been initiated yet
    if not store.candles.are_all_initiated:
        return None

    watch_list_array = strategy.watch_list()

    return watch_list_array if len(watch_list_array) else None


def errors() -> List[List[Union[str, Any]]]:
    array = []

    for w in store.logs.errors[::-1][0:5]:
        array.append([jh.timestamp_to_time(w['time'])[11:19],
                      f"{w['message'][:70]}.." if len(w['message']) > 70 else w['message']])
    return array


def orders():
    arr = []

    route_orders = []
    for r in router.routes:
        r_orders = store.orders.get_orders(r.exchange, r.symbol)
        for o in r_orders:
            route_orders.append(o)

    if not len(route_orders):
        return []

    route_orders.sort(key=lambda x: x.created_at, reverse=False)

    for o in route_orders[::-1][0:5]:
        arr.append({
            'symbol': o.symbol,
            'side': o.side,
            'type': o.type,
            'qty': o.qty,
            'price': o.price,
            'flag': o.flag,
            'status': o.status,
            'created_at': o.created_at,
            'canceled_at': o.canceled_at,
            'executed_at': o.executed_at,
        })

    return arr
