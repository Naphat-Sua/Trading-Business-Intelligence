from AlgorithmImports import *
from collections import deque

class V6(QCAlgorithm):
    # I removed ALL plot cause they eat lots of resource
    def initialize(self):
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(100000)
        self.symbol = self.add_cfd("WTICOUSD", Resolution.HOUR).symbol
        
        self._macd = self.macd(self.symbol, 12, 26, 9, Resolution.HOUR)
        self._sma = self.sma(self.symbol, 20, Resolution.HOUR)
        self._adx = self.adx(self.symbol, 14, Resolution.HOUR)
        self._atr = self.atr(self.symbol, 14, Resolution.HOUR)
        self._rsi = self.rsi(self.symbol, 14, Resolution.HOUR)
        
        self._sma_daily = self.sma(self.symbol, 50, Resolution.DAILY)
        self._macd_daily = self.macd(self.symbol, 12, 26, 9, Resolution.DAILY)
        
        self._high_prices = deque(maxlen=50)
        self._low_prices = deque(maxlen=50)
        self._close_prices = deque(maxlen=5)
        
        self.fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        self.fib_values = {}
        
        self.entry_price = 0
        self.stop_loss_price = 0
        self.take_profit_price = 0
        self.entry_bar = 0
        self.bar_count = 0
    
    def calculate_position_size(self):
        account_value = self.portfolio.total_portfolio_value
        risk_per_trade = 0.06  # Increased to 5% per trade
        atr_value = self._atr.current.value
        position_size = (account_value * risk_per_trade) / (atr_value * 1.2)
        return round(position_size)
    
    def calculate_take_profit(self, entry_price, is_long):
        atr_value = self._atr.current.value
        return entry_price + (atr_value * 8) if is_long else entry_price - (atr_value * 8)
    
    def on_data(self, data: Slice):
        self.bar_count += 1
        if not data.contains_key(self.symbol):
            return
        
        if self.is_warming_up or not all([
            self._macd.is_ready, self._sma.is_ready, self._adx.is_ready,
            self._atr.is_ready, self._rsi.is_ready, self._sma_daily.is_ready,
            self._macd_daily.is_ready]):
            return
        
        bar = data[self.symbol]
        close = bar.close
        self._close_prices.append(close)
        self._high_prices.append(bar.high)
        self._low_prices.append(bar.low)
        if len(self._close_prices) < 5:
            return
        
        adx = self._adx.current.value
        macd_val = self._macd.current.value
        macd_sig = self._macd.signal.current.value
        sma_val = self._sma.current.value
        atr_val = self._atr.current.value
        rsi = self._rsi.current.value
        curr_qty = self.portfolio[self.symbol].quantity
        
        allow_entry_long = (
            adx > 20 and macd_val > macd_sig and close > sma_val and
            rsi > 55 and self._sma_daily.current.value > self._sma_daily.previous.value
        )
        
        allow_entry_short = (
            adx > 20 and macd_val < macd_sig and close < sma_val and
            rsi < 45 and self._sma_daily.current.value < self._sma_daily.previous.value
        )
        
        if allow_entry_long and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, position_size, tag="Long Entry")
            self.entry_price = close
            self.stop_loss_price = close - atr_val * 2.0
            self.take_profit_price = self.calculate_take_profit(close, True)
            self.entry_bar = self.bar_count
        
        elif allow_entry_short and curr_qty == 0:
            position_size = self.calculate_position_size()
            self.market_order(self.symbol, -position_size, tag="Short Entry")
            self.entry_price = close
            self.stop_loss_price = close + atr_val * 2.0
            self.take_profit_price = self.calculate_take_profit(close, False)
            self.entry_bar = self.bar_count
        
        if curr_qty != 0:
            if self.bar_count - self.entry_bar >= 24:
                self.liquidate(tag="Time Exit")
                return
            
            if curr_qty > 0:
                self.stop_loss_price = max(self.stop_loss_price, close - atr_val * 1.0)
            else:
                self.stop_loss_price = min(self.stop_loss_price, close + atr_val * 1.0)
            
            if (curr_qty > 0 and close >= self.take_profit_price) or \
               (curr_qty < 0 and close <= self.take_profit_price):
                self.liquidate(tag="Take Profit")
            elif (curr_qty > 0 and close <= self.stop_loss_price) or \
                 (curr_qty < 0 and close >= self.stop_loss_price):
                self.liquidate(tag="Stop Loss")
