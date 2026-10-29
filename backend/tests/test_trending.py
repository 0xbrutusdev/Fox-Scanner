"""Разбор ответа GeckoTerminal /trending_pools для выпадающего списка на главной."""
import unittest

from foxscanner.scan import market


class TestTrending(unittest.TestCase):
    def test_unique_base_tokens_keep_pool_order(self):
        addr = "0x" + "ab" * 20
        other = "0x" + "cd" * 20
        data = {"included": [
            {"id": "bsc_" + addr, "type": "token", "attributes": {
                "address": addr, "name": "Pump", "symbol": "PUMP",
                "image_url": "https://assets.example/pump.png"}},
            {"id": "bsc_" + other, "type": "token", "attributes": {
                "address": other, "name": "Other", "symbol": "OT", "image_url": "/relative.png"}},
        ], "data": [
            {"relationships": {"base_token": {"data": {"id": "bsc_" + addr}}},
             "attributes": {"market_cap_usd": "4110000000", "base_token_price_usd": "0.2"}},
            {"relationships": {"base_token": {"data": {"id": "bsc_" + addr}}},
             "attributes": {"market_cap_usd": "1"}},
            {"relationships": {"base_token": {"data": {"id": "bsc_" + other}}},
             "attributes": {"fdv_usd": "10", "base_token_price_usd": "nope"}},
        ]}
        items = market.parse_trending(data, 20)
        self.assertEqual([x["symbol"] for x in items], ["PUMP", "OT"])
        self.assertEqual(items[0]["mcap_usd"], 4110000000.0)
        self.assertEqual(items[0]["image"], "https://assets.example/pump.png")
        self.assertEqual(items[1]["image"], "")
        self.assertIsNone(items[1]["price_usd"])
        self.assertEqual(items[1]["mcap_usd"], 10.0)

    def test_search_keeps_bsc_and_prefers_liquidity(self):
        bnb = "0x" + "ab" * 20
        other = "0x" + "cd" * 20
        data = {"pairs": [
            {"chainId": "solana", "baseToken": {"address": "So111", "symbol": "SOL", "name": "Sol"},
             "liquidity": {"usd": 999}, "marketCap": 1},
            {"chainId": "bsc", "baseToken": {"address": other, "symbol": "OT", "name": "Other"},
             "liquidity": {"usd": 10}, "marketCap": 5, "priceUsd": "0.1",
             "info": {"imageUrl": "http://insecure/x.png"}},
            {"chainId": "bsc", "baseToken": {"address": bnb, "symbol": "PUMP", "name": "Pump"},
             "liquidity": {"usd": 1000}, "fdv": 20, "priceUsd": "1.5",
             "info": {"imageUrl": "https://cdn.example/p.png"}},
            {"chainId": "bsc", "baseToken": {"address": bnb, "symbol": "PUMP", "name": "Pump"},
             "liquidity": {"usd": 1}},
        ]}
        items = market.parse_search(data, 20)
        self.assertEqual([x["symbol"] for x in items], ["PUMP", "OT"])
        self.assertEqual(items[0]["image"], "https://cdn.example/p.png")
        self.assertEqual(items[0]["mcap_usd"], 20.0)
        self.assertEqual(items[1]["image"], "")
        self.assertEqual(market.search_tokens("a"), [])


if __name__ == "__main__":
    unittest.main()
