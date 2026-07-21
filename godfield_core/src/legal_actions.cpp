#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"

/**
 * @brief メインフェイズ（PHASE_MAIN）における合法アクション（祈る/捨てる/使用可能な手札）を計算します。
 */
void legal_phase_main(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    // 祈る、捨てるができるかのチェック
    if (can_pray(state, me)) legal_actions[ACTION_PRAY] = true;
    if (can_discard(state, me)) legal_actions[ACTION_DISCARD] = true;

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
            // 展開済みかつ使用済みの奇跡は使えない
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            CardFeatures &f = g_card_registry[state.apparent_hand[me][i]];
            
            // 奇跡のMP消費が足りるか（将来的に精霊系カードで0にできる可能性を含めて判定）
            if (!can_afford_staged_plus_card(state, me, i)) continue;
            
            // 売るで売るアイテムがあるか
            if (state.apparent_hand[me][i] == ID_SELL && !can_sell_card(state, me, i)) continue;
            
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
        CardFeatures &f = get_registry_size() > 0 ? g_card_registry[state.apparent_hand[me][state.staged_cards[me][i]]] : g_card_registry[0]; // safety fallback
        if (f.accuracy < 100) has_unstable_accuracy = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.apparent_hand[me][i];
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

    if (state.num_staged_cards[me] > 0) {
        int first_card = state.apparent_hand[me][state.staged_cards[me][0]];
        if (first_card != CARD_EMPTY) {
            const CardFeatures &first_feat = g_card_registry[first_card];
            if (first_feat.usage_timing & TIMING_MAIN_ATK) {
                if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
                    legal_actions[ACTION_TARGET_OPP] = true;
                    legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy && !state.pending_is_group_attack;
                }
            }
        }
    }
}

void legal_phase_group_weapon(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    bool has_mirage = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        if (state.apparent_hand[me][state.staged_cards[me][i]] == ID_MIRAGE) {
            has_mirage = true;
            break;
        }
    }

    if (has_mirage) {
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
                if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
                
                int card_id = state.apparent_hand[me][i];
                if (card_id == ID_MIRAGE || is_spiritual_zero_mp_card(card_id)) {
                    if (can_afford_staged_plus_card(state, me, i)) {
                        legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                    }
                }
            }
        }
    }

    if (state.num_staged_cards[me] > 0) {
        int first_card = state.apparent_hand[me][state.staged_cards[me][0]];
        if (first_card != CARD_EMPTY) {
            const CardFeatures &first_feat = g_card_registry[first_card];
            if (first_feat.usage_timing & TIMING_MAIN_ATK) {
                if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
                    legal_actions[ACTION_TARGET_OPP] = true;
                }
            }
        }
    }
}

void legal_phase_group_miracle(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.apparent_hand[me][i];
            if (is_spiritual_zero_mp_card(card_id)) {
                if (is_last_staged_card_miracle(state, me)) {
                    if (can_afford_staged_plus_card(state, me, i)) {
                        legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                    }
                }
            }
        }
    }

    if (state.num_staged_cards[me] > 0) {
        int first_card = state.apparent_hand[me][state.staged_cards[me][0]];
        if (first_card != CARD_EMPTY) {
            const CardFeatures &first_feat = g_card_registry[first_card];
            if (first_feat.usage_timing & TIMING_MAIN_MIRACLE) {
                if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
                    legal_actions[ACTION_TARGET_OPP] = true;
                }
            }
        }
    }
}


/**
 * @brief 物理および奇跡防御フェイズで共通する、防御アクションの合法性チェックを行います。
 */
