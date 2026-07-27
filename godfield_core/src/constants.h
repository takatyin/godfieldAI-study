#pragma once
#include "rl_config.h"

// 確率定数 / Probability Constants
constexpr int BOUNCE_SUCCESS_RATE = 50;
constexpr int MARS_RING_RATE = 75;
constexpr int GUARDIAN_LEAVE_RATE = 10;
constexpr int ASCENSION_BOW_HIT_RATE = 75;
constexpr int SICKNESS_WORSEN_RATE = 5;
constexpr int GUARDIAN_ACT_RATE = 25;

// 守護神が行動する際、5種の行動のどれを選ぶかの累積閾値（0..99 の抽選値と比較する）。
// roll < 30 なら行動1、roll < 55 なら行動2 ... のように先頭から判定する。
// テスト側はこの表から「行動 N を狙う代表値」を導出するため、閾値をここ以外に書かないこと。
constexpr int GUARDIAN_ACT_CHOICE_COUNT = 5;
constexpr int GUARDIAN_ACT_CHOICE_THRESHOLDS[GUARDIAN_ACT_CHOICE_COUNT] = {30, 55, 75, 90, 100};

// 終末の時（APOCALYPSE_TURN 以降）のドローで悪魔カードが出る累積確率（%）。
// 0..100 の抽選値と先頭から比較し、どれにも当たらなければ通常の山札抽選になる。
// 対応するカードは combat_resolution.cpp の APOCALYPSE_DEVILS が持つ。
// テスト側はこの表から「狙った悪魔を引く代表値」を導出するため、閾値をここ以外に書かないこと。
constexpr int APOCALYPSE_DEVIL_COUNT = 5;
constexpr int APOCALYPSE_DEVIL_THRESHOLDS[APOCALYPSE_DEVIL_COUNT] = {7, 12, 15, 20, 25};

// 夢状態でドローしたカードが偽装される確率（%）。残りはそのまま正しく見える。
// 偽装される場合は同じ夢グループの「自分以外」のカードから一様に選ばれるため、
// 「見た目が変わっていないこと」は夢がかかっていない証拠にはならない。
constexpr int DREAM_DISGUISE_RATE = 50;

// のこぶんぶんが持つ基本攻撃回数。＜蜃気楼＞の枚数がこれに乗算される。
constexpr int SAW_BOOM_BOOM_ATTACK_COUNT = 2;

// 太陽のお守りで復活したときのHP。
constexpr int SUN_AMULET_REVIVE_HP = 10;

// 昇天弓がターン終了時に発射されるときの攻撃力（手札上の攻撃力とは別物）。
constexpr int ASCENSION_BOW_TRIGGERED_POWER = 30;

// Observation 配列次元 / Observation Array Dimensions
constexpr int NUM_SICKNESS_TYPES = 5;
constexpr int NUM_CURSE_TYPES = 4;
constexpr int NUM_GUARDIAN_TYPES = 11;
constexpr int MAX_HAND_SIZE = 18;     // 最大手札枚数（使用済み奇跡含む）
constexpr int CARD_EMPTY = -1;        // 手札スロットが空であることを示す仮想カードID
constexpr int ACTION_SPACE_SIZE = 122; // 行動の次元数
constexpr int HISTORY_LENGTH = 64;    // イベント履歴の長さ（リングバッファ、2のべき乗推奨）

// ゲームの進行と終末の時（Apocalypse）用パラメータ
constexpr int APOCALYPSE_TURN = 150;   // 終末の時が発動するターン数
// 観測 turn_progress の正規化に使う基準「ターン」数（ステップ数ではない）。
// ゲームの打ち切りには使わない（膠着から終末の時に入る展開も学習させるため、
// 決着はゲームルールにのみ委ねる）。current_turn はこの値を超えうるので turn_progress 側で飽和させる。
// 実測では決着の中央値が17ターン、最長でも109ターンで、300を超える対戦は観測されていない。
// 学習させたい膠着局面（150ターン以降）が 0.5〜0.83 に散る値として300を採用している。
constexpr int TURN_PROGRESS_SCALE_TURNS = 300;

// カードドローの抽選テーブル（drop_rate の重み分だけカードIDを展開した配列）の上限。
// 実データでは合計 500 要素（2KB）で L1 に収まる。極端な drop_rate を設定した際に
// メモリを食い潰さないための安全弁で、超えた場合は init_game_logic が例外を投げる。
constexpr int MAX_DRAW_TABLE_ENTRIES = 1 << 20;

