import unittest

from trendrail.data import Bar, parse_csv_text


class TestBarValidation(unittest.TestCase):
    def test_rejects_high_below_low(self):
        with self.assertRaises(ValueError):
            Bar("2023-01-01", open=10, high=9, low=11, close=10)

    def test_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            Bar("2023-01-01", open=0, high=10, low=1, close=5)


class TestColumnResolution(unittest.TestCase):
    def test_plain_lowercase(self):
        text = "date,open,high,low,close\n2023-01-03,10,11,9,10.5\n"
        bars = parse_csv_text(text)
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].close, 10.5)

    def test_yahoo_style_with_adjustment(self):
        # Close 100 but Adj Close 50 => 2:1 split factor; OHLC must halve.
        text = (
            "Date,Open,High,Low,Close,Adj Close,Volume\n"
            "2023-01-03,98,102,97,100,50,1000\n"
        )
        bars = parse_csv_text(text)
        b = bars[0]
        self.assertAlmostEqual(b.close, 50.0)
        self.assertAlmostEqual(b.open, 49.0)
        self.assertAlmostEqual(b.high, 51.0)
        self.assertAlmostEqual(b.low, 48.5)

    def test_adjustment_can_be_disabled(self):
        text = (
            "Date,Open,High,Low,Close,Adj Close,Volume\n"
            "2023-01-03,98,102,97,100,50,1000\n"
        )
        bars = parse_csv_text(text, adjust=False)
        self.assertAlmostEqual(bars[0].close, 100.0)

    def test_ticker_prefixed_headers(self):
        text = (
            "Date,AAPL.Open,AAPL.High,AAPL.Low,AAPL.Close,AAPL.Volume\n"
            "2023-01-03,98,102,97,100,1000\n"
        )
        bars = parse_csv_text(text)
        self.assertAlmostEqual(bars[0].close, 100.0)
        self.assertAlmostEqual(bars[0].open, 98.0)

    def test_sorted_oldest_first_regardless_of_input_order(self):
        text = (
            "date,open,high,low,close\n"
            "2023-01-05,10,11,9,10\n"
            "2023-01-03,10,11,9,10\n"
        )
        bars = parse_csv_text(text)
        self.assertEqual(bars[0].date, "2023-01-03")
        self.assertEqual(bars[-1].date, "2023-01-05")

    def test_clamps_rounding_artifact(self):
        # close 100.01 slightly above high 100 -> high clamped up to include it.
        text = "date,open,high,low,close\n2023-01-03,99,100,98,100.01\n"
        bars = parse_csv_text(text)
        self.assertGreaterEqual(bars[0].high, bars[0].close)

    def test_thousands_separator(self):
        text = 'date,open,high,low,close\n2023-01-03,"1,000","1,010",990,"1,005"\n'
        bars = parse_csv_text(text)
        self.assertAlmostEqual(bars[0].close, 1005.0)

    def test_missing_required_column_raises(self):
        with self.assertRaises(ValueError):
            parse_csv_text("date,open,high,close\n2023-01-03,10,11,10\n")


if __name__ == "__main__":
    unittest.main()