static void legal_defense_common(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp, GamePhase defense_phase) {
    bool rainbow = false;
    Element effective_atk_element = state.pending_attack_element;

    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.apparent_hand[me][state.staged_cards[me][i]];
        if (card_id == ID_RAINBOW_CURTAIN) {
            rainbow = true;
            effective_atk_element = ELEM_NONE;
        }
    }

    bool has_staged_reaction = false;
    bool reaction_is_miracle = false;
    bool has_staged_spirit = false;

    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.apparent_hand[me][state.staged_cards[me][i]];
        if (card_id == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[card_id];
        if (card_id == ID_RAINBOW_CURTAIN) continue;
        if (is_active_reaction_card(state, card_id, defense_phase, effective_atk_element)) {
            has_staged_reaction = true;
            if (f.is_miracle()) reaction_is_miracle = true;
        } else if (is_spiritual_zero_mp_card(card_id)) {
            has_staged_spirit = true;
        }
    }

    bool has_flash = state.curses[me][CURSE_TYPE_FLASH];
    if (has_flash && state.num_staged_cards[me] >= 1) {
        legal_actions[ACTION_CONFIRM] = true;
        return;
    }

    // Element evaluation for staged normal armor
    bool has_non_element = false, has_multiple_different_elements = false;
    Element base_def_element = ELEM_NONE;
    bool has_light = false;

    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.apparent_hand[me][state.staged_cards[me][i]];
        if (card_id == CARD_EMPTY) continue;
        if (card_id == ID_RAINBOW_CURTAIN) continue;
        const CardFeatures &f = g_card_registry[card_id];
        if (is_active_reaction_card(state, card_id, defense_phase, effective_atk_element)) continue;
        if (is_spiritual_zero_mp_card(card_id)) continue;

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

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.apparent_hand[me][i];
            const CardFeatures &f = g_card_registry[card_id];

            if (!can_afford_staged_plus_card(state, me, i)) continue;

            // 1. 虹のカーテンは1枚目のみ (かつ攻撃力 > 0 のときのみ)
            if (card_id == ID_RAINBOW_CURTAIN) {
                if (state.num_staged_cards[me] == 0 && state.pending_attack_power > 0) {
                    legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                }
                continue;
            }

            // 2. すでにリアクションカードがある場合
            if (has_staged_reaction) {
                if (reaction_is_miracle && !has_staged_spirit && is_spiritual_zero_mp_card(card_id)) {
                    legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                }
                continue;
            }

            // 3. リアクションカードの重ねがけ排他チェック
            bool is_react = is_active_reaction_card(state, card_id, defense_phase, effective_atk_element);
            if (is_react) {
                bool allowed_as_first = false;
                if (defense_phase == GamePhase::PHASE_DEFENSE) {
                    // 物理防御：リアクションは「1枚目」または「虹のカーテンの直後」のみ
                    allowed_as_first = (state.num_staged_cards[me] == 0) || 
                                       (state.num_staged_cards[me] == 1 && state.apparent_hand[me][state.staged_cards[me][0]] == ID_RAINBOW_CURTAIN);
                } else {
                    // 奇跡防御：虹のカーテンの後にリアクションカードを重ねることは非合法（1枚目のみ許可）
                    allowed_as_first = (state.num_staged_cards[me] == 0);
                }
                if (allowed_as_first) {
                    legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                }
                continue;
            }

            // 4. 一般防具の判定
            if (f.reaction_type != REACTION_NONE) {
                continue;
            }
            bool is_weapon_atk = false;
            if (state.pending_attack_source_id != CARD_EMPTY) {
                is_weapon_atk = g_card_registry[state.pending_attack_source_id].is_weapon();
            }
            if (state.pending_attack_power > 0 || is_weapon_atk) {
                uint32_t allowed_timings = (defense_phase == GamePhase::PHASE_DEFENSE) ? TIMING_ATK_DEFENCE : TIMING_MIRACLE_DEFENCE;
                bool counters_element = false;
                if (defense_phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
                    if (f.element == ELEM_LIGHT) counters_element = true;
                    else if (effective_atk_element == ELEM_FIRE && f.element == ELEM_WATER) counters_element = true;
                    else if (effective_atk_element == ELEM_WATER && f.element == ELEM_FIRE) counters_element = true;
                    else if (effective_atk_element == ELEM_WOOD && f.element == ELEM_STONE) counters_element = true;
                    else if (effective_atk_element == ELEM_STONE && f.element == ELEM_WOOD) counters_element = true;
                }
                if (defense_phase == GamePhase::PHASE_MIRACLE_DEFENSE && (rainbow || counters_element)) {
                    allowed_timings |= TIMING_ATK_DEFENCE;
                }
                if (f.usage_timing & allowed_timings) {
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
                    if (effective_atk_element == ELEM_LIGHT) {
                        if (rainbow) can_defend = true;
                    } else if (effective_atk_element == ELEM_NONE || effective_atk_element == ELEM_DARKNESS) {
                        can_defend = true;
                    } else {
                        Element required_def = ELEM_NONE;
                        if (effective_atk_element == ELEM_FIRE) required_def = ELEM_WATER;
                        else if (effective_atk_element == ELEM_WATER) required_def = ELEM_FIRE;
                        else if (effective_atk_element == ELEM_WOOD) required_def = ELEM_STONE;
                        else if (effective_atk_element == ELEM_STONE) required_def = ELEM_WOOD;

                        if (rainbow) can_defend = true;
                        else if (next_def_element == required_def || next_def_element == ELEM_LIGHT) can_defend = true;
                    }

                    if (can_defend) {
                        legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                    }
                }
            }
        }
    }
    legal_actions[ACTION_CONFIRM] = (state.mp[me] >= calculate_staged_mp_cost(state, me));
}

