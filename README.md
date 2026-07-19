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

### C++バインディングの型定義ファイル (Type Stubs) の生成
PythonのIDE（VS CodeのPylance等）で、C++で実装された `godfield_core` モジュールの強力な型補完・チェックを有効にするため、`pybind11-stubgen` を用いて型定義ファイル（`.pyi`）を自動生成しています。
C++側のコード（クラスやメソッド、プロパティ）を変更した後は、以下のコマンドを実行して型定義ファイルを更新してください。

```powershell
# Generate the stubs directly into the godfield_core-stubs directory
.\.venv\Scripts\pybind11-stubgen.exe -o . --root-suffix="-stubs" godfield_core
```

> **[解説] なぜ `-stubs` フォルダを使うのか？ (Pylance 名前空間の衝突問題)**
> プロジェクトルートに C++ソースが入っている `godfield_core/` というフォルダがあるため、単純に `godfield_core.pyi` をルートに置いたり `stubs/` に配置すると、Pylance がソースフォルダの方を Python パッケージだと誤認し、型スタブが無視される問題（Namespace Shadowing）が発生します。
> これを回避するため、Python の PEP 561 仕様に則り `godfield_core-stubs` という型情報専用のパッケージフォルダを作成し、その中に `__init__.pyi` として配置することで、C++のディレクトリを汚さずに Pylance にモジュールの型を100%正しく認識させることができます。

### C++言語サーバー（clangd等）の設定生成 (Generate Compiler Flags for IDE)

C++のヘッダーファイルやソースコードをエディタで編集する際、Pythonの組み込みヘッダー（`Python.h`）や `pybind11` のヘッダーを正しく読み込むために、個人の環境に合わせた include パスを設定した `compile_flags.txt` が必要です。

本プロジェクトでは環境ごとのパス（絶対パス）を Git で管理しないため、`compile_flags.txt` は `.gitignore` に登録されており、各自の開発環境で以下のスクリプトを実行して動的生成します。

```powershell
# 自身の環境に合わせた compile_flags.txt を自動生成
uv run python tools/generate_compile_flags.py
```

### 【重要】Windows環境でのC++コンパイルと文字コード設定 (MSVC UTF-8 Pitfalls)
WindowsのMSVC環境では、デフォルトでソースコードを `Shift-JIS (CP932)` として読み込もうとするため、C++コード内で `"火"` などの日本語文字列を使用するとコンパイル時に文字化けし、JSONからのUTF-8パース結果と一致しなくなる致命的なバグが発生します。
これを防ぐため、`setup.py` にて `/utf-8` コンパイルオプションを渡しています。

**⚠️ ハマりどころ (Caching Pitfall):**
過去に `/utf-8` オプションなしでコンパイルに失敗した、または文字化けした状態でキャッシュされた場合、後から `setup.py` に `/utf-8` を追加して `uv pip install -e .` を実行しても、**C++ソースコード自体に変更がないと再コンパイルが走らず、古い文字化けしたキャッシュ（`.obj` ファイル）が使い回されてしまいます。**
エンコーディング関連でおかしいと感じた場合は、該当する `.cpp` ファイルに適当な空白やコメントを追加して保存（Touch）してから再度 `uv pip install -e .` を実行し、確実に再コンパイルを発生させてください。

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

## 現在のプロジェクト進捗状況 (Current Project Progress)

本プロジェクトは現在、**「フェーズ1：ゲームルールシミュレータの作成・完成度向上」**の段階にあります。
強化学習 (RL) やAIのモデル学習などの実装は**未着手**（スタブコードや枠組みのみの状態）であり、まずはC++側でゴッドフィールドの複雑なルール、例外、フェイズ遷移をバグなく正確にシミュレーションし、100%正しく進行できるゲームエンジンを完成させることに注力しています。

シミュレーション動作の正当性は、`tests/core/` 配下の単体テスト（`pytest`）を通じて厳密に検証されています。

---

## プロジェクト構造とコード分割 (Project Structure & Code Split)

当初 `godfield_core/src/game_logic.cpp` という1つの巨大なモノリスファイル（約2200行/80KB）で実装されていたゲームルールエンジンは、可読性と保守性の観点から、機能ごとに細かく分割・再設計されました。

各関数には、その役割がひと目でわかるよう日本語と英語の丁寧なコメントが記述されています。

### コアモジュールの構成 (`godfield_core/src/`)

* **[game_logic.cpp](./godfield_core/src/game_logic.cpp) (メインエントリー・管制塔)**
  * ルールエンジンの入り口である `step_game()`, `get_legal_actions()`, `get_single_legal_action()` のみを定義しています。
  * 各フェイズの処理や合法手チェックは、対応するモジュールへ委譲し、全体の流れのみをコントロールします。
* **[game_logic_internal.h](./godfield_core/src/game_logic_internal.h) (内部共有ヘッダー)**
  * 分割されたソースファイル間で共有するヘルパー関数、フェイズ固有のアクションステップ、および合法手チェック関数のプロトタイプ宣言をまとめています。
