#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>
#include <cstring>
#include <vector>
#include <random>

struct StagedAttackInfo {
    int mp_cost;
    int attack_power;
    Element element;
    bool absorption;
    bool deal_same_damage;
    bool hit;
};

/**
 * @brief 仮置きされているカード群を評価し、消費MP、攻撃力、属性、吸収フラグ、および命中結果を判定します。
 */
static StagedAttackInfo evaluate_staged_attack(InternalState &state, int player_id) {
    StagedAttackInfo info = {};
    info.mp_cost = calculate_staged_mp_cost(state, player_id);

    int total_atk = 0;
    Element current_element = ELEM_NONE;

    // マジカルステッキ以外のMP消費を計算
    int other_mp_cost = 0;
    int num_cards = state.num_staged_cards[player_id];
    for (int i = 0; i < num_cards; ++i) {
        int card_id = state.true_hand[player_id][state.staged_cards[player_id][i]];
        if (card_id == CARD_EMPTY || card_id == ID_MAGICAL_STICK) continue;
        const CardFeatures &f = g_card_registry[card_id];

        if (f.is_miracle && (i + 1 < num_cards)) {
            int next_card_id = state.true_hand[player_id][state.staged_cards[player_id][i + 1]];
            if (is_spiritual_zero_mp_card(next_card_id)) {
                continue;
            }
        }
        other_mp_cost += f.mp_cost;
    }

    for (int i = 0; i < num_cards; ++i) {
        int h_idx = state.staged_cards[player_id][i];
        state.is_known_to_opp[player_id][h_idx] = true;
        int card_id = state.true_hand[player_id][h_idx];
        const CardFeatures &f = g_card_registry[card_id];

        if (card_id == ID_AURA) {
            total_atk *= 2;
        } else if (card_id == ID_MAGICAL_STICK) {
            int remaining_mp = std::max(0, state.mp[player_id] - other_mp_cost);
            total_atk += remaining_mp * 2;
        } else {
            total_atk += f.attack_power;
        }

        // 精霊系カードは属性計算に関与しない（元の属性を維持）
        if (is_spiritual_zero_mp_card(card_id)) {
            // 属性計算をスキップ
        } else if (card_id == ID_WAND_OF_IGNITION || card_id == ID_WAND_OF_MYSTIC_WATER) {
            // ワンドによる属性上書き
            current_element = f.element; // 火 または 水 に強制上書き
        } else {
            // 通常の属性解決ルール
            Element e = f.element;
            if (e == ELEM_NONE) {
                // 無属性が重ねられた場合、全体の属性も無属性になる
                current_element = ELEM_NONE;
            } else if (e == ELEM_LIGHT) {
                // 光属性が重ねられた場合、現在が無属性なら光属性になり、すでに特定属性があれば維持
                if (current_element == ELEM_NONE) {
                    current_element = ELEM_LIGHT;
                }
            } else {
                // 特定属性（火、水、木、土、闇）が重ねられた場合
                if (current_element == ELEM_NONE) {
                    current_element = e;
                } else if (current_element == ELEM_LIGHT) {
                    current_element = e;
                } else if (current_element != e) {
                    current_element = ELEM_NONE;
                }
            }
        }

        if (card_id == ID_ABSORPTION || card_id == ID_VINE_SHOOT || card_id == ID_GHOST_SWORD || card_id == ID_REAL_GHOST_SWORD) {
            info.absorption = true;
        }
        if (card_id == ID_EVIL_BROADSWORD) {
            info.deal_same_damage = true;
        }
    }

    info.attack_power = total_atk;
    info.element = current_element;

    info.hit = true;
    for (int i = 0; i < state.num_staged_cards[player_id]; ++i) {
        int card_id = state.true_hand[player_id][state.staged_cards[player_id][i]];
        const CardFeatures &f = g_card_registry[card_id];
        if (f.accuracy < 100) {
            std::uniform_int_distribution<int> dist(0, 99);
            if (dist(state.rng) >= f.accuracy) {
                info.hit = false;
                break;
            }
        }
    }

    return info;
}

