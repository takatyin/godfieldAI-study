#pragma once

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