* **[card_registry.cpp](./godfield_core/src/card_registry.cpp) (カードマスター・ドロー管理)**
  * Python側から渡されたリストに基づくカードデータベースの初期化（`init_game_logic`）、カードドローの確率分布構築（山札からの抽選）、カード名の引き当てなどを担当します。
* **[combat_resolution.cpp](./godfield_core/src/combat_resolution.cpp) (戦闘・取引・効果適用解決)**
  * 雑貨カードなどの効果解決（回復、病気・状態異常付与）、売買取引の解決（`execute_sell_resolution`）、スーパーミラーによる反射処理など、直接ステータスや手札を操作する解決ロジックを管理します。
* **[phase_handlers.cpp](./godfield_core/src/phase_handlers.cpp) (フェイズ別ステップハンドラ)**
  * メイン、攻撃、防御、奇跡、両替、破棄など、ゲームフェイズごとのアクションに応じた状態遷移（`step_phase_X`）を実装しています。
* **[legal_actions.cpp](./godfield_core/src/legal_actions.cpp) (フェイズ別合法アクションチェック)**
  * 各種フェイズにおいて、プレイヤーが現在どの手札や行動を選択できるかのマスクを計算する関数群（`legal_phase_X`）を実装しています。
* **[env_pool.cpp](./godfield_core/src/env_pool.cpp) / [env_pool.h](./godfield_core/src/env_pool.h) (並列環境プール)**
  * 強化学習時にマルチスレッドで数万の環境をバッチ処理するためのプール機構です。
* **[bindings.cpp](./godfield_core/src/bindings.cpp) (pybind11 バインディング)**
  * C++で実装されたシミュレータを Python から高速に呼び出すためのバインディング定義。

---

## ドキュメントとアセット (Docs & Assets)

### ドキュメント (`docs/`)
- [`docs/rules.md`](./docs/rules.md): ゴッドフィールドの詳細なゲームルール。
- [`docs/game_flow.md`](./docs/game_flow.md): ゲームのフェイズ進行とフローチャート。
- [`docs/card_schema.md`](./docs/card_schema.md): カード定義YAML/JSONのデータスキーマ仕様。
- [`docs/ai-policy.md`](./docs/ai-policy.md): 強化学習エージェントの方針と状態表現設計。

### アセット (`assets/`)
- [`assets/cards/`](./assets/cards/): 全カードのプロパティや効果を定義したマスターYAMLファイル群。
- `assets/godfield_cards.json`: YAMLから自動生成される成果物ファイル。（※手動で編集しないでください）

---

## 可視化Webアプリケーション (Visualization Web Application)

内部シミュレータの状態をリアルタイムで同期し、実際にカードを選択してプレイ（対戦）できる対話型のWebアプリケーションを提供しています。

### 技術スタック
* **バックエンド**: FastAPI (Python) + Uvicorn + WebSocket
* **フロントエンド**: Vue.js (CDN経由) + Tailwind CSS (CDN経由)
* **静的アセット配信**: `assets/image/` 内の各種アセット画像をマウントしてWebアプリから参照可能にしています

### 主な機能
1. **実機に近い9x2のカード手札レイアウト**:
   * 最大18枚の手札枠をすっきりと収める **9x2 グリッド**を採用しています。
   * カード画像は引き伸ばされない綺麗な正方形で表示されます。
2. **ステータスバッジによる神器特性の可視化**:
   * 属性（火・水・木・土・光・闇・無）、威力（`攻9`、`守4` など）、プラス神器（`+`表記・赤文字）や奇跡の有無などを一目で確認できます。
3. **直感的なハイライト表示**:
   * **合法手（プレイ可能）なカード**: 緑色（エメラルド）の枠線と淡いネオンの光彩で強調され、クリック可能になります。
   * **選択中（仮置き）のカード**: 黄色（アンバー）の枠線でさらに大きく表示され、現在場に提示しているカードが瞬時に認識できます。
4. **戦闘・状態情報の配信ダッシュボード**:
   * 現在のターンやゲームフェイズに加え、攻撃の方向と詳細（例:「プレイヤー 0 から プレイヤー 1 へ 10 の攻撃中 (属性: 火)」）を表示する警告アラートがリアルタイムで更新されます。
5. **超コンパクトなステータスバー表示**:
   * HP/MP/所持金を1行にまとめ、守護神や病・災いなどの各種状態異常は最小限の極小バッジとして並列配置。手札エリアを広々と見渡せます。
6. **対戦操作とAI自動化の切り替え**:
   * 画面上のトグルで「対戦相手のAI操作（自動ターン進行）」を有効/無効に切り替えられます。無効にすることで、**1台の画面でプレイヤー0とプレイヤー1を交互に操作するパス＆プレイ（ローカル対戦）**が可能です。
7. **仮置き場をテーブル上部に配置**:
   * 自分と相手が現在出しているカード（解決待ち状態）を、手札のすぐ上に配置することで、実機と同じテーブル上のプレイ感を再現しています。

### 起動と確認方法

以下のコマンドを実行して可視化用サーバーを起動します：

```bash
# サーバーの起動
uv run python visualize_server.py
```

サーバーが起動したら、ブラウザで以下のURLを開いてください：
👉 **[http://localhost:8000/](http://localhost:8000/)**