static void apply_sickness(InternalState &state, int player_id, int new_sick) {
    if (new_sick > 0) {
        int cur_sick = state.sickness[player_id];
        if (cur_sick == 0) {
            state.sickness[player_id] = new_sick;
        } else {
            if (new_sick > cur_sick) {
                state.sickness[player_id] = new_sick;
            } else {
                if (cur_sick == 4) {
                    state.hp[player_id] = 0;
                } else {
                    state.sickness[player_id] = cur_sick + 1;
                }
            }
        }
    }
}

static void trigger_next_ring_counter(InternalState &state) {
    state.num_pending_counters--;
    int idx = state.num_pending_counters;
    int attacker = state.pending_counter_attacker[idx];
    int defender = state.pending_counter_defender[idx];

    state.attacker_id = attacker;
    state.defender_id = defender;
    state.current_actor_id = defender;
    state.current_phase = GamePhase::PHASE_DEFENSE;

    state.pending_attack_power = state.pending_counter_power[idx];
    state.pending_attack_element = state.pending_counter_element[idx];
    state.pending_absorption = false;
    state.pending_deal_same_damage = false;
    state.pending_is_group_attack = false;
    state.pending_attack_curse = state.pending_counter_curse[idx];
    state.pending_take_cp = state.pending_counter_take_cp[idx];
    state.pending_attack_source_id = state.pending_counter_source_id[idx];
    state.num_staged_cards[defender] = 0;
}

