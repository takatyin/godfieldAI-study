#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>
#include <cstring>
#include <vector>
#include <random>
#include <iostream>
void confirm_all_staged_cards(InternalState &state, int player) {
    for (int i = 0; i < state.num_staged_cards[player]; ++i) {
        confirm_card(state, player, state.staged_cards[player][i]);
    }
}

/**
 * @brief 仮置きされているカード群を評価し、消費MP、攻撃力、属性、吸収フラグ、および命中結果を判定します。
 */
StagedAttackInfo evaluate_staged_attack(InternalState &state, int player_id) {
    StagedAttackInfo info = {};
    info.mp_cost = calculate_staged_mp_cost(state, player_id);

    auto card_ids = get_staged_card_ids(state, player_id);

    int total_atk = 0;
    Element current_element = ELEM_NONE;
    bool has_processed = false;

    // マジカルステッキ以外のMP消費を計算
    int other_mp_cost = 0;
    for (size_t i = 0; i < card_ids.size(); ++i) {
        int card_id = card_ids[i];
        if (card_id == CARD_EMPTY || card_id == ID_MAGICAL_STICK) continue;
        const CardFeatures &f = g_card_registry[card_id];

        if (f.is_miracle() && (i + 1 < card_ids.size())) {
            int next_card_id = card_ids[i + 1];
            if (is_spiritual_zero_mp_card(next_card_id)) {
                continue;
            }
        }
        other_mp_cost += f.mp_cost;
    }

    for (size_t i = 0; i < card_ids.size(); ++i) {
        int card_id = card_ids[i];
        if (card_id == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[card_id];

        if (card_id == ID_AURA) {
            total_atk *= 2;
        } else if (card_id == ID_MAGICAL_STICK) {
            int remaining_mp = std::max(0, state.mp[player_id] - other_mp_cost);
            total_atk += remaining_mp * 2;
        } else {
            total_atk += f.attack_power;
        }

        // 属性判定
        if (is_spiritual_zero_mp_card(card_id)) {
            // 精霊系カードは属性計算に関与しない
        } else if (card_id == ID_WAND_OF_IGNITION || card_id == ID_WAND_OF_MYSTIC_WATER) {
            // ワンドによる属性上書き（無条件で攻撃をその属性にする）
            current_element = f.element;
            has_processed = true;
        } else {
            Element e = f.element;
            if (!has_processed) {
                current_element = e;
                has_processed = true;
            } else {
                if (e == ELEM_NONE || current_element == ELEM_NONE) {
                    current_element = ELEM_NONE;
                } else if (e == ELEM_LIGHT) {
                    if (current_element == ELEM_DARKNESS) {
                        current_element = ELEM_NONE;
                    }
                } else if (current_element == ELEM_LIGHT) {
                    if (e == ELEM_DARKNESS) {
                        current_element = ELEM_NONE;
                    } else {
                        current_element = e;
                    }
                } else if (current_element != e) {
                    current_element = ELEM_NONE;
                }
            }
        }

        if (is_absorption_source(card_id)) {
            info.absorption = true;
        }
        if (card_id == ID_EVIL_BROADSWORD) {
            info.deal_same_damage = true;
        }
    }

    info.attack_power = total_atk;
    info.element = has_processed ? current_element : ELEM_NONE;

    info.hit = true;
    for (int card_id : card_ids) {
        if (card_id == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[card_id];
        if (f.accuracy < 100 && !state.curses[1 - player_id][CURSE_TYPE_DARK_CLOUD]) {
            std::uniform_int_distribution<int> dist(0, 99);
            if (dist(state.rng) >= f.accuracy) {
                info.hit = false;
                break;
            }
        }
    }

    return info;
}


void update_staged_pending_info(InternalState &state, int player_id) {
    auto card_ids = get_staged_card_ids(state, player_id);

    // 防御フェーズで仮置きしている場合は、攻撃側の pending_attack_power を上書き破棄しない
    bool is_defense_staging = (state.current_phase == GamePhase::PHASE_DEFENSE || state.current_phase == GamePhase::PHASE_MIRACLE_DEFENSE);

    if (!is_defense_staging) {
        StagedAttackInfo atk_info = evaluate_staged_attack(state, player_id);
        state.pending_attack_power = atk_info.attack_power;
        state.pending_attack_element = atk_info.element;
        state.pending_absorption = atk_info.absorption;
        state.pending_deal_same_damage = atk_info.deal_same_damage;

        bool is_group = false;
        for (int cid : card_ids) {
            if (cid != CARD_EMPTY && (g_card_registry[cid].is_group_attack || cid == ID_MIRAGE)) {
                is_group = true;
                break;
            }
        }
        state.pending_is_group_attack = is_group;
    }

    // 1. 売却価格計算
    int sell_price = 0;
    bool has_sell = false;
    for (int cid : card_ids) {
        if (cid == ID_SELL) {
            has_sell = true;
        } else if (cid != CARD_EMPTY) {
            sell_price += g_card_registry[cid].price;
        }
    }
    state.pending_sell_price = (has_sell || state.current_phase == GamePhase::PHASE_SELL_SELECT) ? sell_price : 0;

    // 2. 防御力計算
    int def_power = 0;
    for (int cid : card_ids) {
        if (cid == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[cid];
        if (f.defense_power > 0) {
            def_power += f.defense_power;
        }
    }
    state.pending_defense_power = def_power;
}



static void trigger_next_ring_counter(InternalState &state) {
    state.num_pending_counters--;
    int idx = state.num_pending_counters;
    int attacker = state.pending_counter_attacker[idx];
    int defender = state.pending_counter_defender[idx];

    state.attacker_id = attacker;
    state.defender_id = defender;
    state.current_actor_id = defender;

    int card_id = state.pending_counter_source_id[idx];
    bool is_special_ring = (card_id == ID_VENUS_RING ||
                            card_id == ID_MERCURY_RING ||
                            card_id == ID_JUPITER_RING ||
                            card_id == ID_URANUS_RING ||
                            card_id == ID_PLUTO_RING);
    if (is_special_ring) {
        state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
    } else {
        state.current_phase = GamePhase::PHASE_DEFENSE;
    }

    state.pending_attack_power = state.pending_counter_power[idx];
    state.pending_attack_element = state.pending_counter_element[idx];
    state.pending_absorption = false;
    state.pending_deal_same_damage = false;
    state.pending_is_group_attack = false;
    state.pending_attack_curse = state.pending_counter_curse[idx];
    state.pending_take_cp = state.pending_counter_take_cp[idx];
    state.pending_attack_source_id = card_id;
    state.num_staged_cards[defender] = 0;

    push_event(state, defender, EventType::RING_EFFECT, card_id, attacker, 0.0f);
}

static void process_ring_defense_effects(InternalState &state, int me, int opp, int damage) {
    if (damage <= 0) return;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.true_hand[me][state.staged_cards[me][i]];
        if (card_id == ID_MARS_RING) {
            int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
            if (roll < MARS_RING_RATE && state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = damage;
                state.pending_counter_element[idx] = ELEM_FIRE;
                state.pending_counter_curse[idx] = CURSE_NONE;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_MERCURY_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = 0;
                state.pending_counter_element[idx] = ELEM_WATER;
                state.pending_counter_curse[idx] = CURSE_FOG;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_JUPITER_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = 0;
                state.pending_counter_element[idx] = ELEM_WOOD;
                state.pending_counter_curse[idx] = CURSE_DREAM;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_SATURN_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = damage * 2;
                state.pending_counter_element[idx] = ELEM_STONE;
                state.pending_counter_curse[idx] = CURSE_NONE;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_URANUS_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = 0;
                state.pending_counter_element[idx] = ELEM_LIGHT;
                state.pending_counter_curse[idx] = CURSE_FLASH;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_PLUTO_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = 0;
                state.pending_counter_element[idx] = ELEM_DARKNESS;
                state.pending_counter_curse[idx] = CURSE_DARK_CLOUD;
                state.pending_counter_take_cp[idx] = false;
                state.pending_counter_source_id[idx] = card_id;
            }
        } else if (card_id == ID_NEPTUNE_RING) {
            state.mp[me] = std::clamp(state.mp[me] + damage * 2, 0, 99);
            push_event(state, me, EventType::RING_EFFECT, card_id, opp, 0.0f);
        } else if (card_id == ID_VENUS_RING) {
            if (state.num_pending_counters < 10) {
                int idx = state.num_pending_counters++;
                state.pending_counter_attacker[idx] = me;
                state.pending_counter_defender[idx] = opp;
                state.pending_counter_power[idx] = damage;
                state.pending_counter_element[idx] = ELEM_NONE;
                state.pending_counter_curse[idx] = CURSE_NONE;
                state.pending_counter_take_cp[idx] = true;
                state.pending_counter_source_id[idx] = card_id;
            }
        }
    }
}

void setup_multiple_attacks(InternalState &state, int me, int opp, const StagedAttackInfo &info) {
    bool has_saw_boom_boom = false;
    int mirage_count = 0;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.true_hand[me][state.staged_cards[me][i]];
        if (card_id == ID_SAW_BOOM_BOOM) {
            has_saw_boom_boom = true;
        } else if (card_id == ID_MIRAGE) {
            mirage_count++;
        }
    }
    int base_attacks = has_saw_boom_boom ? 2 : 1;
    int total_attacks = base_attacks * std::max(1, mirage_count);

    state.remaining_attacks = total_attacks;
    state.base_attacker_id = me;
    state.base_defender_id = opp;
    state.base_attack_power = info.attack_power;
    state.base_attack_element = info.element;
    state.base_absorption = info.absorption;
    state.base_deal_same_damage = info.deal_same_damage;
}

static void handle_remaining_attacks_transition(InternalState &state, int me, GamePhase current_def_phase) {
    if (state.remaining_attacks > 0) {
        state.remaining_attacks--;
    }
    if (state.remaining_attacks > 0) {
        state.num_staged_cards[me] = 0;
        state.attacker_id = state.base_attacker_id;
        state.defender_id = state.base_defender_id;
        state.pending_attack_power = state.base_attack_power;
        state.pending_attack_element = state.base_attack_element;
        state.pending_absorption = state.base_absorption;
        state.pending_deal_same_damage = state.base_deal_same_damage;
        state.current_actor_id = state.base_defender_id;
        state.current_phase = current_def_phase;
    } else {
        if (state.num_pending_counters > 0) {
            trigger_next_ring_counter(state);
        } else {
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

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
        push_event(state, me, EventType::DRAW_CARD, -1, me, 1.0f);
        state.current_phase = GamePhase::PHASE_END;
    } else if (action == ACTION_DISCARD) {
        push_event(state, me, EventType::STAGE_CARD, -1, -1, 0.0f);
        state.current_phase = GamePhase::PHASE_DISCARD;
    } else if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.apparent_hand[me][idx];
            if (card_id < 0) card_id = state.true_hand[me][idx];
            CardFeatures &f = g_card_registry[card_id];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            update_staged_pending_info(state, me);
            
            if (card_id == ID_EXCHANGE) {
                state.exchange_sum = state.hp[me] + state.mp[me] + state.money[me];
                state.exchange_hp = -1;
                state.current_phase = GamePhase::PHASE_EXCHANGE_HP;
                return;
            }

            // 仮置きイベント
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
            
            if (f.usage_timing & TIMING_MAIN_ATK) {
                state.attacker_id = me;
                state.pending_is_group_attack = f.is_group_attack;
                if (f.is_group_attack) {
                    state.current_phase = GamePhase::PHASE_GROUP_WEAPON;
                } else {
                    state.current_phase = GamePhase::PHASE_ATTACK_PLUS;
                }
                return;
            } else if (f.usage_timing & TIMING_MAIN_MIRACLE) {
                state.attacker_id = me;
                state.pending_is_group_attack = f.is_group_attack;
                if (f.is_group_attack) {
                    state.current_phase = GamePhase::PHASE_GROUP_MIRACLE_PLUS;
                } else {
                    state.current_phase = GamePhase::PHASE_MIRACLE_PLUS;
                }
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
            // 仮置きされているカードを確定（公開）状態にする
            confirm_all_staged_cards(state, me);

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
            
            confirm_all_staged_cards(state, me);

            if (target == me) {
                StagedAttackInfo info = evaluate_staged_attack(state, me);
                auto used_cards = get_staged_card_ids(state, me);
                int first_card = (!used_cards.empty()) ? used_cards[0] : -1;
                push_event(state, me, EventType::CONFIRM_ATTACK, first_card, me, 0.0f);
                
                if (info.element == ELEM_DARKNESS && info.attack_power > 0) {
                    state.hp[me] = 0;
                    run_immediate_revive(state);
                } else {
                    apply_card_effects_to_target(state, target, used_cards);
                }
                state.num_staged_cards[me] = 0;
                if (!state.is_done && state.current_phase != GamePhase::PHASE_DEFENSE) {
                    state.current_phase = GamePhase::PHASE_END;
                }
            } else {
                for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                    int h_idx = state.staged_cards[me][i];
                    if (h_idx >= 0 && h_idx < MAX_HAND_SIZE) {
                        state.is_known_to_opp[me][h_idx] = true;
                    }
                }
                auto used_cards = get_staged_card_ids(state, me);
                int first_card = (!used_cards.empty()) ? used_cards[0] : -1;
                push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

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
            int card_id = state.apparent_hand[me][idx];
            if (card_id < 0) card_id = state.true_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            update_staged_pending_info(state, me);
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
            
            if (card_id == ID_MIRAGE) {
                state.pending_is_group_attack = true;
                state.current_phase = GamePhase::PHASE_GROUP_WEAPON;
            }
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;
        confirm_all_staged_cards(state, me);
        int first_card = -1;
        if (state.num_staged_cards[me] > 0) {
            int h_idx = state.staged_cards[me][0];
            first_card = (state.apparent_hand[me][h_idx] >= 0) ? state.apparent_hand[me][h_idx] : state.true_hand[me][h_idx];
        }
        push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);
        execute_attack_from_staged_cards(state, me, target, false);
        return;
    }
}

/**
 * @brief 全体攻撃フェイズ（武器＝PHASE_GROUP_WEAPON / 奇跡＝PHASE_GROUP_MIRACLE）の共通処理。
 *
 * 武器と奇跡で異なるのは以下の3点のみで、それ以外の仮置き・確定・命中判定は共通です。
 *   - 仮置き時に非公開カード（夢状態など）を真の手札から解決するか
 *   - 仮置き時に攻撃情報（update_staged_pending_info）を更新するか
 *   - 蜃気楼による複数回攻撃（setup_multiple_attacks）を展開するか
 *
 * @param defense_phase 命中時に遷移する防御フェイズ。武器なら PHASE_DEFENSE、奇跡なら PHASE_MIRACLE_DEFENSE。
 */
static void step_phase_group_attack(InternalState &state, ActionType action, int me, int opp,
                                    GamePhase defense_phase) {
    const bool is_weapon = (defense_phase == GamePhase::PHASE_DEFENSE);

    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.apparent_hand[me][idx];
            if (is_weapon && card_id < 0) card_id = state.true_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            if (is_weapon) {
                update_staged_pending_info(state, me);
            }
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
        }
    } else if (action == ACTION_TARGET_OPP) {
        int target = opp;
        confirm_all_staged_cards(state, me);
        int first_card = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : -1;
        push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!info.hit) {
            push_event(state, me, EventType::ATTACK_MISS, first_card, target, 0.0f);
            state.current_phase = GamePhase::PHASE_END;
        } else {
            push_event(state, me, EventType::ATTACK_HIT, first_card, target, info.attack_power);
            if (is_weapon) {
                setup_multiple_attacks(state, me, target, info);
            }

            state.pending_attack_power = info.attack_power;
            state.pending_attack_element = info.element;
            state.pending_absorption = info.absorption;
            // 奇跡に相打ち（邪神の大剣）はないが、前の攻撃の値を持ち越さないよう常に上書きする
            state.pending_deal_same_damage = info.deal_same_damage;
            state.defender_id = target;
            state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;
            state.current_actor_id = target;
            state.current_phase = defense_phase;
        }
    }
}

