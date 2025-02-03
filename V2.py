from AlgorithmImports import *
from collections import deque

class Trading_Strategy(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2022, 1, 1)
        self.set_cash(100000)
        self.symbol = self.add_cfd("WTICOUSD", Resolution.HOUR).symbol

        # Indicators - Hourly timeframe
        self._macd = self.macd(self.symbol, 12, 30, 9, Resolution.HOUR)  
        self._sma = self.sma(self.symbol, 30, Resolution.HOUR)
        self._adx = self.adx(self.symbol, 30, Resolution.HOUR) 
        self._aatr = self.atr(self.symbol, 30, Resolution.HOUR)
        self._rsi = self.rsi(self.symbol, 14, Resolution.HOUR)

        # Daily timeframe indicators
        self._sma_daily = self.sma(self.symbol, 30, Resolution.Daily)
        self._macd_daily = self.macd(self.symbol, 12, 30, 9, Resolution.Daily)

        # Price storage
        self._high_prices = deque(maxlen=100)
        self._low_prices = deque(maxlen=100)
        self._close_prices = deque(maxlen=5)

        # Fibonacci levels
        self.fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        self.fib_values = {}

        # Trade management
        self.entry_price = 0
        self.stop_loss_price = 0
        self.take_profit_price = 0

        self.create_charts()

    def create_charts(self):
        price_chart = Chart("Price and Signals")
        self.add_chart(price_chart)
        price_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.Black))
        price_chart.add_series(Series("SMA", SeriesType.LINE, "$", Color.Blue))
        price_chart.add_series(Series("Long", SeriesType.SCATTER, "$", Color.Green, ScatterMarkerSymbol.TRIANGLE))
        price_chart.add_series(Series("Short", SeriesType.SCATTER, "$", Color.Red, ScatterMarkerSymbol.TRIANGLE_DOWN))
        price_chart.add_series(Series("TP", SeriesType.SCATTER, "$", Color.Green, ScatterMarkerSymbol.CIRCLE))
        price_chart.add_series(Series("SL", SeriesType.SCATTER, "$", Color.Red, ScatterMarkerSymbol.CIRCLE))

        fib_chart = Chart("Fibonacci Levels")
        self.add_chart(fib_chart)
        for level in self.fib_levels:
            fib_chart.add_series(Series(f"Fib_{level}", SeriesType.LINE, "$", Color.Purple))

        indicators_chart = Chart("Indicators")
        self.add_chart(indicators_chart)
        indicators_chart.add_series(Series("MACD", SeriesType.LINE, "$", Color.Blue))
        indicators_chart.add_series(Series("MACD Signal", SeriesType.LINE, "$", Color.Red))
        indicators_chart.add_series(Series("ADX", SeriesType.LINE, "$", Color.Green))
        indicators_chart.add_series(Series("RSI", SeriesType.LINE, "$", Color.Orange))
        indicators_chart.add_series(Series("ATR", SeriesType.LINE, "$", Color.Purple))

    def calculate_position_size(self):
        account_value = self.portfolio.total_portfolio_value
        risk_per_trade = 0.02
        atr_value = self._aatr.current.value
        position_size = (account_value * risk_per_trade) / (atr_value * 1.5)
        return round(position_size)

    def calculate_take_profit(self, entry_price, is_long):
        atr_value = self._aatr.current.value
        adx = self._adx.current.value
        tp_multiplier = min(5, max(2, adx/10))
        return entry_price + (atr_value * tp_multiplier) if is_long else entry_price - (atr_value * tp_multiplier)

    def update_trailing_stop(self, curr_price, entry_price, curr_qty):
        atr_value = self._aatr.current.value
        profit_ratio = abs(curr_price - entry_price) / entry_price
        trail_multiplier = max(1.0, 2.0 - profit_ratio)
        
        if curr_qty > 0:
            return max(self.stop_loss_price, curr_price - (atr_value * trail_multiplier))
        return min(self.stop_loss_price, curr_price + (atr_value * trail_multiplier))

    def calculate_fibonacci_levels(self):
        if len(self._high_prices) < 2 or len(self._low_prices) < 2:
            return

        recent_high = max(list(self._high_prices)[-20:])
        recent_low = min(list(self._low_prices)[-20:])
        price_range = recent_high - recent_low

        for level in self.fib_levels:
            self.fib_values[level] = recent_low + (price_range * level)
            self.plot("Fibonacci Levels", f"Fib_{level}", self.fib_values[level])

    def on_data(self, data: Slice):
        if not data.ContainsKey(self.symbol):
            return

        if self.is_warming_up or not all(indicator.is_ready for indicator in 
            [self._macd, self._sma, self._adx, self._aatr, self._rsi, self._sma_daily, self._macd_daily]):
            return

        bar = data[self.symbol]
        close = bar.close
        
        self._close_prices.append(close)
        self._high_prices.append(bar.high)
        self._low_prices.append(bar.low)

        if len(self._close_prices) < 5:
            return

        self.calculate_fibonacci_levels()

        # Get indicator values
        adx = self._adx.current.value
        macd_value = self._macd.current.value
        macd_signal = self._macd.signal.current.value
        sma_value = self._sma.current.value
        atr_value = self._aatr.current.value
        rsi = self._rsi.current.value

        curr_qty = self.portfolio[self.symbol].quantity

        # Enhanced entry conditions
        allow_entry_long = (
            adx > 25 and
            macd_value > macd_signal and
            close > sma_value and
            close > self._sma_daily.current.value and
            self._macd_daily.current.value > self._macd_daily.signal.current.value and
            rsi < 70 and rsi > 30 and
            close > self._close_prices[-2] + atr_value * 0.5 and
            any(close > self.fib_values.get(level, 0) for level in [0.382, 0.5])
        )
        
        allow_entry_short = (
            adx > 25 and
            macd_value < macd_signal and
            close < sma_value and
            close < self._sma_daily.current.value and
            self._macd_daily.current.value < self._macd_daily.signal.current.value and
            rsi > 30 and rsi < 70 and
            close < self._close_prices[-2] - atr_value * 0.5 and
            any(close < self.fib_values.get(level, 0) for level in [0.618, 0.786])
        )

        # Entry Logic with dynamic position sizing
        if allow_entry_long and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, position_size, tag="long entry")
            self.plot("Price and Signals", "Long", close)
            self.entry_price = close
            self.stop_loss_price = close - atr_value * 1.5
            self.take_profit_price = self.calculate_take_profit(close, True)

        elif allow_entry_short and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, -position_size, tag="short entry")
            self.plot("Price and Signals", "Short", close)
            self.entry_price = close
            self.stop_loss_price = close + atr_value * 1.5
            self.take_profit_price = self.calculate_take_profit(close, False)

        # Enhanced exit logic with trailing stop
        if curr_qty != 0:
            self.stop_loss_price = self.update_trailing_stop(close, self.entry_price, curr_qty)

            if (curr_qty > 0 and (close >= self.take_profit_price or rsi > 80)) or \
               (curr_qty < 0 and (close <= self.take_profit_price or rsi < 20)):
                self.liquidate(tag="tp")
                self.plot("Price and Signals", "TP", close)
            elif (curr_qty > 0 and close <= self.stop_loss_price) or \
                 (curr_qty < 0 and close >= self.stop_loss_price):
                self.liquidate(tag="sl")
                self.plot("Price and Signals", "SL", close)

        # Plot indicators
        self.plot("Price and Signals", "Price", close)
        self.plot("Price and Signals", "SMA", sma_value)
        self.plot("Indicators", "MACD", macd_value)
        self.plot("Indicators", "MACD Signal", macd_signal)
        self.plot("Indicators", "ADX", adx)
        self.plot("Indicators", "RSI", rsi)
        self.plot("Indicators", "ATR", atr_value)