# **ゴッドフィールド AI環境 (C++) 実装仕様書**

本ドキュメントは、強化学習（PPO等）を用いてゴッドフィールドのAIを学習させるための、C++ベースの超高速・高並列シミュレータ（Vectorized Environment）の実装仕様を定義する。

## **1. 全体アーキテクチャ方針**

* **データと処理の分離**: ゲームの状態（Trivially Copyableな構造体）とゲームロジック（関数群）を完全に分離する。
* **視点の正規化 (Canonicalization)**: AI（Python側）には常に「行動権を持つプレイヤー（Current Actor）」の視点に変換（マスキング等）した観測データを渡す。
* **デュアル・バッファ設計**: C++のみが知る「真の内部状態」と、AIに渡すための「観測バッファ」を別々に管理し、完全なゼロコピー連携と情報隠蔽（カンニング防止）を両立する。

## **2. 定数・ハイパーパラメータ定義**

コードの保守性を高めるため、以下の定数はマクロまたは constexpr として外部定義・一元管理すること。

```cpp
constexpr int MAX_HAND_SIZE = 18;        // 最大手札枚数（使用済み奇跡含む）
constexpr int ACTION_SPACE_SIZE = 21;    // 行動の次元数
constexpr int HISTORY_LENGTH = 64;       // イベント履歴の長さ（リングバッファ、2のべき乗推奨）
constexpr int NUM_ENVS = 10000;          // 並列実行するゲーム数（メモリ・コア数に応じて調整）

// ゲームの進行と終末の時（Apocalypse）用パラメータ
constexpr int APOCALYPSE_TURN = 150;     // 終末の時が発動するターン数
constexpr int MAX_EPISODE_TURNS = 300;   // 無限ループ防止用の最大ターン数（到達で引き分け）

// n-step学習用パラメータ
constexpr int N_STEP = 3;                // または 5。報酬を伝播させるステップ数
constexpr float GAMMA = 0.995f;          // 割引率 (ゲーム長 100〜500 stepを想定)
constexpr float WIN_REWARD = 1.0f;       // 勝利時の報酬
constexpr float LOSE_REWARD = -1.0f;     // 敗北時の報酬
constexpr float DRAW_REWARD = 0.0f;      // 引き分け（昇天弓による相打ち、最大ターン超過等）の報酬
```

## **3. データ構造 (Data Structures)**

すべての構造体は `std::memcpy` 可能なプリミティブ型で構成し、キャッシュライン（64バイト）を意識したメモリアライメント (`alignas(64)` または `alignas(32)`) を適用する。

### **3.1 カード共通特徴量フォーマット (CardFeatures)**

疎なベクトル（Sparse Vector）として、全カードのパラメータを固定長で表現する。マスターデータ読み込み時に構築し、C++のメモリ上に保持する。

```cpp
struct CardFeatures {
    float is_attack;
    float is_defense;
    float is_miracle;
    float is_used_miracle;  // 0: 未使用, 1: 使用済み（盤面展開済み）
    float price;            // 正規化された値段
    float atk_power;        // 攻撃以外は 0.0
    float def_power;        // 防具以外は 0.0
    float mp_cost;          // 奇跡以外は 0.0
    float element_type[7];  // 無, 火, 水, 木, 土, 光, 闇 (One-hot)
    // その他必要な効果フラグ...
};
```

### **3.2 イベント構造体 (GameEvent)**

履歴に残す過去の行動記録。1つのイベントを固定サイズで表現する。

```cpp
struct GameEvent {
    int actor;         // 0: 自分(観測者), 1: 相手 (視点正規化時に XOR で反転する)
    int phase;         // フェイズID
    int action_type;   // 攻撃, 防御, スルー, 買う, 等
    int card_id;       // 使用されたカードID (非公開情報は 0 にマスキング)
    float damage;      // 確定したダメージ量などのスカラー値
};
```

### **3.3 観測バッファ (Observation)**

Python（AI）にゼロコピーで渡すための構造体。内部状態から「翻訳」されて生成される。

```cpp
struct alignas(64) Observation {
    // 数値ステータス (0.0 ~ 1.0 に正規化して渡す)
    float hp_me, hp_opp;
    float mp_me, mp_opp;
    float money_me, money_opp;
    
    // 状態異常・病・守護神 (排他要素は独立したOne-hot次元として表現)
    float sickness_me[5];         // 病 (なし, 風邪, 熱病, 地獄病, 天国病)
    float sickness_opp[5];
    float status_ailments_me[4];  // 霧, 閃光, 暗雲, 夢 (Multi-hot)
    float status_ailments_opp[4];
    float guardian_me[11];        // 守護神 (なし=0, 火星神=1, ..., 月神=10)
    float guardian_opp[11];
    
    // 計算済みサポート数値と特殊状態
    float incoming_damage;        // 飛んできている総ダメージ
    float current_staged_defense; // 現在仮置きしている防具の合計
    float is_apocalypse;          // 終末の時フラグ (通常=0.0, 150ターン以降=1.0)
    
    // フェイズ情報
    float phase_one_hot[7];       // 現在のフェイズ (State1 ~ State6, StateM)

    // カードID群 (Embedding層へ入力)
    int hand_cards[MAX_HAND_SIZE];           // 自分の手札（夢状態ならC++で偽装済みIDを入れる）
    int staged_cards[MAX_HAND_SIZE];         // 現在の仮置き場
    int opponent_hand_cards[MAX_HAND_SIZE];  // 相手の手札（非公開=0, 既知のカード・使用済み奇跡=実ID）
    int pending_card;                        // 注目カード（飛んできた攻撃や買う対象など。なし=0）

    // イベント履歴（リングバッファ）
    GameEvent history[HISTORY_LENGTH];
    int history_head;                        // 次に書き込むインデックス

    // 合法手マスク
    float action_mask[ACTION_SPACE_SIZE];    // 1.0 = 選択可能, 0.0 = 選択不可
};
```

