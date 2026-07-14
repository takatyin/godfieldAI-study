# GodField RL
A Reinforcement Learning environment for GodField.

## Development Setup

We use `uv` for fast dependency management and `ruff` for linting.

```bash
# Sync dependencies and build the C++ core extension
uv sync

# Run the training script
uv run python train.py

# Lint and format code
uv run ruff check .
uv run ruff format .
```
