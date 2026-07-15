# GodField RL

GodField（ゴッドフィールド）のAIプレイヤーを育成するための強化学習(RL)環境です。

プロジェクトの計画として、まずはC++ (Pythonバインディング) にてゴッドフィールドのゲームを完璧にシミュレーションできる高速なコア環境を作成し、web-visualizerを用いてそれを可視化できるようにします。
そのあとで、強化学習を用いて高度なAIプレイヤーを育成する予定です。

## 開発セットアップ (Development Setup)

パッケージ管理に `uv` を、リンターとして `ruff` を使用しています。

```bash
# 依存関係の同期（初回セットアップ）
uv sync

# C++コード (.cpp / .h) を変更した場合の再ビルドコマンド
# ※Python側から `import godfield_core` できるように拡張モジュールをコンパイルします
uv pip install -e .

# テストの実行
uv run pytest tests/

# リンターとフォーマッターの実行
uv run ruff check .
uv run ruff format .
```

## カードデータの管理とビルド (Card Data Generation)

カードデータは可読性の高いYAML形式で [`assets/cards/`](./assets/cards/) ディレクトリ配下に定義されています。
これらのYAMLファイルは、ビルドスクリプトによって単一のマスターJSONファイル (`assets/godfield_cards.json`) にコンパイルされ、ゲームエンジンに読み込まれます。

```bash
# YAML定義からマスターJSONとC++ヘッダーをビルド
uv run python tools/build_cards.py

# 生成されたJSONのスキーマバリデーション
uv run python tools/validate_cards.py
```

### 【重要】 JSON変換とC++定数ヘッダーの自動生成
強化学習シミュレータにおけるパフォーマンス（O(1)での条件分岐）を確保するため、特殊カードの判定には文字列比較ではなくC++の整数定数を使用します。
`tools/build_cards.py` はJSONへの変換時に、YAML内で `id_str` （例: `super_mirror`）が定義されたカードを自動で抽出し、以下のようなC++ヘッダー (`godfield_core/src/generated_card_ids.h`) を**自動生成**します。

```cpp
constexpr int ID_SUPER_MIRROR = 184;
constexpr int ID_SUN_AMULET = 205;
```
これにより、特殊カードを追加・変更する際も、YAMLに `id_str` を付与してビルドするだけで、C++側のロジックから安全かつ最高速で参照できるようになります。

## テストアーキテクチャ (Testing API)

本プロジェクトでは、1万並列を捌くための `EnvPool` （バッチ処理機構）と、ゲームのコアロジックを完全に分離しています（関心の分離）。
コアロジックは単発のインライン関数 `step_game(InternalState&, int)` として切り出されており、テスト環境からはこの関数を直接叩きます。
Python側には `InternalState` 構造体がそのまま公開されているため、`SimulationRunner` (`tests/core/test_utils.py`) を使って任意のHPや手札の盤面状況を直接注入し、マイクロステップ単位で詳細なアサーションが可能です。

## プロジェクト構造とドキュメント (Project Structure)

### ドキュメント (`docs/`)
- [`docs/rules.md`](./docs/rules.md): ゴッドフィールドの詳細なゲームルール。
- [`docs/game_flow.md`](./docs/game_flow.md): ゲームのフェイズ進行とフローチャート。
- [`docs/card_schema.md`](./docs/card_schema.md): カード定義YAML/JSONのデータスキーマ仕様。
- [`docs/ai-policy.md`](./docs/ai-policy.md): 強化学習エージェントの方針と状態表現設計。

### アセット (`assets/`)
- [`assets/cards/`](./assets/cards/): 全カードのプロパティや効果を定義したマスターYAMLファイル群。
- `assets/godfield_cards.json`: YAMLから自動生成される成果物ファイル。（※手動で編集しないでください）
