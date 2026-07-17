#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>

/**
 * @brief メインフェイズ（PHASE_MAIN）における合法アクション（祈る/捨てる/使用可能な手札）を計算します。
 */
void legal_phase_main(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    // 祈る、捨てるができるかのチェック
    if (can_pray(state, me)) legal_actions[ACTION_PRAY] = true;
    if (can_discard(state, me)) legal_actions[ACTION_DISCARD] = true;

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            // 展開済みかつ使用済みの奇跡は使えない
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            CardFeatures &f = g_card_registry[state.true_hand[me][i]];
            
            // 奇跡のMP消費が足りるか（将来的に精霊系カードで0にできる可能性を含めて判定）
            if (!can_afford_staged_plus_card(state, me, i)) continue;
            
            // 売るで売るアイテムがあるか
            if (state.true_hand[me][i] == ID_SELL && !can_sell_card(state, me, i)) continue;
            
            if ((f.usage_timing & TIMING_MAIN_SUNDRY) || (f.usage_timing & TIMING_MAIN_ATK) ||
                (f.usage_timing & TIMING_MAIN_MIRACLE) || (f.usage_timing & TIMING_MAIN_DEAL)) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }
}

/**
 * @brief 対象選択フェイズ（PHASE_MAIN_TARGET_SELECT）における合法アクション（自分/相手）を判定します。
 */
void legal_phase_main_target_select(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_actions[ACTION_TARGET_SELF] = true;
    legal_actions[ACTION_TARGET_OPP] = true;
}

/**
 * @brief 物理攻撃の追加・決定フェイズ（PHASE_ATTACK_PLUS）における合法アクションを計算します。
 *        （追加の攻撃プラスカード、または奇跡MPコスト0化神器、およびターゲットの選択）
 */
void legal_phase_attack_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    bool has_unstable_accuracy = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        CardFeatures &f = get_registry_size() > 0 ? g_card_registry[state.true_hand[me][state.staged_cards[me][i]]] : g_card_registry[0]; // safety fallback
        if (f.accuracy < 100) has_unstable_accuracy = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.true_hand[me][i];
            CardFeatures &f = g_card_registry[card_id];
            
            if (!can_afford_staged_plus_card(state, me, i)) continue;

            bool is_legal_timing = false;
            if (f.usage_timing & TIMING_ATK_PLUS) {
                is_legal_timing = true;
            } else if ((f.usage_timing & TIMING_MIRACLE_PLUS) && is_spiritual_zero_mp_card(card_id)) {
                if (is_last_staged_card_miracle(state, me)) {
                    is_legal_timing = true;
                }
            }

            if (is_legal_timing) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }

    if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
        legal_actions[ACTION_TARGET_OPP] = true;
        legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy && !state.pending_is_group_attack;
    }
}

/**
 * @brief 物理・属性防御フェイズ（PHASE_DEFENSE）における合法アクション（防御属性の整合性、およびCONFIRMの可否）を判定します。
 */
void legal_phase_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    Element atk_element = state.pending_attack_element;
    bool rainbow = false;
    bool has_non_element = false, has_multiple_different_elements = false;
    Element base_def_element = ELEM_NONE;
    bool has_light = false;

    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.true_hand[me][state.staged_cards[me][i]];
        CardFeatures &f = g_card_registry[card_id];
        if (card_id == ID_RAINBOW_CURTAIN) rainbow = true;

        Element e = f.element;
        if (e == ELEM_NONE) has_non_element = true;
        else if (e == ELEM_LIGHT) has_light = true;
        else {
            if (base_def_element == ELEM_NONE) base_def_element = e;
            else if (base_def_element != e) has_multiple_different_elements = true;
        }
    }

    Element current_def_element = ELEM_NONE;
    if (has_non_element || has_multiple_different_elements) current_def_element = ELEM_NONE;
    else if (base_def_element != ELEM_NONE) current_def_element = base_def_element;
    else if (has_light) current_def_element = ELEM_LIGHT;

    if (rainbow) atk_element = ELEM_NONE;

    bool has_flash = state.curses[me][static_cast<int>(CurseType::CURSE_FLASH)];
    if (has_flash && state.num_staged_cards[me] >= 1) {
        legal_actions[ACTION_CONFIRM] = true;
        return;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            int card_id = state.true_hand[me][i];
            CardFeatures &f = g_card_registry[card_id];

            if (f.usage_timing & TIMING_ATK_DEFENCE) {
                bool is_rainbow = (card_id == ID_RAINBOW_CURTAIN);
                Element cand_e = f.element;

                Element next_def_element = current_def_element;
                if (cand_e == ELEM_NONE) next_def_element = ELEM_NONE;
                else if (cand_e == ELEM_LIGHT) {
                    if (current_def_element == ELEM_NONE && !has_non_element && !has_multiple_different_elements && !has_light && base_def_element == ELEM_NONE)
                        next_def_element = ELEM_LIGHT;
                } else {
                    if (current_def_element == ELEM_NONE) {
                        if (!has_non_element && !has_multiple_different_elements && !has_light && base_def_element == ELEM_NONE)
                            next_def_element = cand_e;
                        else if (has_light && !has_non_element && !has_multiple_different_elements && base_def_element == ELEM_NONE)
                            next_def_element = cand_e;
                        else next_def_element = ELEM_NONE;
                    } else if (current_def_element != cand_e) {
                        next_def_element = ELEM_NONE;
                    }
                }

                bool can_defend = false;
                if (atk_element == ELEM_LIGHT) {
                    if (is_rainbow) can_defend = true;
                } else if (atk_element == ELEM_NONE || atk_element == ELEM_DARKNESS) {
                    can_defend = true;
                } else {
                    Element required_def = ELEM_NONE;
                    if (atk_element == ELEM_FIRE) required_def = ELEM_WATER;
                    else if (atk_element == ELEM_WATER) required_def = ELEM_FIRE;
                    else if (atk_element == ELEM_WOOD) required_def = ELEM_STONE;
                    else if (atk_element == ELEM_STONE) required_def = ELEM_WOOD;

                    if (is_rainbow) can_defend = true;
                    else if (next_def_element == required_def || next_def_element == ELEM_LIGHT) can_defend = true;
                }

                if (can_defend) legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }
    legal_actions[ACTION_CONFIRM] = true;
}

