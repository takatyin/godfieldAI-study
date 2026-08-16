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

# 開発中は、以下のインプレース差分ビルドコマンドを使うと最速（1〜3秒程度）で再コンパイルが完了します：
uv run python setup.py build_ext --inplace

# 環境全体への再インストール（またはビルド隔離を適用したクリーンなビルド）を行う場合：
uv pip install -e .

# 💡 差分ビルドの注意点（キャッシュの罠）
`setup.py build_ext --inplace` は変更されたソースファイルのみをビルドするため高速ですが、以下の状況で古いキャッシュが残る原因になります：
1. **ヘッダーファイル (`.h`) のみの変更**: ヘッダーファイルを変更しても、それを取り込む `.cpp` ファイル自体に変更がない場合、コンパイラが差分を検知できず再コンパイルを実行しないことがあります。
2. **コンフィグ (`setup.py` のフラグ等) の変更**: ビルド設定を変更しても、キャッシュされたオブジェクトファイル（`.obj`）がそのまま使われます。

ビルドがおかしいと感じた場合や、ヘッダー定義を書き換えた後は、以下のコマンドでキャッシュをクリアしてフルビルドを強制してください：
```bash
# ビルドキャッシュを完全消去
uv run python setup.py clean --all

# その後、再ビルドを実行
uv run python setup.py build_ext --inplace
```

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

### CPU命令セットの最適化フラグ (SIMD / AVX2)

`setup.py` は既定で **AVX2 までを固定ターゲット**としてコンパイルします（Windows は `/arch:AVX2`、Linux/macOS は `-mavx2`）。ARM 系（Apple Silicon 等）ではこれらのフラグが存在しないため、自動的に付与されません。

ビルドしたマシンと実行するマシンが同一である場合（学習用マシンなど）は、環境変数を指定することでネイティブ最適化を有効にできます。

```bash
GODFIELD_MARCH_NATIVE=1 uv run python setup.py build_ext --inplace
```

> **⚠️ 注意**: `-march=native` はビルドしたマシンのCPUに固有の命令を埋め込むため、生成されたバイナリを**別のCPUを持つマシンへ持ち込むと不正命令で異常終了します**。CI でビルドして配布する場合や、複数マシンで `.pyd` / `.so` を共有する場合は指定しないでください。

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
Python側には `InternalState` 構造体がそのまま公開されているため、宣言的テストDSL (`tests/core/dsl.py`) を使って任意のHPや手札の盤面状況を直接注入し、マイクロステップ単位で詳細なアサーションが可能です。乱数も `RollKind` ごとに値を注入できるため、確率イベントの分岐をシードの総当たりではなく宣言的に検証できます。

テストは役割ごとに分かれています。

| ディレクトリ | 対象 |
| --- | --- |
| `tests/core/` | C++ ゲームエンジン（ルール・フェイズ遷移・イベント） |
| `tests/rl/` | 学習まわり（観測レイアウト・方策・報酬・リーグ） |
| `tests/visualizer/` | 表示（ログの文言・カードのラベル） |

## 現在のプロジェクト進捗状況 (Current Project Progress)

C++ 側でゴッドフィールドの複雑なルール、例外、フェイズ遷移を正確にシミュレーションするゲームエンジンが動いており、その上で **MaskablePPO による強化学習** を回している段階です。

- **エンジン**: 1万並列の `EnvPool` で毎秒100万ステップ規模。`RollKind` による乱数注入で確率イベントを宣言的に検証
- **学習**: Transformer で観測を要約し、4GPU の非同期リーグ（自己対戦＋手書き方策）で学習。勾配チェックポイントと bfloat16 で大きいモデルでもバッチを確保する
- **診断**: 勝率だけでは方策の潰れを見つけられないため、`tools/diagnose_policy.py` などで「どの局面で何を間違えているか」を測る

エンジン・学習・表示の正当性は 1100 件超の単体テストで検証しています。

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

開発を始めるとき:
- [`docs/core_architecture.md`](./docs/core_architecture.md): C++コアの構造。`InternalState` の各フィールドが「なぜその形なのか」。
- [`docs/testing_guide.md`](./docs/testing_guide.md): テストの書き方。乱数の固定方法と、空のテストを書かないためのチェックリスト。