/**
 * @brief 物理・属性防御フェイズ（PHASE_DEFENSE）における合法アクション（防御属性の整合性、およびCONFIRMの可否）を判定します。
 */
void legal_phase_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_defense_common(state, legal_actions, me, opp, GamePhase::PHASE_DEFENSE);
}

/**
 * @brief 奇跡攻撃の追加・決定フェイズ（PHASE_MIRACLE_PLUS）における合法アクションを判定します。
 */
void legal_phase_miracle_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    bool has_unstable_accuracy = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        CardFeatures &f = g_card_registry[state.apparent_hand[me][state.staged_cards[me][i]]];
        if (f.accuracy < 100) has_unstable_accuracy = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            
            int card_id = state.apparent_hand[me][i];
            CardFeatures &f = g_card_registry[card_id];
            
            if (!can_afford_staged_plus_card(state, me, i)) continue;

            bool is_legal_timing = false;
            if ((f.usage_timing & TIMING_MIRACLE_PLUS) && is_spiritual_zero_mp_card(card_id)) {
                if (is_last_staged_card_miracle(state, me)) {
                    is_legal_timing = true;
                }
            }

            if (is_legal_timing) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }

    if (state.num_staged_cards[me] > 0) {
        int first_card = state.apparent_hand[me][state.staged_cards[me][0]];
        if (first_card != CARD_EMPTY) {
            const CardFeatures &first_feat = g_card_registry[first_card];
            if (first_feat.usage_timing & TIMING_MAIN_MIRACLE) {
                if (state.mp[me] >= calculate_staged_mp_cost(state, me)) {
                    legal_actions[ACTION_TARGET_OPP] = true;
                    legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy && !state.pending_is_group_attack;
                }
            }
        }
    }
}

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）における合法アクション（手札の奇跡防具、および消費MP制限）を判定します。
 */
void legal_phase_miracle_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_defense_common(state, legal_actions, me, opp, GamePhase::PHASE_MIRACLE_DEFENSE);
}

/**
 * @brief 各種反射選択（ミラー/スーパーミラーの有無）の基本合法アクション（スーパーミラーおよび受諾CONFIRM）を判定します。
 */
void legal_mirror_selection(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.apparent_hand[me][i] == ID_SUPER_MIRROR) {
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
        if (state.apparent_hand[me][i] != CARD_EMPTY && !state.is_deployed[me][i] && !state.is_used[me][i]) {
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
    int card_id = state.apparent_hand[opp][revealed_idx];
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
        int card_id = state.apparent_hand[me][i];
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
