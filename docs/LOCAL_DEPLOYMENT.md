# Local deployment

## Requirements

- Python 3.11
- `uv`

## Setup

```bash
uv sync --python 3.11 --all-groups
```

## Local wallet governor

- Bind the HTTP wrapper only to `127.0.0.1` or `localhost`.
- Keep `spend_enabled: false` unless you explicitly intend to exercise the governed send path.
- Prefer the fake wallet backend for local development and tests.
- The Bitcoin Core backend skeleton is present but disabled by default.
