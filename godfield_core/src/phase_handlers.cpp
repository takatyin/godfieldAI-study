#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>
#include <cstring>
#include <vector>
#include <random>

/**
 * @brief メインフェイズ（PHASE_MAIN）でのプレイヤー行動を処理します。
 *        祈る、捨てる、または使用タイミングがメインフェイズの各種カードの仮置きを行います。
 */
void step_phase_main(InternalState &state, ActionType action, int me, int opp) {
    if (action == ACTION_PRAY) {
        bool is_hand_full = true;
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.true_hand[me][i] == CARD_EMPTY) {
                is_hand_full = false;
                break;
            }
        }
        if (is_hand_full) {
            discard_one_card_randomly(state, me);
        }
        draw_card_to_hand(state, me);
        state.current_phase = GamePhase::PHASE_END;
    } else if (action == ACTION_DISCARD) {
        state.current_phase = GamePhase::PHASE_DISCARD;
    } else if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.true_hand[me][idx];
            CardFeatures &f = g_card_registry[card_id];
            
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            
            if (card_id == ID_EXCHANGE) {
                state.exchange_sum = state.hp[me] + state.mp[me] + state.money[me];
                state.exchange_hp = -1;
                state.current_phase = GamePhase::PHASE_EXCHANGE_HP;
                return;
            } else if (f.usage_timing & TIMING_MAIN_ATK) {
                state.current_phase = GamePhase::PHASE_ATTACK_PLUS;
                state.attacker_id = me;
                state.pending_is_group_attack = (f.is_weapon || f.is_miracle) && (f.accuracy < 100);
                return;
            } else if (f.usage_timing & TIMING_MAIN_MIRACLE) {
                state.current_phase = GamePhase::PHASE_MIRACLE_PLUS;
                state.attacker_id = me;
                state.pending_is_group_attack = (f.is_weapon || f.is_miracle) && (f.accuracy < 100);
                return;
            } else if (card_id == ID_SELL) {
                state.current_phase = GamePhase::PHASE_SELL_SELECT;
                return;
            } else {
                state.current_phase = GamePhase::PHASE_MAIN_TARGET_SELECT;
                return;
            }
        }
    }
}

/**
 * @brief メインアクション発動時の対象選択（自分 / 相手）を処理します。
 *        売りつける、または相手/自分への雑貨効果適用の分岐処理を行います。
 */
void step_phase_main_target_select(InternalState &state, ActionType action, int me, int opp) {
    if (action == ACTION_TARGET_SELF || action == ACTION_TARGET_OPP) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;
        if (state.num_staged_cards[me] > 0) {
            int card_id = state.true_hand[me][state.staged_cards[me][0]];
            if (card_id == ID_SELL) {
                state.attacker_id = me;
                state.defender_id = target;
                if (target == me) {
                    execute_sell_resolution(state, me, me);
                } else {
                    state.current_phase = GamePhase::PHASE_SELL_SELECT_MIRROR;
                    state.current_actor_id = target; 
                }
                return;
            } else if (card_id == ID_BUY) {
                state.attacker_id = me;
                state.defender_id = target;
                if (target == me) {
                    std::vector<int> candidates;
                    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                        if (state.true_hand[me][j] != CARD_EMPTY && !state.is_deployed[me][j] && !state.is_used[me][j]) {
                            candidates.push_back(j);
                        }
                    }
                    if (!candidates.empty()) {
                        std::shuffle(candidates.begin(), candidates.end(), state.rng);
                        state.is_known_to_opp[me][candidates[0]] = true;
                    }
                    state.num_staged_cards[me] = 0;
                    state.current_phase = GamePhase::PHASE_END;
                } else {
                    state.current_phase = GamePhase::PHASE_BUY_SELECT_MIRROR;
                    state.current_actor_id = target;
                }
                return;
            }
            
            if (target == me) {
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, target, used_cards);
                state.num_staged_cards[me] = 0;
                if (!state.is_done) {
                    state.current_phase = GamePhase::PHASE_END;
                }
            } else {
                state.attacker_id = me;
                state.defender_id = target;
                state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
                state.current_actor_id = target;
            }
        }
    }
}