void step_phase_group_weapon(InternalState &state, ActionType action, int me, int opp) {
    step_phase_group_attack(state, action, me, opp, GamePhase::PHASE_DEFENSE);
}

void step_phase_group_miracle(InternalState &state, ActionType action, int me, int opp) {
    step_phase_group_attack(state, action, me, opp, GamePhase::PHASE_MIRACLE_DEFENSE);
}

static void execute_standard_defense(InternalState &state, int me, int opp, GamePhase phase, int total_def, bool rainbow, bool is_darkness_attack, int damage, bool is_bounce_failure) {
    auto apply_combat_damage = [](InternalState &st, int player, int dmg) {
        if (dmg <= 0) return;
        int hp_before = st.hp[player];
        st.hp[player] = std::clamp(st.hp[player] - dmg, 0, 99);
        try_guardian_leave(st, player, st.hp[player] < hp_before);
    };

    auto apply_instant_death = [](InternalState &st, int player) {
        int hp_before = st.hp[player];
        st.hp[player] = 0;
        try_guardian_leave(st, player, st.hp[player] < hp_before);
    };

    if (phase == GamePhase::PHASE_DEFENSE) {
        process_ring_defense_effects(state, me, opp, damage);
    }

    if (damage > 0 && is_darkness_attack && !rainbow) {
        apply_instant_death(state, me);
    } else {
        apply_combat_damage(state, me, damage);
        if (damage > 0) {
            push_event(state, me, EventType::TAKE_DAMAGE, -1, me, static_cast<float>(damage));
        }
    }
    if (state.pending_absorption) {
        if (is_bounce_failure) {
            state.hp[me] = std::clamp(state.hp[me] + damage, 0, 99);
        } else {
            state.hp[opp] = std::clamp(state.hp[opp] + damage, 0, 99);
        }
    }
    run_immediate_revive(state);
    if (state.pending_deal_same_damage && damage > 0) {
        if (is_bounce_failure) {
            apply_combat_damage(state, me, damage);
        } else {
            apply_combat_damage(state, opp, damage);
        }
        run_immediate_revive(state);
    }

    if (state.hp[me] == 0) {
        run_immediate_revive(state);
    }
    if (state.hp[me] == 0) {
        if (phase == GamePhase::PHASE_DEFENSE) {
            if (state.remaining_attacks <= 0 && state.num_pending_counters <= 0) {
                state.current_phase = GamePhase::PHASE_END;
                return;
            }
        } else {
            state.current_phase = GamePhase::PHASE_END;
            return;
        }
    }

    if (phase == GamePhase::PHASE_DEFENSE || phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
        bool is_hit = (state.pending_attack_power > 0) ? (damage > 0) : (total_def == 0);
        if (is_hit) {
            if (state.pending_attack_curse != CURSE_NONE) {
                apply_curse_to_player(state, me, state.pending_attack_curse);
            }
            if (state.pending_take_cp) {
                int steal = std::min(state.money[me], damage);
                state.money[me] -= steal;
                state.money[opp] = std::min(99, state.money[opp] + steal);
            }
        }
    }

    auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
    apply_card_effects_to_target(state, me, attacker_used_cards);

    if (phase == GamePhase::PHASE_DEFENSE) {
        apply_defense_gear_effects(state, me);
        if (state.hp[me] == 0) {
            run_immediate_revive(state);
        }
        if (state.hp[me] == 0) {
            if (state.remaining_attacks <= 0 && state.num_pending_counters <= 0) {
                state.current_phase = GamePhase::PHASE_END;
                return;
            }
        }
    }

    handle_remaining_attacks_transition(state, me, phase);
}

