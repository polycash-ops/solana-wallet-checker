import unittest
from unittest.mock import Mock

import base58

from sol_checker import BTChackClient, get_balance, load_addresses


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class SafeIntegrationTests(unittest.TestCase):
    def test_load_addresses_deduplicates_and_ignores_comments(self):
        address = base58.b58encode(bytes(range(32))).decode()
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "addresses.txt"
            path.write_text(f"# comment\n{address}\n\n{address}\n", encoding="utf-8")
            self.assertEqual(load_addresses(path), [address])

    def test_rejects_wrong_length_address(self):
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "addresses.txt"
            path.write_text(base58.b58encode(b"short").decode(), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_addresses(path)

    def test_btchack_uses_only_metadata_routes(self):
        session = Mock()
        session.get.side_effect = [
            FakeResponse({"status": "ok"}),
            FakeResponse({"ready": True}),
            FakeResponse({"coins": [{"slug": "sol", "name": "Solana"}]}),
            FakeResponse({"limit_min": 10, "limit_max": 50, "limit_step": 5, "default": 50}),
        ]
        result = BTChackClient(session=session).status()
        called_paths = [call.args[0].split("btchack.test")[-1] for call in session.get.call_args_list]
        self.assertEqual(
            called_paths,
            ["/healthz", "/readyz", "/api/v1/coins", "/api/v1/limits"],
        )
        self.assertTrue(result["solana_supported"])
        self.assertEqual(result["health"]["status"], "ok")

    def test_balance_uses_getbalance_and_returns_lamports(self):
        session = Mock()
        session.post.return_value = FakeResponse({"result": {"value": 1234567890}})
        self.assertEqual(get_balance("public-address", session=session), 1234567890)
        self.assertEqual(session.post.call_args.kwargs["json"]["method"], "getBalance")


if __name__ == "__main__":
    unittest.main()