/**
 * @brief 物理攻撃の追加・対象決定フェイズ（PHASE_ATTACK_PLUS）における処理を行います。
 *        攻撃力の合算、属性の評価、命中判定、および防御フェイズへの遷移を担当します。
 */
void step_phase_attack_plus(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.true_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            
            if (card_id == ID_MIRAGE) {
                state.pending_is_group_attack = true;
            }
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        int total_mp_cost = calculate_staged_mp_cost(state, me);
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);

        int total_atk = 0;
        bool has_non_element = false;
        bool has_multiple_different_elements = false;
        Element base_element = ELEM_NONE;
        bool has_light = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            
            if (card_id == ID_AURA) total_atk *= 2;
            else total_atk += f.attack_power;
            
            Element e = f.element;
            if (e == ELEM_NONE) has_non_element = true;
            else if (e == ELEM_LIGHT) has_light = true;
            else {
                if (base_element == ELEM_NONE) base_element = e;
                else if (base_element != e) has_multiple_different_elements = true;
            }

            if (card_id == ID_ABSORPTION || card_id == ID_VINE_SHOOT) {
                state.pending_absorption = true;
            }
        }

        Element atk_element = ELEM_NONE;
        if (has_non_element || has_multiple_different_elements) atk_element = ELEM_NONE;
        else if (base_element != ELEM_NONE) atk_element = base_element;
        else if (has_light) atk_element = ELEM_LIGHT;

        bool hit = true;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int card_id = state.true_hand[me][state.staged_cards[me][i]];
            CardFeatures &f = g_card_registry[card_id];
            if (f.accuracy < 100) {
                std::uniform_int_distribution<int> dist(0, 99);
                if (dist(state.rng) >= f.accuracy) {
                    hit = false;
                    break;
                }
            }
        }

        if (!hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            state.pending_attack_power = total_atk;
            state.pending_attack_element = atk_element;
            state.defender_id = target;

            if (target == me) {
                if (total_atk > 0) {
                    int intended_damage = total_atk;
                    state.hp[me] = std::clamp(state.hp[me] - total_atk, 0, 99);
                    if (state.pending_absorption) {
                        state.hp[me] = std::clamp(state.hp[me] + intended_damage, 0, 99);
                    }
                }
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, me, used_cards);
                state.current_phase = GamePhase::PHASE_END;
            } else {
                state.current_actor_id = target;
                if (is_weapon_attack(state, me)) {
                    state.current_phase = GamePhase::PHASE_DEFENSE;
                } else {
                    state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
                }
            }
        }
    }
}

/**
 * @brief 物理・属性防御フェイズ（PHASE_DEFENSE）における処理を行います。
 *        防御力の集計、属性による相殺判定、残余ダメージの算出、および状態異常効果の適用を行います。
 */
void step_phase_defense(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_CONFIRM) {
        int total_def = 0;
        bool bounced = false; 
        bool rainbow = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            total_def += f.defense_power;
            if (card_id == ID_RAINBOW_CURTAIN) rainbow = true;
        }

        if (!bounced) {
            int damage = std::max(0, state.pending_attack_power - total_def);

            if (damage > 0 && state.pending_attack_element == ELEM_DARKNESS && !rainbow) {
                state.hp[me] = 0;
            } else {
                state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
            }

            if (state.hp[me] == 0) {
                state.is_done = true;
                state.p0_reward = (me == 0) ? -1.0f : 1.0f;
                state.p1_reward = (me == 1) ? -1.0f : 1.0f;
                return;
            }

            auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
            apply_card_effects_to_target(state, me, attacker_used_cards);
        }

        state.current_phase = GamePhase::PHASE_END;
    }
}

/**
 * @brief 奇跡攻撃の追加・決定フェイズ（PHASE_MIRACLE_PLUS）における処理を行います。
 *        MP消費計算、および命中判定、防御フェイズへの移行処理を担当します。
 */
