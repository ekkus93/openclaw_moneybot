# Testing

Run the full quality gates with:

```bash
uv run --python 3.11 ruff check .
uv run --python 3.11 mypy .
uv run --python 3.11 pytest
```

Focused suites:

- wallet path: `tests/unit/test_wallet_governor_service.py`, `test_wallet_governor_client.py`, `test_wallet_governor_http.py`, `test_bitcoin_core_backend.py`
- safety skills: policy, TOS/legal, budget, evidence, email, experiment review
- scout adapters: `tests/unit/test_opportunity_source_adapters.py`

The regression fixtures cover blocked categories, wallet safety regressions, and fail-closed review cases.
