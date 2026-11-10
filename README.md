# Solana Wallet Checker — read-only edition

Checks balances for a finite list of **Solana public addresses you own**. It uses Solana's read-only `getBalance` JSON-RPC method and optionally displays BTChack service and coin metadata.

## Safety and scope

- No random key generation or keyspace traversal.
- No private-key, seed-phrase, or secret input.
- No private-key output or secret files.
- No transactions, signing, transfers, or wallet imports.
- No infinite scanning loop; only addresses in the supplied file are checked.
- BTChack integration is metadata-only: `/healthz`, `/readyz`, `/api/v1/coins`, and `/api/v1/limits`.
- This client deliberately does **not** call BTChack `pages`, `pages/random`, `find`, `derive`, `address`, `check`, or keyspace endpoints. Those workflows can return private-key material and are not part of this checker.

## Setup

Python 3.10+:

```bash
python -m pip install -r requirements.txt
```

Create `addresses.txt` with one Solana public address per line. Blank lines and lines beginning with `#` are ignored.

```text
# Public addresses only
YOUR_SOLANA_PUBLIC_ADDRESS
```

Run:

```bash
python sol_checker.py
```

Optional arguments:

```bash
python sol_checker.py --address-file my_addresses.txt
python sol_checker.py --skip-btchack
```

## Configuration

- `SOLANA_RPC_URL`: defaults to `https://api.mainnet-beta.solana.com`.
- `BTCHACK_BASE_URL`: defaults to `https://btchack.net`.

No API key is required or read by this client. HTTP requests use timeouts. Duplicate addresses are checked once. The script does not save balances or address lists to disk.

## Tests

Run the offline unit tests with:

```bash
python -m unittest discover -s tests -v
```
