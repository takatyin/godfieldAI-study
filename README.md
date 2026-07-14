# GodField RL
A Reinforcement Learning environment for GodField.

プロジェクトの計画として、まずはC++ (Pythonバインディング) にてゴッドフィールドのゲームを完璧にシミュレーションできる環境を作成し、web-visualizerを用いてそれを可視化できるようにする。
そのあとで、強化学習を行い、AIプレイヤーを育成する予定である。

現在はゴッドフィールドのルールを明確にした上で、ゲームのフローをドキュメント化している途中である。

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
