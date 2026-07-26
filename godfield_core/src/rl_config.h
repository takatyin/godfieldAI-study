#pragma once

// ============================================================================
// 強化学習 (RL) パイプライン用定数 / RL Configuration Constants
// ============================================================================

constexpr int NUM_ENVS = 10000;       // 並列実行するゲーム数（メモリ・コア数に応じて調整）
constexpr int N_STEP = 3;            // または 5。報酬を伝播させるステップ数
constexpr float GAMMA = 0.995f;      // 割引率 (ゲーム長 100〜500 stepを想定)
constexpr float WIN_REWARD = 1.0f;   // 勝利時の報酬
constexpr float LOSE_REWARD = -1.0f; // 敗北時の報酬
constexpr float DRAW_REWARD = 0.0f;  // 引き分け（昇天弓による相打ち、最大ターン超過等）の報酬
