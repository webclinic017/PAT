from __future__ import annotations
from typing import List, Dict, Tuple 
import logging
import pandas as pd
import uuid
import matplotlib.pyplot as plt

from beasttrader.indicators import IndicatorConfig, IndicatorMapping, aggregate_indicator_mappings
from beasttrader.strategy import StrategySet, StrategyConfig
from beasttrader.market_data import CandleData
from beasttrader.exchange import SimulatedStockBrokerCandleData, SlippageModels, AccountSet, Account
from beasttrader.performance_analysis import print_account_general_stats, get_best_strategy_and_account
from beasttrader.visualizations import plot_trade_profit_hist, plot_backtest_results, plot_cumulative_returns, plot_underwater, visual_analysis_of_trades
from beasttrader.backtest_tools import *


logger = logging.getLogger(__name__ )


# this is global so that we can make it once and then resuse it when doing consecutive backtests
master_data:CandleData = None       # all of the data
sim_data:CandleData = None          # all data that is valid for use

train_test_split_flag = False
train_data:CandleData = None
test_data:CandleData = None         # data that is used for testing


def get_training_start_end_dates() -> Tuple[pd.Timestamp, pd.Timestamp]:
    if train_test_split_flag:
        return train_data.start, train_data.end
    else:
        return sim_data.start, sim_data.end


def build_features(market_data:CandleData, indicator_mappings:List[IndicatorMapping]):
    """Builds the features for the backtest. This is a global function so that we can make it once and then resuse it when doing consecutive backtests"""
    # this is done to prevent calculation of the features for consecutive backtests (can be somewhat time consuming)
    global master_data
    global sim_data

    if master_data is None or master_data.df.index[0] != market_data.start or master_data.df.index[-1] != market_data.end:
        logger.debug('Computing features for backtest, overwriting global master_df')
        # the full dataframe with all candle data that we will build features on and then loop over
        master_df = market_data.df.copy()
        logger.debug(f'Building features for {len(master_df)} rows of data')
        # aggregate the indicator configs from all the algorithms and add them to the master_df
        master_indicator_config  = aggregate_indicator_mappings(indicator_mappings)
        for indicator_conf in master_indicator_config:
            indicator = indicator_conf.make(master_df)
            master_df = pd.concat([master_df, indicator], axis=1)
        logger.info(f'Built following indicators: {[config.names for config in master_indicator_config]}')
        logger.debug(f'Column names: {master_df.columns}')

        # df is the dataframe that we will loop over for the backtest. It is a subset of master_df
        # that has had the indicators warm up and is ready to be used for the backtest
        df = master_df.copy()
        # drop all rows with nan values in them (this is where the indicators are warming up)
        # for ts, row in df.iterrows():
        #     if not row.isnull().values.any():
        #         break
        # df = df.loc[ts:]
        logger.info(f'Backtest dataframe has {len(df)} rows of data. Starting at {df.index[0]} and ending at {df.index[-1]}')
        # now set up their data objects
        master_data = CandleData(market_data.resolution)
        master_data.add_data(master_df, market_data.tickers, suppress_cleaning_data=True)
        sim_data = CandleData(market_data.resolution)
        sim_data.add_data(df, market_data.tickers, suppress_cleaning_data=True)
    else:
        logger.critical(f'NOT BUILDING FEATURES.... WHY THOUGH?')


def set_train_test_true(fraction:float=0.8):
    global train_test_split_flag
    train_test_split_flag = True
    global train_data
    global test_data
    train_data, test_data = sim_data.split(fraction)


