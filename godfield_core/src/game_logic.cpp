#include "game_logic.h"
#include "game_logic_internal.h"

/**
 * @brief ゲームのルール適用と状態更新 (Game Logic Core)
 *
 * 与えられた `InternalState` と選択された `action` を元に、
 * ゴッドフィールドのルールに従って状態を1マイクロステップ分だけ進める純粋なロジック関数。
 * 各フェイズごとの処理は `phase_handlers.cpp` 内の `step_phase_X` 関数に委譲されます。
 *
 * @param state 現在のゲーム状態 (参照渡しの破壊的更新)
 * @param action 実行されたアクションID
 */
void step_game(InternalState& state, ActionType action) {
    if (state.is_done) return;

    int me = state.current_actor_id;
    int opp = 1 - me;

    // 行動の合法性チェック
    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    if (action < 0 || action >= ACTION_SPACE_SIZE || !legal_actions[action]) return;

    // 現在のフェイズに応じた個別ハンドラの呼び出し
    switch (state.current_phase) {
        case GamePhase::PHASE_MAIN:
            step_phase_main(state, action, me, opp);
            break;
        case GamePhase::PHASE_MAIN_TARGET_SELECT:
            step_phase_main_target_select(state, action, me, opp);
            break;
        case GamePhase::PHASE_ATTACK_PLUS:
            step_phase_attack_plus(state, action, me, opp);
            break;
        case GamePhase::PHASE_DEFENSE:
            step_phase_defense(state, action, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_PLUS:
            step_phase_miracle_plus(state, action, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_DEFENSE:
            step_phase_miracle_defense(state, action, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT:
            step_phase_sell_select(state, action, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT_MIRROR:
            step_phase_sell_select_mirror(state, action, me, opp);
            break;
        case GamePhase::PHASE_BUY_SELECT_MIRROR:
            step_phase_buy_select_mirror(state, action, me, opp);
            break;
        case GamePhase::PHASE_SUNDRY_SELECT_MIRROR:
            step_phase_sundry_select_mirror(state, action, me, opp);
            break;
        case GamePhase::PHASE_BUY:
            step_phase_buy(state, action, me, opp);
            break;
        case GamePhase::PHASE_EXCHANGE_HP:
        case GamePhase::PHASE_EXCHANGE_MP:
            step_phase_exchange(state, action, me, opp);
            break;
        case GamePhase::PHASE_DISCARD:
            step_phase_discard(state, action, me, opp);
            break;
        default:
            break;
    }

    // ターン終了処理 (PHASE_END) の自動解決ループ
    while (!state.is_done) {
        if (state.current_phase == GamePhase::PHASE_END) {
            cleanup_phase_end(state);
            state.current_turn++;
            state.current_actor_id = state.current_turn % 2;
            state.current_phase = GamePhase::PHASE_MAIN;
        } else {
            break;
        }
    }
}

/**
 * @brief 現在のゲーム状態において、どのアクションが合法手かを判定してマスクを返します。
 *        各フェイズごとのチェックは `legal_actions.cpp` 内の `legal_phase_X` 関数に委譲されます。
 *
 * @param state 現在のゲーム状態
 * @param legal_actions 長さACTION_SPACE_SIZEのbool配列。結果が格納されます。
 */
void get_legal_actions(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE]) {
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) legal_actions[i] = false;
    if (state.is_done) return;

    int me = state.current_actor_id;
    int opp = 1 - me;

    switch (state.current_phase) {
        case GamePhase::PHASE_MAIN:
            legal_phase_main(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MAIN_TARGET_SELECT:
            legal_phase_main_target_select(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_ATTACK_PLUS:
            legal_phase_attack_plus(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_DEFENSE:
            legal_phase_defense(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_PLUS:
            legal_phase_miracle_plus(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_DEFENSE:
            legal_phase_miracle_defense(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT:
            legal_phase_sell_select(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT_MIRROR:
            legal_phase_sell_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_BUY:
            legal_phase_buy(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_BUY_SELECT_MIRROR:
            legal_phase_buy_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SUNDRY_SELECT_MIRROR:
            legal_phase_sundry_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_EXCHANGE_HP:
        case GamePhase::PHASE_EXCHANGE_MP:
            legal_phase_exchange(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_DISCARD:
            legal_phase_discard(state, legal_actions, me, opp);
            break;
        default:
            break;
    }
}

/**
 * @brief 現在のゲーム状態において、合法手が1つしかない場合はそのアクションIDを返します。
 *        （自動進行用の判定で使用されます）
 *
 * @param state 現在のゲーム状態
 * @return 合法アクションが唯一存在する場合はそのアクションID。それ以外（0個、または2個以上）の場合は -1。
 */
int get_single_legal_action(const InternalState& state) {
    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    
    int valid_count = 0;
    int last_valid = -1;
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
        if (legal_actions[i]) {
            valid_count++;
            last_valid = i;
            if (valid_count > 1) return -1;
        }
    }
    if (valid_count == 1) return last_valid;
    return -1;
}