static void resolve_defense_step(InternalState &state, ActionType action, int me, int opp, GamePhase phase) {
    int total_def = 0;
    bool rainbow = false;

    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.apparent_hand[me][idx];
            if (card_id < 0) card_id = state.true_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            update_staged_pending_info(state, me);
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
        }
    } else if (action == ACTION_CONFIRM) {
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.apparent_hand[me][h_idx];
            if (card_id < 0) card_id = state.true_hand[me][h_idx];
            if (card_id == ID_RAINBOW_CURTAIN) rainbow = true;
            total_def += g_card_registry[card_id].defense_power;
        }

        int first_card = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : -1;
        push_event(state, me, EventType::CONFIRM_DEFENSE, first_card, opp, static_cast<float>(total_def));

        bool is_darkness_attack = (state.pending_attack_element == ELEM_DARKNESS);
        if (rainbow) {
            state.pending_attack_element = ELEM_NONE;
        }

        ReactionType react_type = REACTION_NONE;
        int react_card_id = -1;
        Element effective_atk_element = state.pending_attack_element;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            int card_id = state.apparent_hand[me][h_idx];
            if (card_id < 0) card_id = state.true_hand[me][h_idx];
            const CardFeatures &f = g_card_registry[card_id];
            if (card_id == ID_RAINBOW_CURTAIN) continue;
            if (is_active_reaction_card(state, card_id, phase, effective_atk_element)) {
                react_type = f.reaction_type;
                react_card_id = card_id;
            }
        }

        int total_mp_cost = calculate_staged_mp_cost(state, me);

        if (react_type == REACTION_BLOCK) {
            push_event(state, me, EventType::BLOCK_ATTACK, react_card_id, opp, 1.0f);
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            handle_remaining_attacks_transition(state, me, phase);
            return;
        } else if (react_type == REACTION_REFLECT || react_type == REACTION_BOUNCE) {
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            bool success = true;
            if (react_type == REACTION_BOUNCE) {
                int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                success = (roll < BOUNCE_SUCCESS_RATE);
            }
            if (success) {
                EventType ev_type = (react_type == REACTION_BOUNCE) ? EventType::BOUNCE_ATTACK : EventType::REFLECT_DAMAGE;
                push_event(state, me, ev_type, react_card_id, opp, 1.0f);
                state.attacker_id = me;
                state.defender_id = opp;
                state.current_actor_id = opp;
                state.current_phase = phase;
                state.num_staged_cards[me] = 0;
                state.num_staged_cards[opp] = 0;
                return;
            } else {
                push_event(state, me, EventType::BOUNCE_ATTACK, react_card_id, opp, 0.0f);
                int damage = std::max(0, state.pending_attack_power - total_def);
                execute_standard_defense(state, me, opp, phase, total_def, rainbow, is_darkness_attack, damage, true);
                return;
            }
        }

        // REACTION_NONE
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
        int damage = std::max(0, state.pending_attack_power - total_def);
        execute_standard_defense(state, me, opp, phase, total_def, rainbow, is_darkness_attack, damage, false);
    }
}

