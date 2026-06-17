import json
import unittest

from archie.fetch import yahoo_to_csv, _stooq_symbol, FetchError
from archie.data import parse_csv_text


class TestStooqSymbol(unittest.TestCase):
    def test_us_default_suffix(self):
        self.assertEqual(_stooq_symbol("AAPL"), "aapl.us")

    def test_keeps_explicit_suffix(self):
        self.assertEqual(_stooq_symbol("aapl.us"), "aapl.us")
        self.assertEqual(_stooq_symbol("^spx"), "^spx")


class TestYahooParsing(unittest.TestCase):
    def _payload(self):
        return json.dumps({
            "chart": {
                "error": None,
                "result": [{
                    # 2021-01-04 and 2021-01-05 (UTC)
                    "timestamp": [1609718400, 1609804800],
                    "indicators": {
                        "quote": [{
                            "open": [133.52, 128.89],
                            "high": [133.61, 131.74],
                            "low": [126.76, 128.43],
                            "close": [129.41, 131.01],
                            "volume": [143301900, 97664900],
                        }],
                        "adjclose": [{"adjclose": [127.0, 128.6]}],
                    },
                }],
            }
        })

    def test_converts_to_loadable_csv(self):
        csv_text = yahoo_to_csv(self._payload(), "AAPL")
        self.assertIn("Adj Close", csv_text.splitlines()[0])
        bars = parse_csv_text(csv_text)
        self.assertEqual(len(bars), 2)
        self.assertEqual(bars[0].date, "2021-01-04")
        # Adjustment applied: close becomes the adjusted close.
        self.assertAlmostEqual(bars[0].close, 127.0)

    def test_skips_null_bars(self):
        payload = json.loads(self._payload())
        payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][1] = None
        csv_text = yahoo_to_csv(json.dumps(payload), "AAPL")
        bars = parse_csv_text(csv_text)
        self.assertEqual(len(bars), 1)

    def test_error_payload_raises(self):
        payload = json.dumps({"chart": {"error": {"code": "Not Found"},
                                        "result": None}})
        with self.assertRaises(FetchError):
            yahoo_to_csv(payload, "NOPE")

    def test_empty_result_raises(self):
        with self.assertRaises(FetchError):
            yahoo_to_csv(json.dumps({"chart": {"result": []}}), "NOPE")


if __name__ == "__main__":
    unittest.main()