enum ActionType {
    ACTION_SELECT_HAND_0 = 0,
    ACTION_SELECT_HAND_1 = 1,
    ACTION_SELECT_HAND_2 = 2,
    ACTION_SELECT_HAND_3 = 3,
    ACTION_SELECT_HAND_4 = 4,
    ACTION_SELECT_HAND_5 = 5,
    ACTION_SELECT_HAND_6 = 6,
    ACTION_SELECT_HAND_7 = 7,
    ACTION_SELECT_HAND_8 = 8,
    ACTION_SELECT_HAND_9 = 9,
    ACTION_SELECT_HAND_10 = 10,
    ACTION_SELECT_HAND_11 = 11,
    ACTION_SELECT_HAND_12 = 12,
    ACTION_SELECT_HAND_13 = 13,
    ACTION_SELECT_HAND_14 = 14,
    ACTION_SELECT_HAND_15 = 15,
    ACTION_SELECT_HAND_16 = 16,
    ACTION_SELECT_HAND_17 = 17,

    ACTION_TARGET_OPP = 18,
    ACTION_DEAL_YES = 18,

    ACTION_TARGET_SELF = 19,
    ACTION_DEAL_NO = 19,
    ACTION_CONFIRM = 19,

    ACTION_PRAY = 20,
    ACTION_DISCARD = 21,

    ACTION_NUM_0 = 22, ACTION_NUM_1 = 23, ACTION_NUM_2 = 24, ACTION_NUM_3 = 25, ACTION_NUM_4 = 26,
    ACTION_NUM_5 = 27, ACTION_NUM_6 = 28, ACTION_NUM_7 = 29, ACTION_NUM_8 = 30, ACTION_NUM_9 = 31,
    ACTION_NUM_10 = 32, ACTION_NUM_11 = 33, ACTION_NUM_12 = 34, ACTION_NUM_13 = 35, ACTION_NUM_14 = 36,
    ACTION_NUM_15 = 37, ACTION_NUM_16 = 38, ACTION_NUM_17 = 39, ACTION_NUM_18 = 40, ACTION_NUM_19 = 41,
    ACTION_NUM_20 = 42, ACTION_NUM_21 = 43, ACTION_NUM_22 = 44, ACTION_NUM_23 = 45, ACTION_NUM_24 = 46,
    ACTION_NUM_25 = 47, ACTION_NUM_26 = 48, ACTION_NUM_27 = 49, ACTION_NUM_28 = 50, ACTION_NUM_29 = 51,
    ACTION_NUM_30 = 52, ACTION_NUM_31 = 53, ACTION_NUM_32 = 54, ACTION_NUM_33 = 55, ACTION_NUM_34 = 56,
    ACTION_NUM_35 = 57, ACTION_NUM_36 = 58, ACTION_NUM_37 = 59, ACTION_NUM_38 = 60, ACTION_NUM_39 = 61,
    ACTION_NUM_40 = 62, ACTION_NUM_41 = 63, ACTION_NUM_42 = 64, ACTION_NUM_43 = 65, ACTION_NUM_44 = 66,
    ACTION_NUM_45 = 67, ACTION_NUM_46 = 68, ACTION_NUM_47 = 69, ACTION_NUM_48 = 70, ACTION_NUM_49 = 71,
    ACTION_NUM_50 = 72, ACTION_NUM_51 = 73, ACTION_NUM_52 = 74, ACTION_NUM_53 = 75, ACTION_NUM_54 = 76,
    ACTION_NUM_55 = 77, ACTION_NUM_56 = 78, ACTION_NUM_57 = 79, ACTION_NUM_58 = 80, ACTION_NUM_59 = 81,
    ACTION_NUM_60 = 82, ACTION_NUM_61 = 83, ACTION_NUM_62 = 84, ACTION_NUM_63 = 85, ACTION_NUM_64 = 86,
    ACTION_NUM_65 = 87, ACTION_NUM_66 = 88, ACTION_NUM_67 = 89, ACTION_NUM_68 = 90, ACTION_NUM_69 = 91,
    ACTION_NUM_70 = 92, ACTION_NUM_71 = 93, ACTION_NUM_72 = 94, ACTION_NUM_73 = 95, ACTION_NUM_74 = 96,
    ACTION_NUM_75 = 97, ACTION_NUM_76 = 98, ACTION_NUM_77 = 99, ACTION_NUM_78 = 100, ACTION_NUM_79 = 101,
    ACTION_NUM_80 = 102, ACTION_NUM_81 = 103, ACTION_NUM_82 = 104, ACTION_NUM_83 = 105, ACTION_NUM_84 = 106,
    ACTION_NUM_85 = 107, ACTION_NUM_86 = 108, ACTION_NUM_87 = 109, ACTION_NUM_88 = 110, ACTION_NUM_89 = 111,
    ACTION_NUM_90 = 112, ACTION_NUM_91 = 113, ACTION_NUM_92 = 114, ACTION_NUM_93 = 115, ACTION_NUM_94 = 116,
    ACTION_NUM_95 = 117, ACTION_NUM_96 = 118, ACTION_NUM_97 = 119, ACTION_NUM_98 = 120, ACTION_NUM_99 = 121
};