void step_phase_defense(InternalState &state, ActionType action, int me, int opp) {
    resolve_defense_step(state, action, me, opp, GamePhase::PHASE_DEFENSE);
}

/**
 * @brief 奇跡攻撃の追加・決定フェイズ（PHASE_MIRACLE_PLUS）における処理を行います。
 *        MP消費計算、および命中判定、防御フェイズへの移行処理を担当します。
 */
void step_phase_miracle_plus(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.apparent_hand[me][idx];
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        confirm_all_staged_cards(state, me);

        int first_card = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : -1;
        push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!info.hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            state.pending_attack_power = info.attack_power;
            state.pending_attack_element = info.element;
            state.pending_absorption = info.absorption;
            state.pending_deal_same_damage = info.deal_same_damage;
            state.defender_id = target;
            state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;
            state.pending_attack_curse = (state.pending_attack_source_id != CARD_EMPTY) ? g_card_registry[state.pending_attack_source_id].hit_curse : CURSE_NONE;

            if (target == me) {
                    apply_damage(state, me, info.attack_power, state.pending_absorption, state.pending_deal_same_damage);
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, me, used_cards);
                if (state.pending_attack_curse != CURSE_NONE) {
                    apply_curse_to_player(state, me, state.pending_attack_curse);
                }
                state.current_phase = GamePhase::PHASE_END;
            } else {
                state.current_actor_id = target;
                state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
            }
        }
    }
}

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）における処理を行います。
 *        （奇跡防御では防具の防御力による減算は行わず、反射や打消し効果を持つ専用カードで対抗します）
 */