def optimize_backtest(
    market_data:CandleData,
    algorithm_configs:List[StrategyConfig],
    slippage_model:SlippageModels=None,
    data_split_fraction:float = 0.8,
    verbose:bool = False,
    plot:bool = False,
    log_level:int = logging.WARNING) -> SimulationResultSet:

    """Backtest a set of algorithms on a set of market data

    Args:
        market_data (CandleData): [description]
        algorithm_configs (List[StrategyConfig]): [description]
        SlippageModel (SlippageModels, optional): [description]. Defaults to None.
        verbose (bool, optional): [description]. Defaults to False.
        plot (bool, optional): [description]. Defaults to False.
        log_level (int, optional): [description]. Defaults to logging.WARNING.

    Returns:
        SimulationResultSet: [description]
    """

    # check to see if different algorithms have different indicator configurations (this is an optimization)
    indicator_mappings:List[IndicatorMapping] = [a.indicator_mapping for a in algorithm_configs]
    # if len(set(indicator_mappings)) > 1:
    if False:
        print(f'detected multiple unique mappings: {indicator_mappings}')
        compute_state_for_each_strategy = True
    else: compute_state_for_each_strategy = False    

    # build the features
    build_features(market_data, [s.indicator_mapping for s in algorithm_configs])

    # split the data
    train_data, test_data = market_data.split(data_split_fraction)

    # do your fancy training here

    # now test


    run_simulation_on_candle_data(
        test_data, 
        algorithm_configs, 
        slippage_model,
        compute_state_for_each_strategy=compute_state_for_each_strategy, 
        verbose=verbose, 
        plot=plot,
        log_level=log_level)


def backtest(
    market_data:CandleData,
    algorithm_configs:List[StrategyConfig],
    slippage_model:SlippageModels=None,
    verbose:bool = False,
    plot:bool = False,
    log_level:int = logging.WARNING) -> SimulationResultSet:

    """Backtest a set of algorithms on a set of market data

    Args:
        market_data (CandleData): [description]
        algorithm_configs (List[StrategyConfig]): [description]
        SlippageModel (SlippageModels, optional): [description]. Defaults to None.
        verbose (bool, optional): [description]. Defaults to False.
        plot (bool, optional): [description]. Defaults to False.
        log_level (int, optional): [description]. Defaults to logging.WARNING.

    Returns:
        SimulationResultSet: [description]
    """

    # check to see if different algorithms have different indicator configurations (this is an optimization)
    indicator_mappings:List[IndicatorMapping] = [a.indicator_mapping for a in algorithm_configs]
    # if len(set(indicator_mappings)) > 1:
    if False:
        print(f'detected multiple unique mappings: {indicator_mappings}')
        compute_state_for_each_strategy = True
    else: compute_state_for_each_strategy = False

    # build the features
    build_features(market_data, [s.indicator_mapping for s in algorithm_configs])
    global train_test_split_flag
    train_test_split_flag = False
    run_simulation_on_candle_data(
        algorithm_configs, 
        slippage_model,
        compute_state_for_each_strategy=compute_state_for_each_strategy, 
        verbose=verbose, 
        plot=plot,
        log_level=log_level)


