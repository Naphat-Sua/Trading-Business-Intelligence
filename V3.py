from AlgorithmImports import *
from collections import deque

class V3(QCAlgorithm):
    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2021, 1, 1)
        self.set_cash(100000)
        self.symbol = self.add_cfd("WTICOUSD", Resolution.HOUR).symbol

        self._macd = self.macd(self.symbol, 12, 26, 9, Resolution.HOUR)
        self._sma = self.sma(self.symbol, 30, Resolution.HOUR)
        self._adx = self.adx(self.symbol, 30, Resolution.HOUR)
        self._aatr = self.atr(self.symbol, 30, Resolution.HOUR)
        self._rsi = self.rsi(self.symbol, 14, Resolution.HOUR)

        self._sma_daily = self.sma(self.symbol, 30, Resolution.DAILY)
        self._macd_daily = self.macd(self.symbol, 12, 26, 9, Resolution.DAILY)

        self._high_prices = deque(maxlen=100)
        self._low_prices = deque(maxlen=100)
        self._close_prices = deque(maxlen=5)

        self.fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        self.fib_values = {}

        self.entry_price = 0
        self.stop_loss_price = 0
        self.take_profit_price = 0
        self.entry_bar = 0
        self.bar_count = 0

        self.create_charts()

    def create_charts(self):
        price_chart = Chart("Price and Signals")
        price_chart.add_series(Series("Price", SeriesType.LINE, "$", Color.BLACK))
        price_chart.add_series(Series("SMA", SeriesType.LINE, "$", Color.BLUE))
        price_chart.add_series(Series("Long", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.TRIANGLE))
        price_chart.add_series(Series("Short", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.TRIANGLE_DOWN))
        price_chart.add_series(Series("TP", SeriesType.SCATTER, "$", Color.GREEN, ScatterMarkerSymbol.CIRCLE))
        price_chart.add_series(Series("SL", SeriesType.SCATTER, "$", Color.RED, ScatterMarkerSymbol.CIRCLE))
        self.add_chart(price_chart)

        fib_chart = Chart("Fibonacci Levels")
        for level in self.fib_levels:
            fib_chart.add_series(Series(f"Fib_{level}", SeriesType.LINE, "$", Color.PURPLE))
        self.add_chart(fib_chart)

        indicators_chart = Chart("Indicators")
        indicators_chart.add_series(Series("MACD", SeriesType.LINE, "$", Color.BLUE))
        indicators_chart.add_series(Series("MACD Signal", SeriesType.LINE, "$", Color.RED))
        indicators_chart.add_series(Series("ADX", SeriesType.LINE, "$", Color.GREEN))
        indicators_chart.add_series(Series("RSI", SeriesType.LINE, "$", Color.ORANGE))
        indicators_chart.add_series(Series("ATR", SeriesType.LINE, "$", Color.PURPLE))
        self.add_chart(indicators_chart)

    def calculate_position_size(self):
        account_value = self.portfolio.total_portfolio_value
        risk_per_trade = 0.02
        atr_value = self._aatr.current.value
        position_size = (account_value * risk_per_trade) / (atr_value * 1.5)
        return round(position_size)

    def calculate_take_profit(self, entry_price, is_long):
        atr_value = self._aatr.current.value
        adx = self._adx.current.value
        tp_multiplier = min(5, max(3, adx/10))
        return entry_price + (atr_value * tp_multiplier) if is_long else entry_price - (atr_value * tp_multiplier)

    def update_trailing_stop(self, curr_price, entry_price, curr_qty):
        atr_value = self._aatr.current.value
        profit = abs(curr_price - entry_price)
        
        # Move to breakeven + buffer when profit reaches 1 ATR
        if profit >= atr_value:
            buffer = atr_value * 0.5
            new_sl = entry_price + buffer if curr_qty > 0 else entry_price - buffer
            if (curr_qty > 0 and new_sl > self.stop_loss_price) or (curr_qty < 0 and new_sl < self.stop_loss_price):
                self.stop_loss_price = new_sl

        # Dynamic trailing based on profit ratio
        profit_ratio = profit / entry_price
        trail_multiplier = max(1.0, 2.0 - profit_ratio)
        
        if curr_qty > 0:
            return max(self.stop_loss_price, curr_price - (atr_value * trail_multiplier))
        return min(self.stop_loss_price, curr_price + (atr_value * trail_multiplier))

    def calculate_fibonacci_levels(self):
        if not self._high_prices or not self._low_prices:
            return

        recent_high = max(self._high_prices)
        recent_low = min(self._low_prices)
        price_range = recent_high - recent_low

        # Determine trend using daily SMA slope
        if self._sma_daily.current.value > self._sma_daily.previous.value:
            for level in self.fib_levels:
                self.fib_values[level] = recent_low + (price_range * level)
        else:
            for level in self.fib_levels:
                self.fib_values[level] = recent_high - (price_range * level)

        for level in self.fib_levels:
            self.plot("Fibonacci Levels", f"Fib_{level}", self.fib_values[level])

    def on_data(self, data: Slice):
        self.bar_count += 1
        if not data.contains_key(self.symbol):
            return

        if self.is_warming_up or not all([indicator.is_ready for indicator in 
            [self._macd, self._sma, self._adx, self._aatr, self._rsi, self._sma_daily, self._macd_daily]]):
            return

        bar = data[self.symbol]
        close = bar.close
        
        self._close_prices.append(close)
        self._high_prices.append(bar.high)
        self._low_prices.append(bar.low)

        if len(self._close_prices) < 5:
            return

        self.calculate_fibonacci_levels()

        adx = self._adx.current.value
        macd_val = self._macd.current.value
        macd_sig = self._macd.signal.current.value
        sma_val = self._sma.current.value
        atr_val = self._aatr.current.value
        rsi = self._rsi.current.value
        curr_qty = self.portfolio[self.symbol].quantity

        # Enhanced entry conditions with trend alignment
        daily_trend_up = self._sma_daily.current.value > self._sma_daily.previous.value
        daily_macd_bull = self._macd_daily.current.value > self._macd_daily.signal.current.value
        
        allow_entry_long = (
            adx > 25 and
            macd_val > macd_sig and
            close > sma_val and
            close > self._sma_daily.current.value and
            daily_macd_bull and
            rsi > 50 and  
            close > self._close_prices[-2] + atr_val * 0.5 and
            any(close > self.fib_values.get(level, 0) for level in [0.382, 0.5]) and
            daily_trend_up
        )
        
        allow_entry_short = (
            adx > 25 and
            macd_val < macd_sig and
            close < sma_val and
            close < self._sma_daily.current.value and
            self._macd_daily.current.value < self._macd_daily.signal.current.value and
            rsi < 50 and 
            close < self._close_prices[-2] - atr_val * 0.5 and
            any(close < self.fib_values.get(level, 0) for level in [0.618, 0.786]) and
            not daily_trend_up
        )

        if allow_entry_long and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, position_size, tag="Long Entry")
            self.plot("Price and Signals", "Long", close)
            self.entry_price = close
            self.stop_loss_price = close - atr_val * 1.5
            self.take_profit_price = self.calculate_take_profit(close, True)
            self.entry_bar = self.bar_count

        elif allow_entry_short and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, -position_size, tag="Short Entry")
            self.plot("Price and Signals", "Short", close)
            self.entry_price = close
            self.stop_loss_price = close + atr_val * 1.5
            self.take_profit_price = self.calculate_take_profit(close, False)
            self.entry_bar = self.bar_count

        # Exit logic with multiple conditions
        if curr_qty != 0:
            if self.bar_count - self.entry_bar >= 24:
                self.liquidate(tag="Time Exit")
                return

            # Update trailing stop
            self.stop_loss_price = self.update_trailing_stop(close, self.entry_price, curr_qty)

            # Profit target or RSI exit
            if (curr_qty > 0 and (close >= self.take_profit_price or rsi < 70)) or \
               (curr_qty < 0 and (close <= self.take_profit_price or rsi > 30)):
                self.liquidate(tag="Take Profit")
                self.plot("Price and Signals", "TP", close)
            # Stop loss
            elif (curr_qty > 0 and close <= self.stop_loss_price) or \
                 (curr_qty < 0 and close >= self.stop_loss_price):
                self.liquidate(tag="Stop Loss")
                self.plot("Price and Signals", "SL", close)

        self.plot("Price and Signals", "Price", close)
        self.plot("Price and Signals", "SMA", sma_val)
        self.plot("Indicators", "MACD", macd_val)
        self.plot("Indicators", "MACD Signal", macd_sig)
        self.plot("Indicators", "ADX", adx)
        self.plot("Indicators", "RSI", rsi)
        self.plot("Indicators", "ATR", atr_val)