### **3.4 内部状態 (InternalState)**

C++だけが知る真のゲーム状態。

```cpp
struct alignas(64) InternalState {
    std::mt19937 rng;                     // ゲーム固有の乱数生成器
    int current_actor_id;                 // 現在行動権を持つプレイヤー (0 or 1)
    int current_turn;                     // 現在の実際のターン数 (終末の時判定用)
    
    // 基本ステータス群 (C++内では正規化前の生の値で管理)
    int hp[2], mp[2], money[2];
    int sickness[2];                      // 0:なし, 1:風邪, 2:熱病, 3:地獄病, 4:天国病
    int status_ailments[2];               // 状態異常のビットフラグ
    int guardian[2];                      // 守護神ID (0~10)
    
    // 手札情報と「既知のカード」の管理
    int true_hand[2][MAX_HAND_SIZE];      // 両プレイヤーの真の手札
    bool is_known_to_opp[2][MAX_HAND_SIZE]; // 相手に中身がバレているか (買うで見られた、売るで渡された等)
    
    // デッキ(山札)
    // ...
    
    // n-step学習用ローカルキュー（詳細は後述）
    // ...
};
```

## **4. 行動空間とマイクロステップ**

### **4.1 21次元のアクション定義 (Action Space)**

AIは常に長さ21のロジット（確率）を出力する。マスクにより強制的に選択肢が絞られ、ターゲット（自分か相手か）もここで決定する。

* 0 ～ 17: 手札のインデックスを選択（カードを仮置き場へ）
* 18: **確定（相手をターゲット） / 買う(YES) / （防具ゼロのままなら）そのまま受ける**
* 19: **確定（自分をターゲット） / 買わない(NO)**
* 20: **祈る（ドロー）**

※メインフェイズ等において、自分にも相手にも使えるカード（武器や奇跡、回復など）を仮置きした場合、C++のアクションマスクは 18 と 19 の両方を 1.0 にして、AIに高度なターゲット選択（自分撃ち等）を委ねる。

※防御フェイズにおいて、防具を置かないまま 18 を押すことが「そのままダメージ等を受ける」行動として処理される。

### **4.2 マイクロステップの処理フロー (step関数)**

1. C++は行動を受け取り、`current_actor_id` の行動として `InternalState` を更新する。
2. アクションが「仮置き（0~17）」の場合、状態を更新し、重ね掛け可能なカードのマスクのみを 1 にした新しい `Observation` を生成。
3. アクションが「確定（18 または 19）」あるいは「祈る（20）」の場合、C++は乱数を振り、指定されたアクションやターゲットに基づいてダメージや効果を解決する。
4. 行動権が相手に移る場合、`current_actor_id` を反転させ、相手視点で `Observation` を生成する。
   * **マスキング処理:** `true_hand` を `opponent_hand_cards` にコピーする際、相手の使用済み奇跡、および `is_known_to_opp` が true のカードのみ真のIDを入れ、それ以外は 0 にマスクする。
   * **イベント履歴の反転:** `GameEvent::actor` を現在の行動プレイヤーから見て 0(自分) か 1(相手) になるよう、XOR演算で高速に反転させて渡す。
   * **終末の時の判定:** `current_turn >= APOCALYPSE_TURN` であれば、`is_apocalypse` フラグを立てる。

## **5. 報酬設計と n-step ローカルバッファ**

スパース報酬問題と、数万ゲームの巨大バッファ圧迫を防ぐための実装仕様。

### **5.1 ローカルバッファの構造**

`InternalState` 内に、各プレイヤーごとの小さなキューを持たせる。

```cpp
struct Transition {
    Observation state;  // その瞬間の観測
    int action;         // 選んだ行動
    float reward;       // そのターンの報酬
};

// InternalStateのメンバとして追加
Transition n_step_queue_p0[N_STEP];
Transition n_step_queue_p1[N_STEP];
int queue_size_p0 = 0, queue_size_p1 = 0;
```

### **5.2 精算（Flush）ロジック**

* マイクロステップが進むごとに、行動したプレイヤー側のキューに `Transition` を追加する。
* キューのサイズが `N_STEP` に達した場合、一番古いデータ（インデックス0）を精算し、Pythonと共有するグローバルな Replay Buffer に以下の形式で書き込む。
  **記録する1単位:** (最初のState, 最初のAction, N_STEP分の割引報酬和, 現在のState)
  ※割引報酬和 = ![image1]