static void process_ring_defense_effects(InternalState &state, int me, int opp, int damage) {
    if (damage <= 0) return;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.true_hand[me][state.staged_cards[me][i]];
        if (card_id == ID_MARS_RING) {
            int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
            if (roll < 75 && state.num_pending_counters < 10) {
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

static void setup_multiple_attacks(InternalState &state, int me, int opp, const StagedAttackInfo &info) {
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
                    state.current_phase = GamePhase::PHASE_GROUP_MIRACLE;
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
                if (!state.is_done && state.current_phase != GamePhase::PHASE_DEFENSE) {
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
                state.current_phase = GamePhase::PHASE_GROUP_WEAPON;
            }
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        // あぶないキネが含まれているか確認
        bool has_dangerous_pestle = false;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            if (state.true_hand[me][state.staged_cards[me][i]] == ID_DANGEROUS_PESTLE) {
                has_dangerous_pestle = true;
                break;
            }
        }

        if (has_dangerous_pestle) {
            // お互いの手札にある「あぶないウス」の枚数をカウント
            int count_a = 0;
            int count_b = 0;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[me][j] == ID_DANGEROUS_MORTAR && !state.is_used[me][j]) {
                    count_a++;
                }
                if (state.true_hand[opp][j] == ID_DANGEROUS_MORTAR && !state.is_used[opp][j]) {
                    count_b++;
                }
            }
            int total_us = count_a + count_b;

            if (total_us > 0) {
                // パターンB: ウスが存在する場合 (防御不可の99ダメージ、被弾側のみ1枚消費)
                int r = std::uniform_int_distribution<int>(0, total_us - 1)(state.rng);
                int victim = (r < count_a) ? me : opp;

                StagedAttackInfo info = evaluate_staged_attack(state, me);
                state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

                // 被弾プレイヤーに防御不可の99ダメージ
                state.hp[victim] = std::clamp(state.hp[victim] - 99, 0, 99);

                // 被弾側のみウスを1枚消費
                for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                    if (state.true_hand[victim][j] == ID_DANGEROUS_MORTAR && !state.is_used[victim][j]) {
                        state.is_used[victim][j] = true;
                        break;
                    }
                }

                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, victim, used_cards);

                state.current_phase = GamePhase::PHASE_END;
                return;
            } else {
                // パターンA: ウスが存在しない場合 (50:50のランダムで光30の物理攻撃)
                int r = std::uniform_int_distribution<int>(0, 1)(state.rng);
                int actual_target = (r == 0) ? me : opp;

                StagedAttackInfo info = evaluate_staged_attack(state, me);
                state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

                if (!info.hit) {
                    state.current_phase = GamePhase::PHASE_END;
                    return;
                }

                state.pending_attack_power = info.attack_power;
                state.pending_attack_element = info.element;
                state.pending_absorption = info.absorption;
                state.pending_deal_same_damage = info.deal_same_damage;
                state.defender_id = actual_target;
                state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;

                if (actual_target == me) {
                    // 自傷：防御不可、直接ダメージ
                    if (info.attack_power > 0) {
                        int intended_damage = info.attack_power;
                        state.hp[me] = std::clamp(state.hp[me] - info.attack_power, 0, 99);
                        if (state.pending_absorption) {
                            state.hp[me] = std::clamp(state.hp[me] + intended_damage, 0, 99);
                        }
                        if (state.pending_deal_same_damage) {
                            state.hp[me] = std::clamp(state.hp[me] - intended_damage, 0, 99);
                        }
                    }
                    auto used_cards = get_staged_card_ids(state, me);
                    apply_card_effects_to_target(state, me, used_cards);
                    state.current_phase = GamePhase::PHASE_END;
                } else {
                    // 相手への攻撃：防御フェイズへ移行
                    state.current_actor_id = actual_target;
                    state.current_phase = GamePhase::PHASE_DEFENSE;
                }
                return;
            }
        }

        // 通常の武器攻撃解決
        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!info.hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            setup_multiple_attacks(state, me, target, info);

            state.pending_attack_power = info.attack_power;
            state.pending_attack_element = info.element;
            state.pending_absorption = info.absorption;
            state.pending_deal_same_damage = info.deal_same_damage;
            state.defender_id = target;
            state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;

            if (target == me) {
                int times = state.remaining_attacks;
                for (int t = 0; t < times; ++t) {
                    if (info.attack_power > 0) {
                        int intended_damage = info.attack_power;
                        state.hp[me] = std::clamp(state.hp[me] - info.attack_power, 0, 99);
                        if (state.pending_absorption) {
                            state.hp[me] = std::clamp(state.hp[me] + intended_damage, 0, 99);
                        }
                        if (state.pending_deal_same_damage) {
                            state.hp[me] = std::clamp(state.hp[me] - intended_damage, 0, 99);
                        }
                    }
                    auto used_cards = get_staged_card_ids(state, me);
                    apply_card_effects_to_target(state, me, used_cards);
                }
                state.remaining_attacks = 0;
                state.current_phase = GamePhase::PHASE_END;
            } else {
                state.current_actor_id = target;
                state.current_phase = GamePhase::PHASE_DEFENSE;
            }
        }
    }
}

void step_phase_group_weapon(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_TARGET_OPP) {
        int target = opp;

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!info.hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            setup_multiple_attacks(state, me, target, info);

            state.pending_attack_power = info.attack_power;
            state.pending_attack_element = info.element;
            state.pending_absorption = info.absorption;
            state.pending_deal_same_damage = info.deal_same_damage;
            state.defender_id = target;
            state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;
            state.current_actor_id = target;
            state.current_phase = GamePhase::PHASE_DEFENSE;
        }
    }
}