void step_phase_miracle_defense(InternalState &state, ActionType action, int me, int opp) {
    resolve_defense_step(state, action, me, opp, GamePhase::PHASE_MIRACLE_DEFENSE);
}

/**
 * @brief 「売る」対象の商品（手札カード）を仮置き場に積む処理を行います。
 */
void step_phase_sell_select(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        int idx = action - ACTION_SELECT_HAND_0;
        if (is_sellable_card(state, me, idx)) {
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
            if (is_sellable_card(state, me, j)) {
                candidates.push_back(j);
            }
        }
        
        if (!candidates.empty()) {
            std::shuffle(candidates.begin(), candidates.end(), state.rng);
            int revealed_idx = candidates[0];
            confirm_card(state, me, revealed_idx);
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
                if (g_card_registry[cid].is_sundry() || g_card_registry[cid].is_miracle()) {
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
        
        // 仮置き場を経由しないカード（守護神の行動・指輪のカウンター）の効果解決
        if (state.pending_attack_source_id != CARD_EMPTY) {
            int source_id = state.pending_attack_source_id;
            if (source_id == ID_BRIBE) { // 金星神のわいろ: 相手にお金を渡す
                state.money[state.defender_id] = std::min(99, state.money[state.defender_id] + state.pending_attack_power);
            } else if (source_id == ID_FINE || source_id == ID_VENUS_RING) { // 罰金・金星の指輪: 相手からお金を徴収
                int damage = state.pending_attack_power;
                execute_money_deduction(state, state.defender_id, damage);
                state.money[state.attacker_id] = std::min(99, state.money[state.attacker_id] + damage);
            } else if (source_id == ID_NOCTURNAL_BROOM || source_id == ID_GODDESS_S_SOAP) {
                // 地球神が引いた雑貨を相手に使ったケース。効果本体はカード効果チェーンが持つ
                apply_card_effect_to_target(state, state.defender_id, source_id);
            }
            // 状態異常の付与は hit_curse を持つカードに共通の処理でまとめて行う。
            // 木星神の紅葉・天王神の後光・冥王神の不吉な予感もここで解決される。
            if (state.pending_attack_curse != CURSE_NONE) {
                apply_curse_to_player(state, state.defender_id, state.pending_attack_curse);
            }
            state.pending_attack_source_id = CARD_EMPTY;
            state.pending_attack_curse = CURSE_NONE;
        }
        
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

            push_event(state, buyer, EventType::BUY_CARD, card_id, seller, static_cast<float>(price));

            clear_hand_slot(state, seller, revealed_idx);

            int empty_slot = -1;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[buyer][j] == CARD_EMPTY) {
                    empty_slot = j;
                    break;
                }
            }

            if (empty_slot != -1) {
                add_card_to_hand_slot(state, buyer, empty_slot, card_id, false);
                state.is_known_to_opp[buyer][empty_slot] = true;
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
                    clear_hand_slot(state, buyer, replace_idx);
                    add_card_to_hand_slot(state, buyer, replace_idx, card_id, false);
                    state.is_known_to_opp[buyer][replace_idx] = true;
                }
            }
        } else {
            // 購入しなかった（または購入資金不足）場合
            push_event(state, buyer, EventType::REFUSE_DEAL, card_id, seller, 0.0f);
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

            push_event(state, me, EventType::EXCHANGE, ID_EXCHANGE, me, static_cast<float>(hp_val));

            if (state.hp[me] <= 0) {
                state.hp[me] = 0;
                state.num_staged_cards[me] = 0;
                state.current_phase = GamePhase::PHASE_END;
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
            if (card_id != CARD_EMPTY && !state.is_used[me][idx]) {
                if (is_discardable_card(card_id)) {
                    state.staged_cards[me][state.num_staged_cards[me]++] = idx;
                    state.is_used[me][idx] = true;
                    push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
                }
            }
        }
    } else if (action == ACTION_CONFIRM) {
        if (state.num_staged_cards[me] > 0) {
            int discarded_count = state.num_staged_cards[me];
            for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                int hand_idx = state.staged_cards[me][i];
                int card_id = state.true_hand[me][hand_idx];
                push_event(state, me, EventType::DISCARD_CARD, card_id, me, 0.0f);
                clear_hand_slot(state, me, hand_idx);
            }
            state.num_staged_cards[me] = 0;

            if (state.current_turn >= APOCALYPSE_TURN) {
                for (int i = 0; i < discarded_count; ++i) {
                    draw_card_to_hand(state, me);
                }
            }

            state.current_phase = GamePhase::PHASE_END;
        }
    }
}