def run_simulation_on_candle_data(
    algorithm_configs:List[StrategyConfig],
    slippage_model:SlippageModels|None=None,
    use_test_data:bool = False,
    compute_state_for_each_strategy:bool = True,
    verbose:bool=False,
    plot:bool=False,
    log_level=logging.WARNING) -> SimulationResultSet:

    logger.setLevel(log_level)

    # set up the data
    global train_test_split_flag
    if train_test_split_flag:
        if use_test_data:
            logger.debug(f'Using test data')
            global test_data
            data = test_data
        else:
            logger.debug(f'Using train data')
            global train_data
            data = train_data
    else:
        logger.debug(f'Using sim data')
        global sim_data
        data = sim_data

    brokerage = SimulatedStockBrokerCandleData()

    # add the market data to the brokerage
    assert isinstance(data, CandleData), f'Expected data to be a CandleData object, got {type(data)}'

    brokerage.set_expected_resolution(data.resolution)
    for t in data.tickers:
        # inform the brokerage that there is a new equity and to expect incoming candle_data about it 
        brokerage.add_ticker(t)

    if slippage_model is not None:
        logger.info(f'Using slippage model: {slippage_model} as dictacted by user')
        brokerage.set_slippage_model(slippage_model)
    elif data.resolution == TemporalResolution.MINUTE:
        logger.warning(f'Using minute resolution data. Slippage model is set to NEXT_CLOSE')
        brokerage.set_slippage_model(SlippageModels.NEXT_CLOSE)
    else:
        logger.info(f'The slippage model has been left at the default, {brokerage.slippage_model.name}')

    # set up the algorithms
    algorithms:StrategySet = {}
    accounts:Dict[uuid.UUID, Account] = {}
    # Instantiates a strategy to the brain and adds a matching account to the brokerage
    for algo_config in algorithm_configs:
        for _ in range(algo_config.quantity):
            account_num = uuid.uuid4()
            algorithms[account_num] = algo_config.instantiate(account_num)

            a = Account(account_num, 10000)
            logger.debug(f'Created account {str(account_num)[:8]} with ${a.cash:.2f}')
            accounts[account_num] = a

    def get_state(ind_mapping:IndicatorMapping, row:pd.Series) -> Dict[str, float]:
        feature_names = []
        for indicator_conf in ind_mapping:
            feature_names.extend(indicator_conf.names)
        # logger.debug(f'Getting state for {feature_names}')
        # logger.debug(f'Row: {row}')
        d = row[feature_names].to_dict()
        d['timestamp'] = row.name
        # for t in data.tickers:
        #     d[f'{t}_close'] = row[f'{t}_close']
        return d

    # Loop through the price history facilitating interaction between the algorithms and the brokerage
    # backtest with itterrows took: 20.058 s, using while loop took 19.1 s holding everything else constant
    for ts, row in data.df.iterrows():

        # submit orders to the brokerage and process them
        brokerage.set_prices(row)
        for acc_num in accounts.keys():
            a, s = accounts[acc_num], algorithms[acc_num]
            brokerage.process_orders_for_account(a)  # processes any pending orders
            a.value_history[ts] = brokerage.get_account_value(a)

        # generate new ordersn
        """This is broken out as a major efficiency upgrade for genetic algorithms where you need the same state hundreds of times for your population. Found that when state was 
        gotten for each strategy, backtesting for 1 day slowed from ~0.75 seconds to 20 seconds."""
        if compute_state_for_each_strategy:
            for acc_num, strategy in algorithms.items():
                logger.debug(f'Getting state for {strategy.indicator_mapping}')
                state = get_state(strategy.indicator_mapping, row)
                new_orders = strategy.act(account, state)
                if new_orders is not None:
                    accounts[acc_num].submit_new_orders(new_orders)
            
        else:   # get the mapping once from the first strategy is the set and use it for all the others
            logger.debug(f'Getting state for {list(algorithms.values())[0].indicator_mapping}')
            state = get_state(list(algorithms.values())[0].indicator_mapping, row)
            for acc_num in algorithms.keys():
                account, strategy = accounts[acc_num], algorithms[acc_num]
                new_orders = strategy.act(account, state)
                if new_orders is not None:
                    accounts[acc_num].submit_new_orders(new_orders)

        brokerage.clean_up()

    results:SimulationResultSet = []
    for account, strategy in zip(accounts.values(), algorithms.values()):
        res = SimulationResult(strategy, account, data.start, data.end, data.tickers, data.resolution)
        results.append(res)
    
    if verbose or plot:
        # find the best performing agent
        if len(results) > 1:
            best_strategy, best_account = get_best_strategy_and_account(results)
            print(F'Printing stats for the best performing strategy only: {best_strategy}')
        else: 
            best_strategy = results[0].strategy
            best_account = results[0].account

    df = data.df

    if verbose:
        print_account_general_stats(best_account, data)
    if plot:
        dt = data.end - data.start
        # if dt.days > 365:
        #     use_datetimes = True
        # else:
        #     use_datetimes = False
        use_datetimes = False
        # if 1:
        #     # create the nested indicators the strategy to provide insights in plotting
        #     for indicator_conf in best_strategy.indicator_mapping:
        #         if type(indicator_conf.target) == IndicatorConfig and all([n not in df.columns for n in indicator_conf.target.names]):
        #             s = indicator_conf.target.make(df)
        #             df = pd.concat([df, s], axis=1)
        plot_backtest_results(df, best_account, data.tickers, use_datetimes=use_datetimes, strategy_name=type(best_strategy).__name__)
        plot_underwater(best_account, use_datetimes=use_datetimes)
        plot_cumulative_returns(best_account, df, use_datetimes=use_datetimes)
        
        visual_analysis_of_trades(best_account, df)
        plt.show()
    
    return results

