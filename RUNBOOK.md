# OpenClaw MoneyBot Runbook

## How to run tests
```bash
make test
```

## How to run a dry-run mission
```bash
python -m skills.integration_pipeline.runner run_integration_pipeline --opportunity-id test-1
```

## How to enable wallet spending
Edit configs/moneybot.yaml:
- Set wallet_governor_url to your wallet governor endpoint.
- Ensure email_mode is draft_only initially.

## How to disable wallet spending immediately
Edit configs/moneybot.yaml:
- Set wallet_governor_url to an empty value.
- Set wallet spending to disabled.

## How to run linting and type checking
```bash
make lint
make type-check
```

## How to format code
```bash
make format
```
