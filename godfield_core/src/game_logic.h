#pragma once
#include "types.h"
#include <vector>
#include <random>
#include <string>
#include <pybind11/pybind11.h>

extern std::vector<CardFeatures> g_card_registry;
extern std::discrete_distribution<int> g_drop_distribution;

/**
 * Initializes the global card registry and drop distribution for the game.
 * Must be called once before any game logic or environments are run.
 */
void init_game_logic(const pybind11::list &cards);

/**
 * Draws a random card ID from the initialized game logic registry.
 * Throws an exception if init_game_logic has not been called.
 */
int draw_card(InternalState& state);

/**
 * Registry accessors for python side testing and observation building
 */
int get_registry_size();
std::string get_card_name(int card_id);

/**
 * @brief ゲームのルール適用と状態更新 (Game Logic Core)
 *
 * 与えられた `InternalState` と選択された `action` を元に、
 * ゴッドフィールドのルールに従って状態を1マイクロステップ分だけ進める純粋なロジック関数。
 * 
 * @param action 
 *  0~8: 手札選択 (0~8番目のカード)
 *  18:  決定 / 相手を指定して実行など
 */
void step_game(InternalState& state, ActionType action);

/**
 * @brief 現在のゲーム状態において、どのアクションが合法手かを返す
 * 
 * @param state 現在のゲーム状態
 * @param legal_actions 長さACTION_SPACE_SIZEのbool配列（結果が格納される）
 */
void get_legal_actions(const InternalState& state, bool legal_actions[ACTION_SPACE_SIZE]);

/**
 * @brief 現在のゲーム状態において、合法手が1つしかない場合はそのアクションIDを返す
 *        それ以外（0個、または2個以上）の場合は -1 を返す
 */
int get_single_legal_action(const InternalState& state);

/**
 * @brief 新しいゲームの初期状態を作ります（初期HP/MP/所持金・初期手札・強制手の消化まで）。
 *
 * 開始局面に強制手（合法手が1つしかない状況）が続くことがあるため、プレイヤーの
 * 入力が必要になるところまで進めて返します。その過程で決着してしまった場合は
 * シードを変えて配り直し、MAX_NEW_GAME_ATTEMPTS 回試しても開始できなければ例外を投げます。
 *
 * 初期値やカードの配り方はゲームのルールなので、環境プール（EnvPool）ではなく
 * ここが持ちます。
 */
void init_new_game(InternalState& state, int seed);

/**
 * @brief 「解決中の攻撃・取引」に関するフィールドを未設定の番兵に戻します。
 *
 * これらは 0 が有効な値（プレイヤーID 0 / カードID 0）になるため、ゼロ埋めした
 * 状態を「まっさらな盤面」として扱ってはいけません。init_new_game() と、
 * テスト用の clear_state() の両方から呼びます。
 */
void reset_pending_resolution(InternalState& state);

/**
 * @brief 指定プレイヤーの視点での部分観測（Observation）を構築して書き込む
 */
void make_observation(const InternalState& state, int player_id, Observation& obs);

/**
 * @brief 指定プレイヤーの視点での部分観測（Observation）を新しく構築して返却する
 */
Observation get_observation(const InternalState& state, int player_id);