ゲーム仕様:
- [`docs/rules.md`](./docs/rules.md): ゴッドフィールドの詳細なゲームルール。
- [`docs/phase_specifications.md`](./docs/phase_specifications.md): フェイズ遷移とターン終了処理の詳細。
- [`docs/special_cards.md`](./docs/special_cards.md): 特殊な挙動を持つカードの仕様。
- [`docs/dream_curse.md`](./docs/dream_curse.md): 夢状態の仕様と夢グループの分類。
- [`docs/event_log_spec.md`](./docs/event_log_spec.md): イベント履歴に載る種別と、その配信条件。

データと学習:
- [`docs/card_schema.md`](./docs/card_schema.md): カード定義YAML/JSONのデータスキーマ仕様。
- [`docs/rl_architecture.md`](./docs/rl_architecture.md): 観測・行動・リーグ学習・診断の構成。
- [`docs/hand_value_nn.md`](./docs/hand_value_nn.md): 勝敗value推定NNのデータ収集・学習・artifact・reward shapingへの接続。
- [`docs/rl_history.md`](./docs/rl_history.md): 何を試して何が起きたかの記録。MLPからTransformerへ、リーグ学習で踏んだ罠、失敗した実験とその原因。
- [`EXPERIMENTS.md`](./EXPERIMENTS.md): 実験ディレクトリ、Git管理境界、run ID、metadataの共通設計。

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
4. **取引系カード（売る・買う）の重複を考慮したスマート価格バッジ**:
   * メインフェイズ中に使用（仮置き）されたトリガーカード自体の価格バッジは表示されません。
   * 手札や仮置き場に残っている「取引対象の同一カード」には、正しく `¥5` が価格バッジとして表示されます。
   * 仮置きリスト内のアイテムの合計価格（売値）は、トリガー分を除外して正確に計算され、合計バッジ（`¥5` 等）として自動算出されます。
5. **文言のローカライズとアクションの動的変更**:
   * 取引・雑貨受諾時のボタンラベルを、従来の「断る」から「受け入れる」に統一。
   * スーパーミラーなどの反射カードをステージング（仮置き）した場合は、動的に「はね返す」にボタン表記が変更されます。
   * 購入選択フェイズ時は、選択肢が「買う / 買わない」に適切にローカライズされています。
6. **戦闘・状態情報の配信ダッシュボード**:
   * 現在のターンやゲームフェイズに加え、攻撃の方向と詳細（例:「プレイヤー 0 から プレイヤー 1 へ 10 の攻撃中 (属性: 火)」）を表示する警告アラートがリアルタイムで更新されます。
7. **超コンパクトなステータスバー表示**:
   * HP/MP/所持金を1行にまとめ、守護神や病・災いなどの各種状態異常は最小限の極小バッジとして並列配置。手札エリアを広々と見渡せます。
8. **対戦操作とAI自動化の切り替え**:
   * 画面上のトグルで「対戦相手のAI操作（自動ターン進行）」を有効/無効に切り替えられます。無効にすることで、**1台の画面でプレイヤー0とプレイヤー1を交互に操作するパス＆プレイ（ローカル対戦）**が可能です。
9. **引き分け（同時死亡）のゲームオーバー検知**:
   * 相打ち（土星の指輪による反射等）によって両者のHPが同時に0以下になった場合、双方のカラムの終了オーバーレイに正しく「引き分け」が表示されます。
10. **仮置き場をテーブル上部に配置**:
   * 自分と相手が現在出しているカード（解決待ち状態）を、手札のすぐ上に配置することで、実機と同じテーブル上のプレイ感を再現しています。

### 起動と確認方法

以下のコマンドを実行して可視化用サーバーを起動します：

```bash
# サーバーの起動
uv run python visualize_server.py
```