void step_phase_miracle_plus(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.true_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            
            if (card_id == ID_MIRAGE) {
                state.pending_is_group_attack = true;
            }
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        int total_mp_cost = calculate_staged_mp_cost(state, me);
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);

        int total_atk = 0;
        bool has_non_element = false;
        bool has_multiple_different_elements = false;
        Element base_element = ELEM_NONE;
        bool has_light = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            
            if (card_id == ID_AURA) total_atk *= 2;
            else total_atk += f.attack_power;
            
            Element e = f.element;
            if (e == ELEM_NONE) has_non_element = true;
            else if (e == ELEM_LIGHT) has_light = true;
            else {
                if (base_element == ELEM_NONE) base_element = e;
                else if (base_element != e) has_multiple_different_elements = true;
            }

            if (card_id == ID_ABSORPTION || card_id == ID_VINE_SHOOT) {
                state.pending_absorption = true;
            }
        }

        Element atk_element = ELEM_NONE;
        if (has_non_element || has_multiple_different_elements) atk_element = ELEM_NONE;
        else if (base_element != ELEM_NONE) atk_element = base_element;
        else if (has_light) atk_element = ELEM_LIGHT;

        bool hit = true;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int card_id = state.true_hand[me][state.staged_cards[me][i]];
            CardFeatures &f = g_card_registry[card_id];
            if (f.accuracy < 100) {
                std::uniform_int_distribution<int> dist(0, 99);
                if (dist(state.rng) >= f.accuracy) {
                    hit = false;
                    break;
                }
            }
        }

        if (!hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            state.pending_attack_power = total_atk;
            state.pending_attack_element = atk_element;
            state.defender_id = target;

            if (target == me) {
                if (total_atk > 0) {
                    int intended_damage = total_atk;
                    state.hp[me] = std::clamp(state.hp[me] - total_atk, 0, 99);
                    if (state.pending_absorption) {
                        state.hp[me] = std::clamp(state.hp[me] + intended_damage, 0, 99);
                    }
                }
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, me, used_cards);
                state.current_phase = GamePhase::PHASE_END;
            } else {
                state.current_actor_id = target;
                if (is_weapon_attack(state, me)) {
                    state.current_phase = GamePhase::PHASE_DEFENSE;
                } else {
                    state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
                }
            }
        }
    }
}

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）における処理を行います。
 *        （奇跡防御では防具の防御力による減算は行わず、反射や打消し効果を持つ専用カードで対抗します）
 */
void step_phase_miracle_defense(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_CONFIRM) {
        bool bounced = false;
        int total_mp_cost = 0;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            total_mp_cost += f.mp_cost;
            if (card_id == ID_TURBULENCE || card_id == ID_SUPER_MIRROR) {
                bounced = true;
            }
        }
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
        
        int target = me;
        int attacker = opp;
        
        if (bounced) {
            target = opp;
            attacker = me;
        }
        
        int total_atk = state.pending_attack_power;
        int intended_damage = total_atk;
        state.hp[target] = std::clamp(state.hp[target] - total_atk, 0, 99);
        
        if (state.pending_absorption) {
            state.hp[attacker] = std::clamp(state.hp[attacker] + intended_damage, 0, 99);
        }

        auto attacker_used_cards = get_staged_card_ids(state, attacker);
        apply_card_effects_to_target(state, target, attacker_used_cards);
        
        if (!state.is_done) {
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

/**
 * @brief 「売る」対象の商品（手札カード）を仮置き場に積む処理を行います。
 */
void step_phase_sell_select(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        int idx = action - ACTION_SELECT_HAND_0;
        int card_id = state.true_hand[me][idx];
        if (card_id != CARD_EMPTY && !state.is_deployed[me][idx] && !state.is_used[me][idx]) {
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            state.current_phase = GamePhase::PHASE_MAIN_TARGET_SELECT;
        }
    }
}

