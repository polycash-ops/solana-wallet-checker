#!/usr/bin/env python3
"""Finite, read-only Solana balance checker for public addresses you own.

This tool never generates keypairs, accepts private keys, or writes secrets.
BTChack integration is deliberately limited to health/readiness and public
coin/limit metadata. It does not call keyspace, page, find, derive, or key
inspection endpoints.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

import base58
import requests

SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
BTCHACK_BASE_URL = os.getenv("BTCHACK_BASE_URL", "https://btchack.net").rstrip("/")
HTTP_TIMEOUT = 12


def load_addresses(path: Path) -> list[str]:
    addresses: list[str] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        try:
            decoded = base58.b58decode(value)
        except Exception as exc:
            raise ValueError(f"Invalid Base58 public address on line {line_number}") from exc
        if len(decoded) != 32:
            raise ValueError(f"Expected a 32-byte Solana public address on line {line_number}")
        addresses.append(value)
    # Preserve order while avoiding duplicate RPC requests.
    return list(dict.fromkeys(addresses))


class BTChackClient:
    """Metadata-only BTChack client; never requests key-bearing endpoints."""

    def __init__(self, base_url: str = BTCHACK_BASE_URL, session=None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def _get(self, path: str) -> dict:
        response = self.session.get(f"{self.base_url}{path}", timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected BTChack response for {path}")
        return payload

    def status(self) -> dict:
        result = {}
        for label, path in (("health", "/healthz"), ("readiness", "/readyz")):
            try:
                data = self._get(path)
                # Whitelist harmless status fields; do not dump arbitrary API data.
                result[label] = {
                    key: data[key]
                    for key in ("status", "ok", "ready", "service")
                    if key in data and isinstance(data[key], (str, bool, int, float))
                }
                result[label]["reachable"] = True
            except (requests.RequestException, ValueError):
                result[label] = {"reachable": False}
        try:
            coins = self._get("/api/v1/coins").get("coins", [])
            result["solana_supported"] = any(
                isinstance(coin, dict) and str(coin.get("slug", "")).lower() == "sol"
                for coin in coins
            )
        except (requests.RequestException, ValueError):
            result["solana_supported"] = None
        try:
            limits = self._get("/api/v1/limits")
            result["limits"] = {
                key: limits[key]
                for key in ("limit_min", "limit_max", "limit_step", "default")
                if key in limits and isinstance(limits[key], int)
            }
        except (requests.RequestException, ValueError):
            result["limits"] = None
        return result


def get_balance(address: str, session=None) -> int:
    client = session or requests
    response = client.post(
        SOLANA_RPC_URL,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address, {"commitment": "confirmed"}],
        },
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError("Solana RPC returned an error")
    value = payload.get("result", {}).get("value")
    if not isinstance(value, int) or value < 0:
        raise ValueError("Solana RPC returned an invalid balance")
    return value


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check balances for your Solana public addresses.")
    parser.add_argument("--address-file", default="addresses.txt", help="One public address per line")
    parser.add_argument("--skip-btchack", action="store_true", help="Skip BTChack metadata status")
    args = parser.parse_args(argv)

    address_file = Path(args.address_file)
    if not address_file.is_file():
        print(f"Address file not found: {address_file}", file=sys.stderr)
        return 2
    try:
        addresses = load_addresses(address_file)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Could not read address file: {exc}", file=sys.stderr)
        return 2
    if not addresses:
        print("No public addresses found. Add one address per line to addresses.txt.")
        return 0

    if not args.skip_btchack:
        status = BTChackClient().status()
        print("BTChack metadata status:")
        print(f"  Health reachable: {status['health']['reachable']}")
        print(f"  Readiness reachable: {status['readiness']['reachable']}")
        print(f"  SOL listed as supported: {status['solana_supported']}")
        print("  Scope: metadata only; no keyspace or private-key endpoints called")

    print(f"Checking {len(addresses)} unique public address(es) via Solana read-only RPC.")
    failures = 0
    for address in addresses:
        try:
            lamports = get_balance(address)
            print(f"{address}  {lamports / 1_000_000_000:.9f} SOL  ({lamports} lamports)")
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            failures += 1
            print(f"{address}  ERROR: {type(exc).__name__}")
    print(f"Complete: {len(addresses) - failures} successful, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
