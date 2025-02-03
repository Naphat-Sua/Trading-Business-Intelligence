# region imports
from AlgorithmImports import *
# endregion

class MACD_Template(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2024, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100000)
        self.symbol = self.add_cfd("WTICOUSD", Resolution.HOUR).symbol #WTICOUSD

        self._macd = self.macd(self.symbol, 12, 26, 9)
        self._bb = self.bb(self.symbol, 20, 2)

        self.window = RollingWindow[float](20)

        self.set_warm_up(1000)

    def on_data(self, data: Slice):
        close = data[self.symbol].close
        self.window.add(close) # Save closing price to the window

        if self.is_warming_up:
            return

        # Indicators
        fast = self._macd.fast.current.value
        slow = self._macd.slow.current.value
        macd = self._macd.current.value
        histogram = self._macd.histogram.current.value

        curr_qty = self.portfolio[self.symbol].quantity

        # ===== Write Logic Here =====
        if histogram < 0 and curr_qty == 0:
            self.market_order(self.symbol, -100)

        elif histogram > 0 and curr_qty == -100:
            self.liquidate()

        adj_qty = 0
        if histogram > 0:
            adj_qty = 100
        elif histogram < 0:
            adj_qty = -100
        # ============================

        # Plot
        self.plot("MACD", "Histogram", histogram)
        self.plot("Curr_qty", "Curr_qty", curr_qty)