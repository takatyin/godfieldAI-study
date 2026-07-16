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
void init_game_logic(pybind11::list cards);

/**
 * Draws a random card ID from the initialized game logic registry.
 * Throws an exception if init_game_logic has not been called.
 */
int draw_card(std::mt19937& rng);

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

// Helper function to resolve ongoing effects/events.
void resolve_events(InternalState& state);