void step_phase_group_miracle(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_TARGET_OPP) {
        int target = opp;

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!info.hit) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            state.pending_attack_power = info.attack_power;
            state.pending_attack_element = info.element;
            state.pending_absorption = info.absorption;
            state.defender_id = target;
            state.pending_attack_source_id = (state.num_staged_cards[me] > 0) ? state.true_hand[me][state.staged_cards[me][0]] : CARD_EMPTY;
            state.current_actor_id = target;
            state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
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
        bool rainbow = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            total_def += f.defense_power;
            if (card_id == ID_RAINBOW_CURTAIN) rainbow = true;

            // 熱狂仮面の処理
            if (card_id == ID_FEVER_MASK) {
                apply_sickness(state, me, 2); // SICKNESS_FEVER
            }
            // 夢見る帽子の処理
            else if (card_id == ID_DREAMING_HAT) {
                state.curses[me][static_cast<int>(CurseType::CURSE_DREAM)] = true;
                
                bool is_staged[MAX_HAND_SIZE] = {false};
                for (int k = 0; k < state.num_staged_cards[me]; ++k) {
                    is_staged[state.staged_cards[me][k]] = true;
                }
                for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                    if (!is_staged[j]) {
                        if (state.true_hand[me][j] != CARD_EMPTY || state.is_deployed[me][j]) {
                            clear_hand_slot(state, me, j);
                            state.is_used[me][j] = true;
                        }
                    }
                }
            }
        }

        ReactionType react_type = REACTION_NONE;
        Element effective_atk_element = rainbow ? ELEM_NONE : state.pending_attack_element;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            int card_id = state.true_hand[me][h_idx];
            const CardFeatures &f = g_card_registry[card_id];
            if (card_id == ID_RAINBOW_CURTAIN) continue;
            if (is_active_reaction_card(card_id, GamePhase::PHASE_DEFENSE, effective_atk_element)) {
                react_type = f.reaction_type;
            }
        }

        int total_mp_cost = calculate_staged_mp_cost(state, me);

        if (react_type == REACTION_BLOCK) {
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            handle_remaining_attacks_transition(state, me, GamePhase::PHASE_DEFENSE);
            return;
        } else if (react_type == REACTION_REFLECT || react_type == REACTION_BOUNCE) {
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            bool success = true;
            if (react_type == REACTION_BOUNCE) {
                int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                success = (roll < 50);
            }
            if (success) {
                // Reflect back to attacker (opp)
                state.attacker_id = me;
                state.defender_id = opp;
                state.current_actor_id = opp;
                state.current_phase = GamePhase::PHASE_DEFENSE;
                state.num_staged_cards[me] = 0;
                state.num_staged_cards[opp] = 0;
                return;
            } else {
                // Bounce failed -> self harm!
                int damage = std::max(0, state.pending_attack_power - total_def);
                process_ring_defense_effects(state, me, opp, damage);

                if (state.pending_attack_source_id == ID_FINE) {
                    int total_paid = 0;
                    if (state.money[me] >= damage) {
                        state.money[me] -= damage;
                        total_paid = damage;
                    } else {
                        total_paid += state.money[me];
                        int remaining = damage - state.money[me];
                        state.money[me] = 0;
                        if (state.mp[me] >= remaining) {
                            state.mp[me] -= remaining;
                            total_paid += remaining;
                        } else {
                            total_paid += state.mp[me];
                            remaining -= state.mp[me];
                            state.mp[me] = 0;
                            state.hp[me] = std::max(0, state.hp[me] - remaining);
                        }
                    }
                    state.money[opp] = std::min(99, state.money[opp] + total_paid);
                } else {
                    if (state.pending_attack_source_id == ID_COLORED_LEAVES) {
                        state.curses[me][static_cast<int>(CurseType::CURSE_DREAM)] = true;
                    } else if (state.pending_attack_source_id == ID_OMINOUS_PREMONITION) {
                        state.curses[me][static_cast<int>(CurseType::CURSE_DARK_CLOUD)] = true;
                    } else if (state.pending_attack_source_id == ID_HALO) {
                        state.curses[me][static_cast<int>(CurseType::CURSE_FLASH)] = true;
                    } else {
                        if (damage > 0 && state.pending_attack_element == ELEM_DARKNESS && !rainbow) {
                            state.hp[me] = 0;
                        } else {
                            state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
                        }
                        if (state.pending_absorption) {
                            state.hp[me] = std::clamp(state.hp[me] + damage, 0, 99);
                        }
                        if (state.pending_deal_same_damage) {
                            state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
                        }
                    }
                }

                if (state.hp[me] == 0) {
                    bool paused = run_death_check(state);
                    if (paused) return;
                    if (state.is_done) return;
                }

                bool is_hit = (state.pending_attack_power > 0) ? (damage > 0) : (total_def == 0);
                if (state.pending_attack_source_id == ID_COLORED_LEAVES || state.pending_attack_source_id == ID_OMINOUS_PREMONITION || state.pending_attack_source_id == ID_HALO) {
                    is_hit = true;
                }
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

                auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
                apply_card_effects_to_target(state, me, attacker_used_cards);
                handle_remaining_attacks_transition(state, me, GamePhase::PHASE_DEFENSE);
                return;
            }
        }

        // REACTION_NONE (一般防具で軽減)
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
        int damage = std::max(0, state.pending_attack_power - total_def);
        process_ring_defense_effects(state, me, opp, damage);

        if (state.pending_attack_source_id == ID_FINE) {
            int total_paid = 0;
            if (state.money[me] >= damage) {
                state.money[me] -= damage;
                total_paid = damage;
            } else {
                total_paid += state.money[me];
                int remaining = damage - state.money[me];
                state.money[me] = 0;
                if (state.mp[me] >= remaining) {
                    state.mp[me] -= remaining;
                    total_paid += remaining;
                } else {
                    total_paid += state.mp[me];
                    remaining -= state.mp[me];
                    state.mp[me] = 0;
                    state.hp[me] = std::max(0, state.hp[me] - remaining);
                }
            }
            state.money[opp] = std::min(99, state.money[opp] + total_paid);
        } else {
            if (state.pending_attack_source_id == ID_COLORED_LEAVES) {
                state.curses[me][static_cast<int>(CurseType::CURSE_DREAM)] = true;
            } else if (state.pending_attack_source_id == ID_OMINOUS_PREMONITION) {
                state.curses[me][static_cast<int>(CurseType::CURSE_DARK_CLOUD)] = true;
            } else if (state.pending_attack_source_id == ID_HALO) {
                state.curses[me][static_cast<int>(CurseType::CURSE_FLASH)] = true;
            } else {
                if (damage > 0 && state.pending_attack_element == ELEM_DARKNESS && !rainbow) {
                    state.hp[me] = 0;
                } else {
                    state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
                }
                if (state.pending_absorption) {
                    state.hp[opp] = std::clamp(state.hp[opp] + damage, 0, 99);
                }
                if (state.pending_deal_same_damage && damage > 0) {
                    state.hp[opp] = std::clamp(state.hp[opp] - damage, 0, 99);
                }
            }
        }

        if (state.hp[me] == 0) {
            bool paused = run_death_check(state);
            if (paused) return;
            if (state.is_done) return;
        }

        bool is_hit = (state.pending_attack_power > 0) ? (damage > 0) : (total_def == 0);
        if (state.pending_attack_source_id == ID_COLORED_LEAVES || state.pending_attack_source_id == ID_OMINOUS_PREMONITION || state.pending_attack_source_id == ID_HALO) {
            is_hit = true;
        }
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

        auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
        apply_card_effects_to_target(state, me, attacker_used_cards);
        handle_remaining_attacks_transition(state, me, GamePhase::PHASE_DEFENSE);
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
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

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

            if (target == me) {
                if (info.attack_power > 0) {
                    int intended_damage = info.attack_power;
                    state.hp[me] = std::clamp(state.hp[me] - info.attack_power, 0, 99);
                    if (state.pending_absorption) {
                        state.hp[me] = std::clamp(state.hp[me] + intended_damage, 0, 99);
                    }
                    if (state.pending_deal_same_damage) {
                        state.hp[me] = std::clamp(state.hp[me] - intended_damage, 0, 99);
                    }
                }
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, me, used_cards);
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
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_CONFIRM) {
        int total_def = 0;
        bool rainbow = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            if (card_id == ID_RAINBOW_CURTAIN) rainbow = true;
            total_def += g_card_registry[card_id].defense_power;
        }

        ReactionType react_type = REACTION_NONE;
        Element effective_atk_element = rainbow ? ELEM_NONE : state.pending_attack_element;
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            int card_id = state.true_hand[me][h_idx];
            const CardFeatures &f = g_card_registry[card_id];
            if (card_id == ID_RAINBOW_CURTAIN) continue;
            if (is_active_reaction_card(card_id, GamePhase::PHASE_MIRACLE_DEFENSE, effective_atk_element)) {
                react_type = f.reaction_type;
            }
        }

        int total_mp_cost = calculate_staged_mp_cost(state, me);

        if (react_type == REACTION_BLOCK) {
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            handle_remaining_attacks_transition(state, me, GamePhase::PHASE_MIRACLE_DEFENSE);
            return;
        } else if (react_type == REACTION_REFLECT || react_type == REACTION_BOUNCE) {
            state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
            bool success = true;
            if (react_type == REACTION_BOUNCE) {
                int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                success = (roll < 50);
            }
            if (success) {
                // Reflect back to attacker (opp)
                state.attacker_id = me;
                state.defender_id = opp;
                state.current_actor_id = opp;
                state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
                state.num_staged_cards[me] = 0;
                state.num_staged_cards[opp] = 0;
                return;
            } else {
                // Bounce failed -> self harm!
                int damage = std::max(0, state.pending_attack_power - total_def);
                if (damage > 0 && state.pending_attack_element == ELEM_DARKNESS && !rainbow) {
                    state.hp[me] = 0;
                } else {
                    state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
                }

                if (state.pending_absorption) {
                    state.hp[me] = std::clamp(state.hp[me] + damage, 0, 99);
                }
                if (state.pending_deal_same_damage) {
                    state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
                }

                if (state.hp[me] == 0) {
                    state.current_phase = GamePhase::PHASE_END;
                    return;
                }

                auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
                apply_card_effects_to_target(state, me, attacker_used_cards);
                handle_remaining_attacks_transition(state, me, GamePhase::PHASE_MIRACLE_DEFENSE);
                return;
            }
        }

        // REACTION_NONE
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
        int damage = std::max(0, state.pending_attack_power - total_def);

        if (damage > 0 && state.pending_attack_element == ELEM_DARKNESS && !rainbow) {
            state.hp[me] = 0;
        } else {
            state.hp[me] = std::clamp(state.hp[me] - damage, 0, 99);
        }

        if (state.hp[me] == 0) {
            state.current_phase = GamePhase::PHASE_END;
            return;
        }

        if (state.pending_absorption) {
            state.hp[opp] = std::clamp(state.hp[opp] + damage, 0, 99);
        }
        if (state.pending_deal_same_damage && damage > 0) {
            state.hp[opp] = std::clamp(state.hp[opp] - damage, 0, 99);
        }

        auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
        apply_card_effects_to_target(state, me, attacker_used_cards);
        handle_remaining_attacks_transition(state, me, GamePhase::PHASE_MIRACLE_DEFENSE);
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
        if (state.num_staged_cards[opp] > 0 && state.staged_cards[opp][0] == -1) {
            std::vector<int> candidates;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[me][j] != CARD_EMPTY && !state.is_deployed[me][j] && !state.is_used[me][j]) {
                    candidates.push_back(j);
                }
            }
            if (!candidates.empty()) {
                std::shuffle(candidates.begin(), candidates.end(), state.rng);
                int sell_idx = candidates[0];
                state.staged_cards[me][0] = -1; // ダミー
                state.staged_cards[me][1] = sell_idx;
                state.num_staged_cards[me] = 2;
                execute_sell_resolution(state, me, opp); // 売り手 me, 買い手 opp
            }
            state.num_staged_cards[0] = 0;
            state.num_staged_cards[1] = 0;
            state.current_phase = GamePhase::PHASE_END;
            return;
        }

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

            clear_hand_slot(state, seller, revealed_idx);

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
                    clear_hand_slot(state, buyer, replace_idx);
                    state.true_hand[buyer][replace_idx] = card_id;
                    state.is_known_to_opp[buyer][replace_idx] = true;
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
                clear_hand_slot(state, me, hand_idx);
            }
            state.num_staged_cards[me] = 0;
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}