/**
 * @brief 奇跡攻撃の追加・決定フェイズ（PHASE_MIRACLE_PLUS）における合法アクションを判定します。
 */
void legal_phase_miracle_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    bool has_unstable_accuracy = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        CardFeatures &f = g_card_registry[state.true_hand[me][state.staged_cards[me][i]]];
        if (f.accuracy < 100) has_unstable_accuracy = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.true_hand[me][i];
            CardFeatures &f = g_card_registry[card_id];
            
            if (!can_afford_staged_plus_card(state, me, i)) continue;

            bool is_legal_timing = false;
            if (f.usage_timing & TIMING_ATK_PLUS) {
                is_legal_timing = true;
            } else if ((f.usage_timing & TIMING_MIRACLE_PLUS) && is_spiritual_zero_mp_card(card_id)) {
                if (is_last_staged_card_miracle(state, me)) {
                    is_legal_timing = true;
                }
            }

            if (is_legal_timing) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }

    if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
        legal_actions[ACTION_TARGET_OPP] = true;
        legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy && !state.pending_is_group_attack;
    }
}

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）における合法アクション（手札の奇跡防具、および消費MP制限）を判定します。
 */
void legal_phase_miracle_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    int current_mp_cost = 0;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        current_mp_cost += g_card_registry[state.true_hand[me][state.staged_cards[me][i]]].mp_cost;
    }

    bool has_flash = state.curses[me][static_cast<int>(CurseType::CURSE_FLASH)];
    if (has_flash && state.num_staged_cards[me] >= 1) {
        legal_actions[ACTION_CONFIRM] = true;
        return;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            CardFeatures &f = g_card_registry[state.true_hand[me][i]];
            if (state.mp[me] < current_mp_cost + f.mp_cost) continue;

            if (f.usage_timing & TIMING_MIRACLE_DEFENCE) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }
    legal_actions[ACTION_CONFIRM] = true;
}

/**
 * @brief 各種反射選択（ミラー/スーパーミラーの有無）の基本合法アクション（スーパーミラーおよび受諾CONFIRM）を判定します。
 */
void legal_mirror_selection(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] == ID_SUPER_MIRROR) {
            legal_actions[ACTION_SELECT_HAND_0 + i] = true;
        }
    }
    legal_actions[ACTION_CONFIRM] = true;
}

/**
 * @brief 購入反射選択フェイズにおける合法アクションを判定します。
 */
void legal_phase_buy_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_mirror_selection(state, legal_actions, me);
}

/**
 * @brief 雑貨使用時の反射選択フェイズにおける合法アクションを判定します。
 */
void legal_phase_sundry_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_mirror_selection(state, legal_actions, me);
}

/**
 * @brief 売る対象の選択フェイズ（PHASE_SELL_SELECT）における合法アクションを判定します。
 */
void legal_phase_sell_select(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[me][i] != CARD_EMPTY && !state.is_deployed[me][i] && !state.is_used[me][i]) {
            legal_actions[ACTION_SELECT_HAND_0 + i] = true;
        }
    }
}

/**
 * @brief 売却反射選択フェイズにおける合法アクションを判定します。
 */
void legal_phase_sell_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_mirror_selection(state, legal_actions, me);
}

/**
 * @brief 購入可否判定フェイズ（PHASE_BUY）における合法アクション（YES/NO、および所持金チェック）を判定します。
 */
void legal_phase_buy(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_actions[ACTION_DEAL_NO] = true;
    int revealed_idx = state.staged_cards[opp][0];
    int card_id = state.true_hand[opp][revealed_idx];
    CardFeatures &f = g_card_registry[card_id];
    if (state.money[me] >= f.price) {
        legal_actions[ACTION_DEAL_YES] = true;
    }
}

/**
 * @brief 両替フェイズ（PHASE_EXCHANGE_HP / PHASE_EXCHANGE_MP）における入力値（0~99）の合法判定を行います。
 */
void legal_phase_exchange(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    if (state.current_phase == GamePhase::PHASE_EXCHANGE_HP) {
        int sum = state.exchange_sum;
        for (int x = 0; x <= 99; ++x) {
            if (x <= sum && (sum - x) <= 198) {
                legal_actions[ACTION_NUM_0 + x] = true;
            }
        }
    } else if (state.current_phase == GamePhase::PHASE_EXCHANGE_MP) {
        int sum = state.exchange_sum;
        int x = state.exchange_hp;
        for (int y = 0; y <= 99; ++y) {
            if (x + y <= sum && (sum - x - y) <= 99) {
                legal_actions[ACTION_NUM_0 + y] = true;
            }
        }
    }
}

/**
 * @brief 捨てるカード選択フェイズ（PHASE_DISCARD）における合法アクションを判定します。
 */
void legal_phase_discard(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.true_hand[me][i];
        if (card_id != CARD_EMPTY && !state.is_used[me][i]) {
            if (is_discardable_card(card_id)) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }
    if (state.num_staged_cards[me] > 0) {
        legal_actions[ACTION_CONFIRM] = true;
    }
}