/**
 * @brief 相手にアイテムを売りつける際のスーパーミラーによる反射、または受諾判定を行います。
 */
void step_phase_sell_select_mirror(InternalState &state, ActionType action, int me, int opp) {
    if (try_execute_super_mirror_reflection(state, action, me, opp)) {
        return;
    }
    if (action == ACTION_CONFIRM) {
        int seller = state.attacker_id;
        int buyer = state.defender_id;
        execute_sell_resolution(state, seller, buyer);
    }
}

/**
 * @brief 相手に「買う」を仕掛けた際の相手側の反射、または受諾選択を処理します。
 */
void step_phase_buy_select_mirror(InternalState &state, ActionType action, int me, int opp) {
    if (try_execute_super_mirror_reflection(state, action, me, opp)) {
        return;
    }
    if (action == ACTION_CONFIRM) {
        state.current_phase = GamePhase::PHASE_BUY;
        state.current_actor_id = opp;
        
        std::vector<int> candidates;
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (state.true_hand[me][j] != CARD_EMPTY && !state.is_deployed[me][j] && !state.is_used[me][j]) {
                candidates.push_back(j);
            }
        }
        
        if (!candidates.empty()) {
            std::shuffle(candidates.begin(), candidates.end(), state.rng);
            int revealed_idx = candidates[0];
            state.is_known_to_opp[me][revealed_idx] = true;
            state.staged_cards[me][0] = revealed_idx;
            state.num_staged_cards[me] = 1;
        } else {
            state.num_staged_cards[me] = 0;
            state.num_staged_cards[opp] = 0;
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

/**
 * @brief 相手に「雑貨」を使用した際の相手側の反射、または受諾選択を処理します。
 */
void step_phase_sundry_select_mirror(InternalState &state, ActionType action, int me, int opp) {
    if (try_execute_super_mirror_reflection(state, action, me, opp)) {
        return;
    }
    if (action == ACTION_CONFIRM) {
        int original_caster = -1;
        for (int p = 0; p < 2; ++p) {
            for (int i = 0; i < state.num_staged_cards[p]; ++i) {
                int cid = state.true_hand[p][state.staged_cards[p][i]];
                if (g_card_registry[cid].is_sundry) {
                    original_caster = p;
                    break;
                }
            }
            if (original_caster != -1) break;
        }
        
        if (original_caster == -1) {
            original_caster = state.attacker_id;
        }
        
        auto used_cards = get_staged_card_ids(state, original_caster);
        apply_card_effects_to_target(state, state.defender_id, used_cards);
        
        state.num_staged_cards[0] = 0;
        state.num_staged_cards[1] = 0;
        
        if (!state.is_done) {
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

/**
 * @brief 提示された相手のカードを購入するかどうかの意思決定を処理します。
 */
void step_phase_buy(InternalState &state, ActionType action, int me, int opp) {
    if (action == ACTION_DEAL_YES || action == ACTION_DEAL_NO) {
        int buyer = me;
        int seller = opp;
        int revealed_idx = state.staged_cards[seller][0];
        int card_id = state.true_hand[seller][revealed_idx];
        CardFeatures &f_bought = g_card_registry[card_id];
        int price = f_bought.price;

        if (action == ACTION_DEAL_YES && state.money[buyer] >= price) {
            state.money[buyer] -= price;
            state.money[seller] = std::clamp(state.money[seller] + price, 0, 99);

            state.true_hand[seller][revealed_idx] = CARD_EMPTY;
            state.is_known_to_opp[seller][revealed_idx] = false;
            state.is_used[seller][revealed_idx] = false;

            int empty_slot = -1;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[buyer][j] == CARD_EMPTY) {
                    empty_slot = j;
                    break;
                }
            }

            if (empty_slot != -1) {
                state.true_hand[buyer][empty_slot] = card_id;
                state.is_known_to_opp[buyer][empty_slot] = true;
                state.is_used[buyer][empty_slot] = false;
            } else {
                std::vector<int> candidates;
                int buy_card_idx = state.staged_cards[buyer][0];
                for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                    if (state.true_hand[buyer][j] != CARD_EMPTY && j != buy_card_idx) {
                        candidates.push_back(j);
                    }
                }
                if (!candidates.empty()) {
                    std::shuffle(candidates.begin(), candidates.end(), state.rng);
                    int replace_idx = candidates[0];
                    state.true_hand[buyer][replace_idx] = card_id;
                    state.is_known_to_opp[buyer][replace_idx] = true;
                    state.is_deployed[buyer][replace_idx] = false;
                    state.miracle_used_this_turn[buyer][replace_idx] = false;
                    state.is_used[buyer][replace_idx] = false;
                }
            }
        } else {
            // 購入しなかった（または購入資金不足）場合
            // 売り手の他のスロットに同じカードタイプ（card_id）で既に手札内公開（is_known_to_opp かつ 未展開）状態のものがあるか確認
            bool already_known = false;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (j != revealed_idx && 
                    state.true_hand[seller][j] == card_id && 
                    state.is_known_to_opp[seller][j] && 
                    !state.is_deployed[seller][j]) { // 展開済みの同名奇跡は手札公開情報とは別として扱います
                    already_known = true;
                    break;
                }
            }
            // 同種のカードが既に手札内で公開済みの場合は、この新たに提示されたスロットの公開フラグをfalse（非公開）に戻す
            if (already_known) {
                state.is_known_to_opp[seller][revealed_idx] = false;
            }
        }

        state.staged_cards[seller][0] = 0;
        state.num_staged_cards[seller] = 0;
        state.num_staged_cards[me] = 0;
        state.current_phase = GamePhase::PHASE_END;
    }
}

/**
 * @brief 「両替」カードでのHP/MP/お金の配分決定を処理します。
 */
void step_phase_exchange(InternalState &state, ActionType action, int me, int opp) {
    if (state.current_phase == GamePhase::PHASE_EXCHANGE_HP) {
        if (action >= ACTION_NUM_0 && action <= ACTION_NUM_99) {
            state.exchange_hp = action - ACTION_NUM_0;
            state.current_phase = GamePhase::PHASE_EXCHANGE_MP;
        }
    } else if (state.current_phase == GamePhase::PHASE_EXCHANGE_MP) {
        if (action >= ACTION_NUM_0 && action <= ACTION_NUM_99) {
            int hp_val = state.exchange_hp;
            int mp_val = action - ACTION_NUM_0;
            int money_val = std::clamp(state.exchange_sum - hp_val - mp_val, 0, 99);

            state.hp[me] = hp_val;
            state.mp[me] = mp_val;
            state.money[me] = money_val;

            if (state.hp[me] <= 0) {
                state.hp[me] = 0;
                state.is_done = true;
                state.p0_reward = (me == 0) ? -1.0f : 1.0f;
                state.p1_reward = (me == 1) ? -1.0f : 1.0f;
                return;
            }

            state.num_staged_cards[me] = 0;
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

/**
 * @brief 「捨てる」フェイズでの対象カード選択・確定処理を行います。
 */
void step_phase_discard(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.true_hand[me][idx];
            if (card_id != CARD_EMPTY && !state.is_deployed[me][idx] && !state.is_used[me][idx]) {
                if (is_discardable_card(card_id)) {
                    state.staged_cards[me][state.num_staged_cards[me]++] = idx;
                    state.is_used[me][idx] = true;
                }
            }
        }
    } else if (action == ACTION_CONFIRM) {
        if (state.num_staged_cards[me] > 0) {
            for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                int hand_idx = state.staged_cards[me][i];
                state.true_hand[me][hand_idx] = CARD_EMPTY;
                state.is_known_to_opp[me][hand_idx] = false;
                state.is_deployed[me][hand_idx] = false;
                state.miracle_used_this_turn[me][hand_idx] = false;
            }
            state.num_staged_cards[me] = 0;
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}