* **ゲーム終了時（Done）または上限到達時（Truncation）の特別処理:** 勝敗（+1.0, -1.0）が確定した瞬間、または `current_turn >= MAX_EPISODE_TURNS` に到達し強制引き分け（0.0）となった瞬間、両プレイヤーのキューに残っているすべての未精算データを、その終了報酬を用いて直ちに割引計算し、グローバルバッファに全放出（Flush）する。この時の次状態（Next State）はダミー（0埋め）とする。

## **6. 環境プール (EnvPool) の並列設計**

10,000ゲームの極限効率化を実現するための管理者クラス。

* **メモリ確保**: `std::vector<InternalState>` と `std::vector<Observation>` を事前に一括確保。
* **マルチスレッド**: `std::thread` を用いたカスタムワーカープールを構築。
  * **ロックフリーキュー**: 推論待ちになった環境ID（env_id）を `moodycamel::ConcurrentQueue` 等で管理。
  * **スレッドピニング**: 各スレッドを特定の物理コアに固定（OS依存API）し、キャッシュヒット率を最大化する。
  * **False Sharing対策**: 前述の `alignas(64)` により、各ゲーム状態がキャッシュラインを跨がないようにする。

## **7. Python / Pybind11 API インターフェース**

C++で実装した `EnvPool` をPythonモジュールとして公開し、OpenAI Gym (Gymnasium) に似たAPIを提供する。

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

class EnvPool {
public:
    // ゲームの初期化
    // 運の要素を完全に同一にして複数エージェントを評価・比較する
    // Duplicate Evaluation に備え、シードの固定機能は必須とする。
    void reset(int seed);
    
    // AIの推論結果の配列を受け取り、シミュレーションを進行する
    // actions は [バッチサイズ] のnumpy配列 (int32)
    void step_all(pybind11::array_t<int> actions);
    
    // 推論待ちになったゲームの Observation バッファのポインタを返す
    // [バッチサイズ, 観測次元数] の float32 配列としてPython側にゼロコピーで覗かせる
    pybind11::array_t<float> get_observations();
    
    // どのゲームIDが推論待ちか（Python側で結果をマッピングするため）
    pybind11::array_t<int> get_ready_env_ids();
};
```

## **8. 強化学習エージェントの学習方針**

### **8.1 アルゴリズムの選定: PPO (Proximal Policy Optimization)**

行動空間が完全に離散化された21次元の環境に対し、学習の安定性とハイパーパラメータの堅牢性に優れる PPO を採用する。

C++側の10,000並列環境から生成される膨大な経験データを、方策勾配法によって高速に学習させる。

### **8.2 自己対戦 (Self-Play)**

視点の正規化（常に相手と自分を反転させる）により、エージェントは1つのニューラルネットワークモデルを共有しながら自分自身と対戦する。

これにより、特定の戦術に過学習することなく、ナッシュ均衡に近づくプレイングを自律的に獲得する。

### **8.3 スパース報酬問題と補助タスク**

勝敗確定まで報酬がゼロである期間（スパース報酬）における学習速度を担保するため、AIのネットワーク（Critic等）に以下の補助予測タスク（Auxiliary Tasks）を課す。

* **次ターンのHP/MP予測:** 「この行動を取った後、自分と相手のステータスはどう変動するか」を予測させる。
* **相手の手札推論 (Belief State):** 「0埋め」された相手の手札スロットの中身について、イベント履歴から真のカードを予測させる。

## **9. C++環境実装で求められる絶対要件 (コーディングの鉄則)**

これからのC++実装フェーズにおいて、バグの温床を根絶し極限効率を達成するために、以下の要件を**絶対遵守**する。

1. **Trivially Copyable なデータ構造の徹底**
   * 盤面状態やイベント履歴の構造体には、`std::string`、仮想関数 (`virtual`)、動的コンテナ (`std::vector` など)、ポインタを**一切含めない**こと。
   * 全て固定長の配列とプリミティブ型で構成し、`std::memcpy` で一瞬でコピー・移動できるようにする。
2. **厳密なルール・ステートマシン（アクションマスクの絶対的正確性）**
   * 「アクションマスクの生成」がAIの命綱となる。「今は攻撃フェーズの1枚目」「今は防御フェーズで、相手は火属性武器の攻撃をしてきている」といったゲームの進行状態（State）を厳密に管理する。
   * **絶対にルール違反の行動が 1.0（選択可能）にならないようにする。** マスクに抜け穴があると、AIは瞬時にそれを見つけ出してゲームを破壊する。
3. **算数と確率のオフロード（AIに計算させない）**
   * **AIは数学者ではなくゲーマーである。** 飛んできているダメージ量の計算や、防具の合計値の計算など、C++で確定できる算数は全てC++側で行い、結果を Observation に乗せて渡す。
   * 確率的なカードの効果（命中率など）は、AIが「確定」した直後にC++側でサイコロ（乱数）を振り、その結果を「事後報告」としてイベント履歴に書き込む。AIに未来の確率を予測させつつも、乱数シードそのものは隠蔽する。