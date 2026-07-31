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
        int slot = staged_hand_slot(state, player, i);
        if (slot != NO_HAND_SLOT) confirm_card(state, player, slot);
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

    // マジカルステッキの威力は「残りMP×2」なので、ステッキ以外の消費MPが要る。
    // 以前はこの計算を calculate_staged_mp_cost() と別々に書いており、精霊系の規則が
    // 2箇所に複製されていた（片方だけ変えると攻撃力とMP消費が食い違う）。
    int other_mp_cost = calculate_mp_cost_excluding_magical_stick(state, player_id, nullptr);

    for (size_t i = 0; i < card_ids.size(); ++i) {
        int card_id = card_ids[i];
        if (card_id == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[card_id];

        // 精霊系カードを「奇跡に重ねた」場合は、そのカード自身の攻撃力・属性を持ち込まない。
        // 効果は直前の奇跡の消費MPを0にすることだけで、プラス攻撃ではないため。
        //
        // 1枚目に置かれた場合は別で、精霊の杖は攻撃力12の無属性武器として普通に働く
        // （usage_timing が main_atk_phase と miracle_plus_phase の両方を持つ）。
        // 以前はこの区別が無く、＜炎＞（攻10）に精霊の杖を重ねると攻撃力が22になっていた。
        const bool used_as_spiritual = is_used_as_spiritual(card_ids, i);

        if (used_as_spiritual) {
            // 攻撃力にも属性にも関与しない
            continue;
        }

        if (card_id == ID_AURA) {
            total_atk *= 2;
        } else if (card_id == ID_MAGICAL_STICK) {
            int remaining_mp = std::max(0, state.mp[player_id] - other_mp_cost);
            total_atk += remaining_mp * 2;
        } else {
            total_atk += f.attack_power;
        }

        // 属性判定
        if (is_element_overriding_wand(card_id)) {
            // ワンドによる属性上書き（無条件で攻撃をその属性にする）
            current_element = f.element;
            has_processed = true;
        } else {
            // 【属性の合成規則】重ねた順に1枚ずつ current_element へ畳み込む。
            //   1. 無属性が1枚でも混ざれば無属性になる
            //   2. 光は中立。他の属性と混ざるとその属性になり、光同士なら光のまま
            //   3. ただし光は闇の代わりにはなれない。光と闇が混ざると無属性になる
            //   4. 異なる通常属性同士（火＋土など）は打ち消し合って無属性になる
            // 規則そのものは tests/core/test_combat_flow.py の ELEMENT_RULE_CASES が
            // 日本語付きの表で網羅している。挙動を変えるときはそちらも見ること。
            Element e = f.element;
            if (!has_processed) {
                current_element = e;
                has_processed = true;
            } else {
                if (e == ELEM_NONE || current_element == ELEM_NONE) {
                    current_element = ELEM_NONE;                  // 規則1
                } else if (e == ELEM_LIGHT) {
                    // 光を足す: 相手が闇なら打ち消し、それ以外は元の属性を保つ（規則2・3）
                    if (current_element == ELEM_DARKNESS) {
                        current_element = ELEM_NONE;
                    }
                } else if (current_element == ELEM_LIGHT) {
                    // 光に足す: 闇なら打ち消し、それ以外は足した側の属性になる（規則2・3）
                    if (e == ELEM_DARKNESS) {
                        current_element = ELEM_NONE;
                    } else {
                        current_element = e;
                    }
                } else if (current_element != e) {
                    current_element = ELEM_NONE;                  // 規則4
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

    return info;
}

/**
 * @brief 仮置きされた武器・奇跡の命中判定を行います（乱数を消費します）。
 *
 * この判定は evaluate_staged_attack から意図的に分離しています。以前は
 * evaluate_staged_attack の中で判定していたため、
 *   - 仮置きのたびに呼ばれる update_staged_pending_info（観測へ攻撃力・属性を
 *     反映するだけのプレビュー）でも判定が行われ、その結果は捨てられていた
 *   - 自分自身を対象にする解決（命中判定を使わない経路）でも判定が行われていた
 * ため、1回の攻撃で命中判定が2回転がり、消費される乱数の量が仮置き・解除の
 * 回数に依存していました。最終的な命中率は変わりませんが、「攻撃力を計算すると
 * 乱数が進む」という非純粋性は、プレビューと実結果が食い違う実装を招きやすいので
 * 解決時にだけ判定するようにしています。
 *
 * @param player_id 攻撃側のプレイヤーID。
 * @return 命中したなら true。暗雲がかかっている相手への攻撃は判定せず必中。
 */
bool roll_staged_attack_hits(InternalState &state, int player_id) {
    for (int card_id : get_staged_card_ids(state, player_id)) {
        if (card_id == CARD_EMPTY) continue;
        const CardFeatures &f = g_card_registry[card_id];
        if (f.accuracy < 100 && !state.curses[1 - player_id][CURSE_TYPE_DARK_CLOUD]) {
            if (roll_range(state, RollKind::ACCURACY, 0, 99) >= f.accuracy) {
                return false;
            }
        }
    }
    return true;
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

    // 防御力は解決側と同じ関数で求める。効果の方を使ったカード（リアクション・
    // 精霊系）は防具として出していないので守を持ち込まない。
    // ここが解決側とずれると、エージェントには効かない防御力が見える。
    state.pending_defense_power =
        evaluate_staged_defense(state, player_id, state.current_phase).total_defense;
}



static void trigger_next_ring_counter(InternalState &state) {
    // 指輪の反撃は「使われた順」に解決する（先入れ先出し）。
    // 以前は末尾から取り出しており、後から使った指輪の反撃が先に解決していた。
    const PendingCounter c = state.pending_counters[0];
    state.num_pending_counters--;
    for (int i = 0; i < state.num_pending_counters; ++i) {
        state.pending_counters[i] = state.pending_counters[i + 1];
    }

    state.attacker_id = c.attacker;
    state.defender_id = c.defender;
    state.current_actor_id = c.defender;

    if (is_non_damage_ring_counter(c.source_id)) {
        // 指輪の反撃は、反撃した側（defender）が仕掛けた側になる
        state.pending_initiator = c.defender;
        state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
    } else {
        state.current_phase = GamePhase::PHASE_DEFENSE;
    }

    state.pending_attack_power = c.power;
    state.pending_attack_element = c.element;
    state.pending_absorption = false;
    state.pending_deal_same_damage = false;
    state.pending_is_group_attack = false;
    state.pending_attack_curse = c.curse;
    state.pending_take_cp = c.take_cp;
    state.pending_attack_source_id = c.source_id;
    state.num_staged_cards[c.defender] = 0;

    push_event(state, c.defender, EventType::RING_EFFECT, c.source_id, c.attacker, 0.0f);
}

static void process_ring_defense_effects(InternalState &state, int me, int opp, int damage) {
    if (damage <= 0) return;

    // 指輪の反撃は使われた順に積む（解決も同じ順＝先入れ先出し）。
    auto enqueue = [&](const PendingCounter &c) {
        if (state.num_pending_counters >= MAX_PENDING_COUNTERS) return;
        state.pending_counters[state.num_pending_counters++] = c;
    };

    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = staged_card_id(state, me, i);
        PendingCounter c;
        c.attacker = me;
        c.defender = opp;
        c.source_id = card_id;

        if (card_id == ID_MARS_RING) {
            // 火星の指輪だけは確率で発動する
            if (roll_range(state, RollKind::MARS_RING, 0, 99) >= MARS_RING_RATE) continue;
            c.power = damage;
            c.element = ELEM_FIRE;
        } else if (card_id == ID_MERCURY_RING) {
            c.element = ELEM_WATER;
            c.curse = CURSE_FOG;
        } else if (card_id == ID_JUPITER_RING) {
            c.element = ELEM_WOOD;
            c.curse = CURSE_DREAM;
        } else if (card_id == ID_SATURN_RING) {
            c.power = damage * 2;
            c.element = ELEM_STONE;
        } else if (card_id == ID_URANUS_RING) {
            c.element = ELEM_LIGHT;
            c.curse = CURSE_FLASH;
        } else if (card_id == ID_PLUTO_RING) {
            c.element = ELEM_DARKNESS;
            c.curse = CURSE_DARK_CLOUD;
        } else if (card_id == ID_VENUS_RING) {
            c.power = damage;
            c.take_cp = true;
        } else if (card_id == ID_NEPTUNE_RING) {
            // 海王の指輪だけは反撃ではなく即時のMP回復
            state.mp[me] = std::clamp(state.mp[me] + damage * 2, 0, 99);
            push_event(state, me, EventType::RING_EFFECT, card_id, opp, 0.0f);
            continue;
        } else {
            continue;
        }
        enqueue(c);
    }
}

void setup_multiple_attacks(InternalState &state, int me, int opp, const StagedAttackInfo &info) {
    bool has_saw_boom_boom = false;
    int mirage_count = 0;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = staged_card_id(state, me, i);
        if (card_id == ID_SAW_BOOM_BOOM) {
            has_saw_boom_boom = true;
        } else if (card_id == ID_MIRAGE) {
            mirage_count++;
        }
    }
    int base_attacks = has_saw_boom_boom ? SAW_BOOM_BOOM_ATTACK_COUNT : 1;
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
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
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

            int card_id = staged_card_id(state, me, 0);
            if (card_id == ID_SELL || card_id == ID_BUY) {
                // 取引を誰に仕掛けたのかを記録する。他のカードは対象選択の時点で
                // CONFIRM_ATTACK を出すが、売る・買うだけは以前ここより手前で
                // return しており、対象が履歴に残らなかった。とくに「買うを
                // 自分に使う」経路（下）はイベントを1件も出さないため、手札が
                // 1枚公開されるのにログが空という状態になっていた。
                push_event(state, me, EventType::CONFIRM_ATTACK, card_id, target, 0.0f);
            }
            if (card_id == ID_SELL) {
                state.attacker_id = me;
                state.defender_id = target;
                state.pending_initiator = me;  // 反射しても「仕掛けた側」は変わらない
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
                state.pending_initiator = me;
                if (target == me) {
                    std::vector<int> candidates;
                    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                        if (state.true_hand[me][j] != CARD_EMPTY && !state.is_deployed[me][j] && !state.is_used[me][j]) {
                            candidates.push_back(j);
                        }
                    }
                    if (!candidates.empty()) {
                        shuffle_by_value(state, RollKind::REVEAL_SLOT, candidates);
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
                    apply_darkness_self_death(state, me, info.attack_power);
                } else {
                    apply_card_effects_to_target(state, target, used_cards);
                }
                // 効果をすべて解決してから死亡判定を行う。天国草を自分に使って発作死する
                // 経路もここに含まれる（apply_heaven_seizure_death は自分では復活させない）。
                run_immediate_revive(state);
                state.num_staged_cards[me] = 0;
                if (!state.is_done && state.current_phase != GamePhase::PHASE_DEFENSE) {
                    state.current_phase = GamePhase::PHASE_END;
                }
            } else {
                for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                    int h_idx = staged_hand_slot(state, me, i);
                    if (h_idx >= 0 && h_idx < MAX_HAND_SIZE) {
                        state.is_known_to_opp[me][h_idx] = true;
                    }
                }
                auto used_cards = get_staged_card_ids(state, me);
                int first_card = (!used_cards.empty()) ? used_cards[0] : -1;
                push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

                state.attacker_id = me;
                state.defender_id = target;
                state.pending_initiator = me;
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
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
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
            int h_idx = staged_hand_slot(state, me, 0);
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
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
            state.is_used[me][idx] = true;
            if (is_weapon) {
                update_staged_pending_info(state, me);
            }
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
        }
    } else if (action == ACTION_TARGET_OPP) {
        int target = opp;
        confirm_all_staged_cards(state, me);
        int first_card = staged_card_id(state, me, 0);
        push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!roll_staged_attack_hits(state, me)) {
            push_event(state, me, EventType::ATTACK_MISS, first_card, target, 0.0f);
            state.current_phase = GamePhase::PHASE_END;
        } else {
            push_event(state, me, EventType::ATTACK_HIT, first_card, target,
                       static_cast<float>(info.attack_power));
            if (is_weapon) {
                setup_multiple_attacks(state, me, target, info);
            }

            // 以前はここで代入を並べており、pending_attack_curse だけが漏れていた。
            // そのため霧の扇や＜閃光＞など、全体攻撃カードの状態異常が一切
            // 適用されなかった。設定は3経路で共通のヘルパーに寄せてある。
            set_pending_from_staged_attack(state, me, info, target);
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
    // 指輪は属性が合っていて防具として出せるなら、武器攻撃・奇跡攻撃を問わず反撃する。
    // 以前はここが PHASE_DEFENSE に限定されており、奇跡防御では「出せるのに何も
    // 起きない」状態だった（火星の指輪は防御力も持たないため、出すとカードを1枚
    // 失うだけになっていた）。
    process_ring_defense_effects(state, me, opp, damage);

    apply_damage_without_revive(state, me, damage);
    if (damage > 0) {
        push_event(state, me, EventType::TAKE_DAMAGE, -1, me, static_cast<float>(damage));
    }
    if (damage > 0 && is_darkness_attack && !rainbow) {
        // 闇属性即死。ダメージによる守護神退散判定は直前の apply_damage_without_revive() で
        // 済んでおり、HPを0にするこの部分では退散判定を行いません。
        apply_darkness_instant_death(state, me);
    }
    // 吸収と自傷は武器の特殊効果なので、どちらも死亡判定より前に解決する。
    // 途中でお守りを発動させると、邪神の大剣を弾き損ねた側が本体で復活してから
    // 自傷で死ぬ（＝お守りが無駄になる）ことになる。実機では2つのセグメントを
    // まとめて解決し、そのあとで1度だけ復活する。詳細は
    // combat_resolution.cpp の apply_damage() のコメントを参照。
    if (state.pending_absorption) {
        if (is_bounce_failure) {
            state.hp[me] = std::clamp(state.hp[me] + damage, 0, 99);
        } else {
            state.hp[opp] = std::clamp(state.hp[opp] + damage, 0, 99);
        }
    }
    if (state.pending_deal_same_damage && damage > 0) {
        if (is_bounce_failure) {
            apply_damage_without_revive(state, me, damage);
        } else {
            apply_damage_without_revive(state, opp, damage);
        }
    }

    // 命中時の状態異常付与とCP奪取。HPが0になっていても解決される。
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

    // 防具の副作用は、武器攻撃・奇跡攻撃のどちらに対して出した場合も発動する。
    // 以前はここが PHASE_DEFENSE に限定されており、奇跡攻撃に対して熱狂仮面や
    // 夢見る帽子を出しても熱病・夢・神器一新が一切起きなかった（指輪の反撃が
    // 物理防御に限定されていたのと同じ取りこぼし）。
    // 属性防具は対抗属性の奇跡に出せるうえ（＜滝＞に熱狂仮面、＜岩＞に夢見る帽子）、
    // 虹のカーテンを併用すれば属性を問わず出せるので、到達しない経路ではない。
    apply_defense_gear_effects(state, me);

    // ここまでが1回の攻撃解決。太陽のお守りによる復活はここで1度だけ判定する。
    //
    // 以前は「ダメージ直後」「発作（apply_heaven_seizure_death の内部）」
    // 「熱狂仮面の解決後」の3箇所で復活していたため、1回の攻撃でお守りが最大3枚
    // 消費された。実機では、HPが0になったあとも武器の状態異常付与と防具の副作用が
    // 順に解決され、最後にお守りが1枚だけ発動する（激烈疾風剣＋オーラを熱狂仮面4枚で
    // 防いだ場合、HP0 -> 風邪 -> 熱病 -> 地獄病 -> 天国病 -> 発作 -> お守りでHP10・
    // 天国病、で確定）。
    run_immediate_revive(state);

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
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
            state.is_used[me][idx] = true;
            update_staged_pending_info(state, me);
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
        }
    } else if (action == ACTION_CONFIRM) {
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = staged_hand_slot(state, me, i);
            // 防御の仮置きは手札由来のみだが、NO_HAND_SLOT(-1) を添字にすると
            // 静かに範囲外へ書き込むので念のため弾く。
            if (h_idx != NO_HAND_SLOT) state.is_known_to_opp[me][h_idx] = true;
        }

        bool is_darkness_attack = (state.pending_attack_element == ELEM_DARKNESS);

        // 位置に依存する評価（カーテンによる無属性化・効果が出るリアクション・
        // 実際に効く防御力）は、合法手の判定や観測と同じ関数で求める。
        // 以前はここだけ自前で走査しており、
        //   - 位置を見ていなかったため、一般防具を挟んだ後に置いたスカイアーマーの
        //     弾きが発動して攻守が入れ替わっていた
        //   - 観測（pending_defense_power）だけがリアクションカードの守を足しており、
        //     エージェントには効かない防御力が見えていた
        // という食い違いが起きた。
        const StagedDefenseInfo staged = evaluate_staged_defense(state, me, phase);
        rainbow = staged.has_curtain;
        if (rainbow) {
            state.pending_attack_element = ELEM_NONE;
        }
        total_def = staged.total_defense;

        const int react_card_id = staged.reaction_card_id;
        const ReactionType react_type =
            (staged.reaction_index >= 0) ? g_card_registry[react_card_id].reaction_type
                                         : REACTION_NONE;

        int first_card = staged_card_id(state, me, 0);
        push_event(state, me, EventType::CONFIRM_DEFENSE, first_card, opp, static_cast<float>(total_def));

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
                int roll = roll_range(state, RollKind::BOUNCE, 0, 99);
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
            int card_id = card_id_in_hand(state, me, idx);
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
            state.is_used[me][idx] = true;
            // このフェイズだけ STAGE_CARD の発行と仮置き情報の更新が抜けていた。
            // 精霊系カードを重ねて消費MPを0にする操作が履歴に残らず、
            // 他の5つの仮置きフェイズと挙動が食い違っていた。
            update_staged_pending_info(state, me);
            push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        confirm_all_staged_cards(state, me);

        int first_card = staged_card_id(state, me, 0);
        push_event(state, me, EventType::CONFIRM_ATTACK, first_card, target, 0.0f);

        StagedAttackInfo info = evaluate_staged_attack(state, me);
        state.mp[me] = std::clamp(state.mp[me] - info.mp_cost, 0, 99);

        if (!roll_staged_attack_hits(state, me)) {
            state.current_phase = GamePhase::PHASE_END;
        } else {
            set_pending_from_staged_attack(state, me, info, target);

            if (target == me) {
                // 自傷解決は武器経路（execute_attack_from_staged_cards）と共有する。
                // 奇跡は連撃を持たないので1回だけ。
                auto used_cards = get_staged_card_ids(state, me);
                resolve_self_targeted_attack(state, me, info, used_cards, 1);
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
 *
 * 防具の防御力は物理防御と同じように減算されます（docs/rules.md 4.1）。
 * 「1枚目に他の防具を置いた場合や2枚目以降に出した場合はリアクション効果は発動せず、
 * 防具自身の標準防御力が合算される」ためです。実測でも＜炎＞（攻10）に対して
 * 氷の鎧（守6）を出すとダメージが4になります。
 *
 * 物理防御と異なるのは次の2点だけです。
 *   - リアクションカードの合法性判定（is_active_reaction_card）
 *   - 指輪の反撃と防具の追加効果（熱狂仮面・夢見る帽子）は物理防御でのみ発動する
 *     ＝これらのカードは usage_timing に miracle_defence_phase を持たない
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
            state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
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
            shuffle_by_value(state, RollKind::REVEAL_SLOT, candidates);
            int revealed_idx = candidates[0];
            confirm_card(state, me, revealed_idx);
            state.is_known_to_opp[me][revealed_idx] = true;
            state.staged_cards[me][0] = StagedEntry::from_hand(revealed_idx);
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
        // 反射で attacker/defender が入れ替わるため、「今の攻撃側 = 使用した人」ではない。
        // 以前はここで両者の仮置き場を走査して雑貨・奇跡を持つ側を探し、
        // 見つからなければ黙って attacker_id を使っていた（誤った側へ効果が飛ぶ）。
        int original_caster = state.pending_initiator;
        if (original_caster < 0 || original_caster > 1) {
            throw std::runtime_error("雑貨の反射解決で、使用した側が記録されていません。");
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
            } else if (is_opponent_discarding_sundry(source_id)) {
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

        // 雑貨・守護神の行動をすべて解決してから死亡判定を行う
        run_immediate_revive(state);

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
        int revealed_idx = staged_hand_slot(state, seller, 0);
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
                int buy_card_idx = staged_hand_slot(state, buyer, 0);
                for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                    if (state.true_hand[buyer][j] != CARD_EMPTY && j != buy_card_idx) {
                        candidates.push_back(j);
                    }
                }
                if (!candidates.empty()) {
                    shuffle_by_value(state, RollKind::HAND_REPLACE_SLOT, candidates);
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

        state.staged_cards[seller][0] = StagedEntry::from_hand(0);
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
                    state.staged_cards[me][state.num_staged_cards[me]++] = StagedEntry::from_hand(idx);
                    state.is_used[me][idx] = true;
                    push_event(state, me, EventType::STAGE_CARD, card_id, -1, 0.0f);
                }
            }
        }
    } else if (action == ACTION_CONFIRM) {
        if (state.num_staged_cards[me] > 0) {
            int discarded_count = state.num_staged_cards[me];
            for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                int hand_idx = staged_hand_slot(state, me, i);
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