サーバーが起動したら、ブラウザで以下のURLを開いてください：
👉 **[http://localhost:8000/](http://localhost:8000/)**

#### 対戦相手を選ぶ

画面から相手を切り替えられます。

| 相手 | 中身 |
| --- | --- |
| `league_v5_50M` | **学習済みの方策**（既定）。5000万ステップ・4GPUのリーグ学習 |
| `strategic` | 人手で書いた方策。買う・売る・捨てるの方針を持つ |
| `heuristic` | 単純な規則。対象は常に相手 |
| `random` | 合法手から一様に選ぶ |

学習済みモデルは `assets/models/*.zip` を起動時に読み込みます。ここに置けば
複数を並べて選べます。ただし**観測や特徴抽出器を変えると古いモデルは読めなく
なります**。読めないものは警告を出して飛ばすので、人手の方策では遊べます。

`league_v5_50M` の強さは、席を入れ替えて各3000局での実測で

| 相手 | 勝率 |
| --- | --- |
| `strategic` | 45.8% |
| `heuristic` | 93.4% |
| `random` | 97.0% |

です。**人手の方策にはまだ勝てていません。** 経緯と原因の切り分けは
[`docs/rl_history.md`](./docs/rl_history.md) にあります。

---

## 学習用サーバーについて (Training Server Environment)

強化学習（RL）の本番学習には、計算資源の豊富な専用の学習用サーバーを利用します。

### ハードウェア仕様
* **CPU**: AMD EPYC 7452 32-Core Processor
* **GPU**: NVIDIA RTX 3090 × 4
* **OS**: Linux (Ubuntu) - 最新のGPUドライバ適用済み

### アクセス方法
学習用サーバー `istanbul02` には、踏み台サーバー `pisa` を経由して SSH 接続します。
ローカルマシンの `~/.ssh/config` 等でプロキシジャンプ（ProxyJump）の設定が行われている前提で、以下のコマンドで直接アクセス可能です。

```bash
ssh istanbul02
```

* **ユーザー名**: `otani`
* **作業ディレクトリ**: `/home/otani/GodFieldAI`

### GitHubへのアクセス (SSH Agent Forwarding)
サーバー上でのリポジトリの clone や pull などの Git 操作は、ローカルマシンの SSH 鍵を転送する **SSH Agent Forwarding** を利用して行います。
これにより、サーバー上に直接秘密鍵を配置することなく安全に GitHub へアクセス可能です。

### 学習の起動

**ヘッダ（`.h`）を変更した場合は必ずクリーンビルドしてください。** 増分ビルドでは
再コンパイルされず、エラーも出ないまま古いバイナリで動き続けます（観測レイアウトを
変えたのに古い次元のまま数十時間学習する、という事故が起きます）。

```bash
cd ~/GodFieldAI && git pull
uv run python setup.py clean --all && uv run python setup.py build_ext --inplace
uv run python -c "import godfield_core as g; print(g.OBSERVATION_FEATURE_SIZE)"
```

最後の1行で、期待した観測次元になっているかを必ず確認してください。

tmux でセッションを永続化してから起動します（スクリプトは全ワーカーの終了まで
制御を返しません）。

```bash
tmux new -s league ./scripts/run_league.sh
```

`Ctrl+b` → `d` でデタッチ、`tmux attach -t league` で復帰します。

起動時に観測の次元・プールの場所・ワーカーごとの更新回数が表示されるので、
**意図した設定になっているかここで確認してください**。150秒後に生存確認が入り、
起動に失敗したワーカーがあればログを出して全体を停止します。

### 進行の確認

```bash
tail -f logs/league_worker_0.log            # ログ
tensorboard --logdir logs/league_tb         # 学習曲線
grep approx_kl logs/league_worker_3.log | tail -1   # 更新量（0.03前後なら健全）
```

`approx_kl` は最初に見るべき指標です。0.1 を大きく超えている場合、1回の更新で
方策が変わりすぎていて学習が進みません（`scripts/run_league.sh` の worker 表を参照）。

### 学習を止める

```bash
pkill -f run_league.sh; pkill -f "train.py"
```

親スクリプトを先に止めないと `wait` が残ります。

### やり直す

観測のレイアウトを変えた場合、**過去のモデルは読めません**。新しいプールを
指定してください（古いプールを指すと起動時に落ちます）。

```bash
POOL_DIR=models/league_v4 ./scripts/run_league.sh
```
