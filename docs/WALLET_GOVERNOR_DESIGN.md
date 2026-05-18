# Wallet governor design

## Canonical flow

1. `wallet_governor_client` validates a spend request locally.
2. The client writes a `proposed` spend request to the ledger.
3. The client calls the local HTTP wallet governor with `spend_request_id`.
4. `wallet_governor_service` loads the existing ledger spend request and verifies policy, budget, TOS/legal, evidence, destination, category, and limits.
5. The service transitions the spend request through `approved -> sending -> sent` or to `rejected` / `failed`.
6. The service records wallet transactions and audit events for request receipt, rejections, backend failures, and successful sends.

## Safety properties

- No service-side spend request creation.
- Idempotency conflicts reject instead of silently reusing a mismatched request.
- Fee estimates are included in limit enforcement.
- Bitcoin Core support exists only as a disabled-by-default skeleton backend.
- The HTTP API is localhost-only by default.
