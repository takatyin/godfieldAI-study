#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>
#include <cstring>
#include <vector>
#include <random>
#include <iostream>

/**
 * @brief 指定されたカードが「捨てる」ことが可能なカード（武器・太陽のお守り・あぶないウス以外）かを判定します。
 */
bool is_discardable_card(int card_id) {
    if (card_id == CARD_EMPTY) return false;
    return !g_card_registry[card_id].is_weapon() && card_id != ID_SUN_AMULET && card_id != ID_DANGEROUS_MORTAR;
}

/**
 * @brief 指定されたカードが奇跡の消費MPを0にする「精霊の神器」であるかを判定します。
 */
bool is_spiritual_zero_mp_card(int card_id) {
    return (card_id == ID_SPIRITUAL_STAFF ||
            card_id == ID_SPIRITUAL_SOCKS ||
            card_id == ID_SPIRITUAL_HOOD ||
            card_id == ID_SPIRITUAL_SASH ||
            card_id == ID_SPIRITUAL_DOLL);
}

void deploy_miracle(InternalState &state, int player_id, int slot_idx) {
    if (state.is_deployed[player_id][slot_idx]) {
        return;
    }
    state.is_deployed[player_id][slot_idx] = true;
    state.is_known_to_opp[player_id][slot_idx] = true;

    // 展開キューに積む
    state.deployed_miracles_order[player_id][state.num_deployed_miracles[player_id]] = slot_idx;
    state.num_deployed_miracles[player_id]++;
}

void undeploy_miracle(InternalState &state, int player_id, int slot_idx) {
    if (!state.is_deployed[player_id][slot_idx]) {
        return;
    }
    state.is_deployed[player_id][slot_idx] = false;

    int found_idx = -1;
    for (int k = 0; k < state.num_deployed_miracles[player_id]; ++k) {
        if (state.deployed_miracles_order[player_id][k] == slot_idx) {
            found_idx = k;
            break;
        }
    }
    if (found_idx != -1) {
        for (int k = found_idx + 1; k < state.num_deployed_miracles[player_id]; ++k) {
            state.deployed_miracles_order[player_id][k - 1] = state.deployed_miracles_order[player_id][k];
        }
        state.num_deployed_miracles[player_id]--;
    }
}

void clear_hand_slot(InternalState &state, int player_id, int slot_idx) {
    state.true_hand[player_id][slot_idx] = CARD_EMPTY;
    state.apparent_hand[player_id][slot_idx] = CARD_EMPTY;
    state.is_confirmed[player_id][slot_idx] = true;
    state.is_known_to_opp[player_id][slot_idx] = false;
    state.is_used[player_id][slot_idx] = false;
    state.miracle_used_this_turn[player_id][slot_idx] = false;
    undeploy_miracle(state, player_id, slot_idx);
}

void confirm_card(InternalState &state, int player_id, int slot_idx) {
    if (slot_idx >= 0 && slot_idx < MAX_HAND_SIZE) {
        state.is_confirmed[player_id][slot_idx] = true;
        state.apparent_hand[player_id][slot_idx] = state.true_hand[player_id][slot_idx];
        state.is_known_to_opp[player_id][slot_idx] = true;
    }
}

void clear_all_status_effects(InternalState &state, int player_id) {
    state.sickness[player_id] = SICKNESS_NONE;
    for (int j = 0; j < 4; ++j) {
        state.curses[player_id][j] = false;
    }
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] != CARD_EMPTY) {
            state.is_confirmed[player_id][i] = true;
            state.apparent_hand[player_id][i] = state.true_hand[player_id][i];
        }
    }
}

DreamGroup calculate_dream_group(int card_id) {
    if (card_id < 0 || card_id >= get_registry_size()) return DreamGroup::NONE;
    const CardFeatures &feat = g_card_registry[card_id];
    
    if (feat.is_miracle()) return DreamGroup::NONE;
    if (feat.is_deal()) return DreamGroup::NONE; // 両替, 売る, 買う
    
    // 特殊確定カード（generated_card_ids.hのマクロ定数で判定）
    if (card_id == ID_SUPER_MIRROR || 
        card_id == ID_RAINBOW_CURTAIN || 
        card_id == ID_SPIRITUAL_DOLL || 
        card_id == ID_STRENGTH_POWDER || 
        card_id == ID_SPIRITUAL_STAFF || 
        card_id == ID_JINN_S_ROCKING_HORSE || 
        card_id == ID_FLAMING_ROLL) {
        return DreamGroup::NONE;
    }
    
    // 守護神の行動、および悪魔系カードは常に確定
    if ((feat.usage_timing & TIMING_GUARDIAN) || feat.is_devil()) {
        return DreamGroup::NONE;
    }
    
    // 雑貨 (Sundry)
    if (feat.is_sundry()) {
        if (feat.usage_timing == 0) return DreamGroup::SUNDRY_PASSIVE;
        return DreamGroup::SUNDRY_NORMAL;
    }
    
    // 防具 (Defense)
    if (feat.is_defense()) {
        if (feat.usage_timing & TIMING_MIRACLE_DEFENCE) return DreamGroup::DEF_MIRACLE_COUNTER;
        if (feat.usage_timing & TIMING_MIRACLE_PLUS) return DreamGroup::DEF_SPIRITUAL;
        if (feat.usage_timing & TIMING_ATK_PLUS) return DreamGroup::DEF_PLUS_ATK;
        
        // 属性別 (冥王の指輪は闇属性ですが無属性防具グループに含めます)
        int elem = feat.element;
        if (elem == ELEM_NONE || elem == ELEM_DARKNESS) return DreamGroup::DEF_NONE;
        if (elem == ELEM_FIRE) return DreamGroup::DEF_FIRE;
        if (elem == ELEM_WATER) return DreamGroup::DEF_WATER;
        if (elem == ELEM_WOOD) return DreamGroup::DEF_WOOD;
        if (elem == ELEM_STONE) return DreamGroup::DEF_EARTH;
        if (elem == ELEM_LIGHT) return DreamGroup::DEF_LIGHT;
        return DreamGroup::DEF_NONE;
    }
    
    // 武器 (Weapon)
    if (feat.is_weapon()) {
        if (feat.is_group_attack) return DreamGroup::WPN_GROUP;
        
        // 奇跡対策プラス武器 (スカイハープーン, エンゼルの弓)
        if ((feat.usage_timing & TIMING_MIRACLE_DEFENCE) && (feat.usage_timing & TIMING_ATK_PLUS)) {
            return DreamGroup::WPN_MIRACLE_COUNTER_PLUS;
        }
        // 奇跡対策武器 (月光のオノ, エンゼルナイフ, エンゼルソード, エンゼルアクス)
        if (feat.usage_timing & TIMING_MIRACLE_DEFENCE) {
            return DreamGroup::WPN_MIRACLE_COUNTER;
        }
        // プラス武器
        if (feat.usage_timing & TIMING_ATK_PLUS) {
            return DreamGroup::WPN_PLUS;
        }
        // 攻守兼用武器
        if (feat.usage_timing & TIMING_ATK_DEFENCE) {
            if (feat.reaction_type == REACTION_REFLECT || feat.reaction_type == REACTION_BOUNCE) {
                return DreamGroup::WPN_REFLECT;
            }
            return DreamGroup::WPN_HYBRID;
        }
        return DreamGroup::WPN_NORMAL;
    }
    
    return DreamGroup::NONE;
}

DreamGroup get_dream_group(int card_id) {
    if (card_id < 0 || card_id >= get_registry_size()) return DreamGroup::NONE;
    return g_card_registry[card_id].dream_group;
}

static int get_fake_dream_card(InternalState &state, int true_card_id) {
    DreamGroup target_grp = get_dream_group(true_card_id);
    if (target_grp == DreamGroup::NONE) {
        return true_card_id;
    }
    
    std::vector<int> candidates;
    for (int i = 0; i < get_registry_size(); ++i) {
        if (i == CARD_EMPTY) continue;
        if (get_dream_group(i) == target_grp) {
            candidates.push_back(i);
        }
    }
    if (candidates.empty()) {
        return true_card_id;
    }
    int idx = std::uniform_int_distribution<int>(0, candidates.size() - 1)(state.rng);
    return candidates[idx];
}

void add_card_to_hand_slot(InternalState &state, int player_id, int slot_idx, int card_id, bool is_drawn) {
    clear_hand_slot(state, player_id, slot_idx);
    state.true_hand[player_id][slot_idx] = card_id;
    
    if (card_id == CARD_EMPTY) {
        state.apparent_hand[player_id][slot_idx] = CARD_EMPTY;
        state.is_confirmed[player_id][slot_idx] = true;
        return;
    }

    if (is_drawn) {
        bool has_dream = state.curses[player_id][CURSE_TYPE_DREAM];
        DreamGroup grp = get_dream_group(card_id);
        if (has_dream && grp != DreamGroup::NONE) {
            state.is_confirmed[player_id][slot_idx] = false;
            state.apparent_hand[player_id][slot_idx] = get_fake_dream_card(state, card_id);
        } else {
            state.is_confirmed[player_id][slot_idx] = true;
            state.apparent_hand[player_id][slot_idx] = card_id;
        }
    } else {
        // 取引等で他者から移ったカード、または手動設定：即確定
        state.is_confirmed[player_id][slot_idx] = true;
        state.apparent_hand[player_id][slot_idx] = card_id;
    }
}

/**
 * @brief 対象プレイヤーの仮置き場の最後に置かれたカードが「奇跡」であるかを判定します。
 */
bool is_last_staged_card_miracle(const InternalState &state, int player_id) {
    auto card_ids = get_staged_card_ids(state, player_id);
    if (card_ids.empty()) return false;
    int card_id = card_ids.back();
    if (card_id == CARD_EMPTY) return false;
    return g_card_registry[card_id].is_miracle();
}

/**
 * @brief 現在の仮置き場のカードから、今回の攻撃が「武器（物理）攻撃」であるかを判定します。
 *        （武器が含まれている場合に武器攻撃扱いとなります）
 */
bool is_weapon_attack(const InternalState &state, int player_id) {
    auto card_ids = get_staged_card_ids(state, player_id);
    for (int card_id : card_ids) {
        if (card_id == CARD_EMPTY) continue;
        CardFeatures &f = g_card_registry[card_id];
        if (f.is_weapon() && !is_spiritual_zero_mp_card(card_id)) {
            return true;
        }
    }
    return false;
}

/**
 * @brief 仮置き場のカードの合計消費MPを計算します（精霊による奇跡コスト0化ルールを適用）。
 */
int calculate_staged_mp_cost(const InternalState &state, int player_id) {
    int total_cost = 0;
    auto card_ids = get_staged_card_ids(state, player_id);
    bool has_magical_stick = false;

    for (size_t i = 0; i < card_ids.size(); ++i) {
        int card_id = card_ids[i];
        if (card_id == CARD_EMPTY) continue;
        if (card_id == ID_MAGICAL_STICK) {
            has_magical_stick = true;
            continue;
        }
        const CardFeatures &f = g_card_registry[card_id];

        if (f.is_miracle() && (i + 1 < card_ids.size())) {
            int next_card_id = card_ids[i + 1];
            if (is_spiritual_zero_mp_card(next_card_id)) {
                continue;
            }
        }
        total_cost += f.mp_cost;
    }

    if (has_magical_stick) {
        int remaining_mp = std::max(0, state.mp[player_id] - total_cost);
        total_cost += remaining_mp;
    }

    return total_cost;
}

/**
 * @brief 指定したカードを仮置き場に加えたと仮定し、そのMPコストが支払えるかを判定します。
 */
bool can_afford_staged_plus_card(const InternalState &state, int player_id, int next_hand_idx) {
    InternalState temp = state;
    if (temp.num_staged_cards[player_id] >= MAX_HAND_SIZE) {
        return false;
    }

    // 閃光状態かつ防御フェイズの場合は、同時に1枚しかカードを仮置きできない
    bool has_flash = temp.curses[player_id][CURSE_TYPE_FLASH];
    bool is_defense = (temp.current_phase == GamePhase::PHASE_DEFENSE || temp.current_phase == GamePhase::PHASE_MIRACLE_DEFENSE);
    bool restrict_flash = has_flash && is_defense;

    if (restrict_flash && temp.num_staged_cards[player_id] >= 1) {
        return false;
    }

    temp.staged_cards[player_id][temp.num_staged_cards[player_id]] = next_hand_idx;
    temp.num_staged_cards[player_id]++;
    
    // 1. 仮置き場以外の手札に残っている、未使用の「消費MPを0にする精霊系カード」の個数 U をカウント
    int U = 0;
    if (!restrict_flash) { // 閃光状態かつ防御フェイズでなければ、将来的な精霊カードの重ねがけを考慮する
        bool is_staged[MAX_HAND_SIZE];
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            is_staged[j] = false;
        }
        for (int i = 0; i < temp.num_staged_cards[player_id]; ++i) {
            is_staged[temp.staged_cards[player_id][i]] = true;
        }
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            int card_id = temp.apparent_hand[player_id][j];
            if (card_id < 0) card_id = temp.true_hand[player_id][j];
            if (card_id != CARD_EMPTY && !temp.is_used[player_id][j] && !is_staged[j]) {
                if (is_spiritual_zero_mp_card(card_id)) {
                    U++;
                }
            }
        }
    }

    // 2. 仮置き場にある奇跡カードのうち、直後に精霊系カードが置かれていないもののMPコストをリスト化
    std::vector<int> miracle_costs;
    int base_non_miracle_cost = 0;
    int num_cards = temp.num_staged_cards[player_id];
    for (int i = 0; i < num_cards; ++i) {
        int idx = temp.staged_cards[player_id][i];
        int card_id = temp.apparent_hand[player_id][idx];
        if (card_id < 0) card_id = temp.true_hand[player_id][idx];
        const CardFeatures &f = g_card_registry[card_id];
        if (f.is_miracle()) {
            bool followed_by_spiritual = false;
            if (i + 1 < num_cards) {
                int next_idx = temp.staged_cards[player_id][i + 1];
                int next_card_id = temp.apparent_hand[player_id][next_idx];
                if (next_card_id < 0) next_card_id = temp.true_hand[player_id][next_idx];
                if (is_spiritual_zero_mp_card(next_card_id)) {
                    followed_by_spiritual = true;
                }
            }
            if (!followed_by_spiritual) {
                miracle_costs.push_back(f.mp_cost);
            }
        } else {
            base_non_miracle_cost += f.mp_cost;
        }
    }

    // 3. 奇跡コストの高い順にソートし、残りの精霊系カード U 枚で削減できる最大分を引く
    std::sort(miracle_costs.rbegin(), miracle_costs.rend());
    int total_min_cost = base_non_miracle_cost;
    for (size_t i = 0; i < miracle_costs.size(); ++i) {
        if (static_cast<int>(i) >= U) {
            total_min_cost += miracle_costs[i];
        }
    }

    return temp.mp[player_id] >= total_min_cost;
}

/**
 * @brief メインフェイズにおいて「祈る」（武器がない状態）が可能かを判定します。
 */
bool can_pray(const InternalState &state, int player_id) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.apparent_hand[player_id][i];
        if (card_id != CARD_EMPTY && !state.is_used[player_id][i]) {
            if (g_card_registry[card_id].is_weapon()) return false;
        }
    }
    return true;
}

/**
 * @brief メインフェイズにおいて「捨てる」（捨てられるカードが1枚以上ある）が可能かを判定します。
 */
bool can_discard(const InternalState &state, int player_id) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.apparent_hand[player_id][i];
        if (card_id != CARD_EMPTY && !state.is_used[player_id][i]) {
            if (is_discardable_card(card_id)) return true;
        }
    }
    return false;
}

/**
 * @brief 「売る」カード自体を除いて、売却可能なカードが手札にあるかを判定します。
 */
bool is_sellable_card(const InternalState &state, int player_id, int slot_idx) {
    if (slot_idx < 0 || slot_idx >= MAX_HAND_SIZE) return false;
    return state.true_hand[player_id][slot_idx] != CARD_EMPTY &&
           !state.is_deployed[player_id][slot_idx] &&
           !state.is_used[player_id][slot_idx];
}

bool can_sell_card(const InternalState &state, int player_id, int sell_card_index) {
    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
        if (j != sell_card_index) {
            if (is_sellable_card(state, player_id, j)) {
                return true;
            }
        }
    }
    return false;
}

/**
 * @brief 手札からランダムに1枚カードを破棄し、相手に公開されている同名カードがあれば優先して破棄します。
 */
void discard_one_card_randomly(InternalState &state, int player_id) {
    std::vector<int> candidate_indices;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] != CARD_EMPTY && !state.is_used[player_id][i]) {
            candidate_indices.push_back(i);
        }
    }
    if (candidate_indices.empty()) return;

    std::uniform_int_distribution<int> dist(0, (int)candidate_indices.size() - 1);
    int initial_pick_idx = candidate_indices[dist(state.rng)];
    int target_card_id = state.true_hand[player_id][initial_pick_idx];

    int best_idx = initial_pick_idx;
    for (int idx : candidate_indices) {
        if (state.true_hand[player_id][idx] == target_card_id && state.is_known_to_opp[player_id][idx]) {
            best_idx = idx;
            break;
        }
    }

    clear_hand_slot(state, player_id, best_idx);
}

void apply_devil_little(InternalState &state, int player_id) {
    state.hp[player_id] = std::max(0, state.hp[player_id] - 10);
}

void apply_devil_medium(InternalState &state, int player_id) {
    state.hp[player_id] = std::max(0, state.hp[player_id] - 20);
}

void apply_devil_large(InternalState &state, int player_id) {
    state.hp[player_id] = std::max(0, state.hp[player_id] - 30);
}

void apply_devil_prankster(InternalState &state, int player_id) {
    std::vector<int> candidates;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] != CARD_EMPTY) {
            candidates.push_back(i);
        }
    }
    if (candidates.empty()) return;
    if (candidates.size() <= 2) {
        for (int idx : candidates) {
            clear_hand_slot(state, player_id, idx);
        }
    } else {
        int first = std::uniform_int_distribution<int>(0, candidates.size() - 1)(state.rng);
        int second;
        do {
            second = std::uniform_int_distribution<int>(0, candidates.size() - 1)(state.rng);
        } while (second == first);
        clear_hand_slot(state, player_id, candidates[first]);
        clear_hand_slot(state, player_id, candidates[second]);
    }
}

void apply_devil_fairy(InternalState &state, int player_id) {
    int choice = std::uniform_int_distribution<int>(0, 2)(state.rng);
    if (choice == 0) {
        state.hp[player_id] = std::min(99, state.hp[player_id] + 10);
    } else if (choice == 1) {
        state.mp[player_id] = std::min(99, state.mp[player_id] + 10);
    } else {
        state.money[player_id] = std::min(99, state.money[player_id] + 10);
    }
}

int draw_card_with_apocalypse(InternalState &state, int player_id) {
    while (true) {
        if (state.is_done) {
            return CARD_EMPTY;
        }
        bool is_apocalypse = (state.current_turn >= APOCALYPSE_TURN);
        int card_id = CARD_EMPTY;
        if (is_apocalypse) {
            std::uniform_real_distribution<double> dist(0.0, 100.0);
            double r = dist(state.rng);
            if (r < 7.0) {
                card_id = ID_SMALL_DEVIL;
            } else if (r < 12.0) {
                card_id = ID_MEDIUM_DEVIL;
            } else if (r < 15.0) {
                card_id = ID_LARGE_DEVIL;
            } else if (r < 20.0) {
                card_id = ID_TRICKSTER;
            } else if (r < 25.0) {
                card_id = ID_CHARITY_FAIRY;
            } else {
                card_id = draw_card(state.rng);
            }
        } else {
            card_id = draw_card(state.rng);
        }

        // is_devil に基づく即時解決と再ドロー
        if (card_id != CARD_EMPTY && g_card_registry[card_id].is_devil()) {
            if (card_id == ID_SMALL_DEVIL) {
                apply_devil_little(state, player_id);
            } else if (card_id == ID_MEDIUM_DEVIL) {
                apply_devil_medium(state, player_id);
            } else if (card_id == ID_LARGE_DEVIL) {
                apply_devil_large(state, player_id);
            } else if (card_id == ID_TRICKSTER) {
                apply_devil_prankster(state, player_id);
            } else if (card_id == ID_CHARITY_FAIRY) {
                apply_devil_fairy(state, player_id);
            }

            if (state.hp[player_id] <= 0) {
                state.hp[player_id] = 0;
                bool paused = run_death_check(state);
                if (paused || state.is_done) {
                    return CARD_EMPTY;
                }
            }
            continue; // 再ドロー
        }

        return card_id;
    }
}

/**
 * @brief 空いている手札スロットに新しくカードをドローします。
 */
void draw_card_to_hand(InternalState &state, int player_id) {
    if (state.hp[player_id] <= 0) {
        return;
    }
    int empty_slot_idx = -1;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] == CARD_EMPTY) {
            empty_slot_idx = i;
            break;
        }
    }
    if (empty_slot_idx != -1) {
        int card_id = draw_card_with_apocalypse(state, player_id);
        if (card_id != CARD_EMPTY) {
            add_card_to_hand_slot(state, player_id, empty_slot_idx, card_id, true);
        }
    }
}

/**
 * @brief ターン終了時に使用済みフラグの解決や奇跡の再配置などを行います。
 */
void cleanup_phase_end(InternalState &state) {
    for (int p = 0; p < 2; ++p) {
        state.num_staged_cards[p] = 0;
        
        if (state.hp[p] <= 0) {
            // 死者は is_used フラグのリセットのみを行い、ドローや奇跡の再配置をスキップ
            for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                if (state.is_used[p][i]) {
                    state.is_used[p][i] = false;
                }
            }
            continue;
        }

        int draw_count = 0;
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.is_used[p][i]) {
                int card_id = state.true_hand[p][i];
                if (card_id == CARD_EMPTY) {
                    int new_card = draw_card_with_apocalypse(state, p);
                    add_card_to_hand_slot(state, p, i, new_card, true);
                    state.is_used[p][i] = false;
                    continue;
                }
                CardFeatures &f = g_card_registry[card_id];
                
                if (f.is_miracle()) {
                    deploy_miracle(state, p, i);
                    state.is_used[p][i] = false;
                    draw_count++;
                } else {
                    int new_card = draw_card_with_apocalypse(state, p);
                    add_card_to_hand_slot(state, p, i, new_card, true);
                }
            }
        }
        
        for (int i = 0; i < draw_count; ++i) {
            draw_card_to_hand(state, p);
        }
    }
    state.pending_attack_power = 0;
    state.pending_attack_element = ELEM_NONE;
    state.pending_absorption = false;
    state.pending_deal_same_damage = false;
    state.pending_is_group_attack = false;
    state.num_pending_counters = 0;
    state.pending_attack_curse = CURSE_NONE;
    state.pending_take_cp = false;
    state.pending_attack_source_id = CARD_EMPTY;
}

/**
 * @brief 仮置きされているカードの実際のIDリストを取得します。
 */
std::vector<int> get_staged_card_ids(const InternalState &state, int player) {
    std::vector<int> ids;
    for (int i = 0; i < state.num_staged_cards[player]; ++i) {
        int idx = state.staged_cards[player][i];
        if (idx >= 0 && idx < MAX_HAND_SIZE) {
            int card_id = state.apparent_hand[player][idx];
            if (card_id < 0) card_id = state.true_hand[player][idx];
            ids.push_back(card_id);
        }
    }
    return ids;
}

void apply_sickness(InternalState &state, int player_id, SicknessType new_sick) {
    if (new_sick > SICKNESS_NONE) {
        SicknessType cur_sick = state.sickness[player_id];
        if (cur_sick == SICKNESS_NONE) {
            state.sickness[player_id] = new_sick;
        } else {
            if (new_sick > cur_sick) {
                state.sickness[player_id] = new_sick;
            } else {
                if (cur_sick == SICKNESS_HEAVEN) {
                    state.hp[player_id] = 0;
                } else {
                    state.sickness[player_id] = static_cast<SicknessType>(cur_sick + 1);
                }
            }
        }
    }
}

void apply_curse_to_player(InternalState &state, int player_id, HitCurse curse) {
    if (curse == CURSE_NONE) return;
    SicknessType new_sick = SICKNESS_NONE;
    if (curse == CURSE_COLD) new_sick = SICKNESS_COLD;
    else if (curse == CURSE_FEVER) new_sick = SICKNESS_FEVER;
    else if (curse == CURSE_HELL) new_sick = SICKNESS_HELL;
    else if (curse == CURSE_HEAVEN) new_sick = SICKNESS_HEAVEN;

    if (new_sick > SICKNESS_NONE) {
        apply_sickness(state, player_id, new_sick);
    } else {
        if (curse == CURSE_FOG) {
            state.curses[player_id][CURSE_TYPE_FOG] = true;
        } else if (curse == CURSE_FLASH) {
            state.curses[player_id][CURSE_TYPE_FLASH] = true;
        } else if (curse == CURSE_DARK_CLOUD) {
            state.curses[player_id][CURSE_TYPE_DARK_CLOUD] = true;
        } else if (curse == CURSE_DREAM) {
            state.curses[player_id][CURSE_TYPE_DREAM] = true;
        }
    }
}


/**
 * @brief 適用対象プレイヤーに対して、使用されたカードの回復や状態異常、またはその他特殊カードの効果を処理します。
 */
void apply_card_effects_to_target(InternalState &state, int target_id, const std::vector<int>& used_card_ids) {
    int hp_diff = 0;
    int mp_diff = 0;
    for (int card_id : used_card_ids) {
        CardFeatures &f = g_card_registry[card_id];
        
        // 特殊処理：HP回復
        if (card_id == ID_SMILE_DEW) hp_diff += 5;
        else if (card_id == ID_HEART_DEW) hp_diff += 10;
        else if (card_id == ID_ROMANCE_WATER) hp_diff += 15;
        else if (card_id == ID_GALAXY_GEYSER) hp_diff += 20;

        // 特殊処理：MP回復
        if (card_id == ID_SMILE_FLOWER) mp_diff += 5;
        else if (card_id == ID_HEART_FLOWER) mp_diff += 10;
        else if (card_id == ID_ROMANCE_FRAGRANCE) mp_diff += 15;
        else if (card_id == ID_HEAVEN_HERB) mp_diff += 20;

        if (f.hit_curse != CURSE_NONE && !f.is_weapon() && !f.is_miracle()) {
            apply_curse_to_player(state, target_id, f.hit_curse);
        }

        if (card_id == ID_TONE || card_id == ID_SMILE_SHELL) {
            state.sickness[target_id] = (state.sickness[target_id] == SICKNESS_COLD || state.sickness[target_id] == SICKNESS_FEVER) ? SICKNESS_NONE : state.sickness[target_id];
            state.curses[target_id][CURSE_TYPE_FOG] = false;
            state.curses[target_id][CURSE_TYPE_FLASH] = false;
        } else if (card_id == ID_SONG || card_id == ID_HEART_SHELL) {
            clear_all_status_effects(state, target_id);
        }
        
        if (card_id == ID_RELEASE) {
            state.guardian[0] = GUARDIAN_NONE;
            state.guardian[1] = GUARDIAN_NONE;
        }
        if (card_id == ID_SPRING) {
            hp_diff += 10;
        }
        if (card_id == ID_TREASURE) {
            state.money[target_id] = std::clamp(state.money[target_id] + 10, 0, 99);
        }

        if (card_id == ID_GUARDIAN_POT) {
            std::uniform_int_distribution<int> dist(1, 10);
            state.guardian[target_id] = static_cast<GuardianType>(dist(state.rng));
        }
        if (card_id == ID_THUMP_THUMP_TEAR) {
            std::uniform_int_distribution<int> dist(0, 1);
            hp_diff += (dist(state.rng) == 0) ? 10 : -10;
        }
        if (card_id == ID_NOCTURNAL_BROOM) {
            std::vector<int> target_candidates;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[target_id][j] != CARD_EMPTY && !state.is_deployed[target_id][j] && !state.is_used[target_id][j]) {
                    target_candidates.push_back(j);
                }
            }
            if (!target_candidates.empty()) {
                std::shuffle(target_candidates.begin(), target_candidates.end(), state.rng);
                int num_to_discard = std::min(3, (int)target_candidates.size());
                for (int k = 0; k < num_to_discard; ++k) {
                    int discard_idx = target_candidates[k];
                    clear_hand_slot(state, target_id, discard_idx);
                }
            }
        }
        if (card_id == ID_GODDESS_S_SOAP) {
            std::vector<int> target_candidates;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[target_id][j] != CARD_EMPTY && state.is_deployed[target_id][j]) {
                    target_candidates.push_back(j);
                }
            }
            if (!target_candidates.empty()) {
                std::shuffle(target_candidates.begin(), target_candidates.end(), state.rng);
                int num_to_discard = std::min(2, (int)target_candidates.size());
                for (int k = 0; k < num_to_discard; ++k) {
                    int discard_idx = target_candidates[k];
                    clear_hand_slot(state, target_id, discard_idx);
                }
            }
        }

        if (card_id == ID_STRING_OF_FATE) {
            std::uniform_int_distribution<int> dist(0, 9);
            int phenomenon = dist(state.rng);
            int opp = 1 - target_id;
            push_event(state, target_id, EventType::TRIGGER_PHENOMENON, ID_STRING_OF_FATE, -1, static_cast<float>(phenomenon));

            if (phenomenon == 0) { // 夕焼け: 全員熱病
                state.sickness[0] = SICKNESS_FEVER;
                state.sickness[1] = SICKNESS_FEVER;
            }
            else if (phenomenon == 1) { // 濃霧: 全員霧
                state.curses[0][CURSE_TYPE_FOG] = true;
                state.curses[1][CURSE_TYPE_FOG] = true;
            }
            else if (phenomenon == 2) { // きのこ大発生
                state.mushroom_turns += 6;
            }
            else if (phenomenon == 3) { // 竜巻: 全員HP ➡ 1
                state.hp[0] = 1;
                state.hp[1] = 1;
            }
            else if (phenomenon == 4) { // 巨大なタライ: 自分か相手に光属性攻50
                int target_player = std::uniform_int_distribution<int>(0, 1)(state.rng);
                if (target_player == target_id) { // 自分自身: 防御不可で50ダメ
                    state.hp[target_id] = std::max(0, state.hp[target_id] - 50);
                    if (state.hp[target_id] == 0) {
                        run_death_check(state);
                    }
                } else { // 相手: 防御フェイズ起動
                    state.attacker_id = target_id;
                    state.defender_id = opp;
                    state.current_actor_id = opp;
                    state.current_phase = GamePhase::PHASE_DEFENSE;
                    state.pending_attack_source_id = ID_GIGANTIC_TUB;
                    state.pending_attack_power = 50;
                    state.pending_attack_element = ELEM_LIGHT;
                    state.pending_absorption = false;
                    state.pending_deal_same_damage = false;
                    state.pending_is_group_attack = false;
                    state.pending_attack_curse = CURSE_NONE;
                    state.turn_end_state = 5;
                }
            }
            else if (phenomenon == 5) { // ブラックホール: 自分が撃った全体攻撃
                state.attacker_id = target_id;
                state.defender_id = opp;
                state.current_actor_id = opp;
                state.current_phase = GamePhase::PHASE_DEFENSE;
                state.pending_attack_source_id = ID_BLACK_HOLE;
                state.pending_attack_power = 30;
                state.pending_attack_element = ELEM_DARKNESS;
                state.pending_absorption = false;
                state.pending_deal_same_damage = false;
                state.pending_is_group_attack = true; // 全体攻撃
                state.pending_attack_curse = CURSE_NONE;
                state.turn_end_state = 5;
            }
            else if (phenomenon == 6) { // 暖流: 自身HP+50
                hp_diff += 50;
            }
            else if (phenomenon == 7) { // 金山: お金集約
                int total_money = state.money[0] + state.money[1];
                int lucky = std::uniform_int_distribution<int>(0, 1)(state.rng);
                state.money[lucky] = std::clamp(total_money, 0, 99);
                state.money[1 - lucky] = 0;
            }
            else if (phenomenon == 8) { // 磁気嵐: 手札相互交換 & known_to_opp 追跡
                struct ShuffledCard {
                    int card_id;
                    int original_owner;
                    bool original_known;
                };
                std::vector<ShuffledCard> pool;
                int original_counts[2] = {0, 0};
                
                for (int p = 0; p < 2; ++p) {
                    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                        int cid = state.true_hand[p][i];
                        if (cid != CARD_EMPTY) {
                            bool is_staged = false;
                            for (int k = 0; k < state.num_staged_cards[p]; ++k) {
                                if (state.staged_cards[p][k] == i) {
                                    is_staged = true;
                                    break;
                                }
                            }
                            if (!is_staged) {
                                pool.push_back({cid, p, state.is_known_to_opp[p][i]});
                                original_counts[p]++;
                            }
                        }
                    }
                }
                
                std::shuffle(pool.begin(), pool.end(), state.rng);
                
                bool is_any_dream = state.curses[0][CURSE_TYPE_DREAM] || state.curses[1][CURSE_TYPE_DREAM];
                int pool_idx = 0;
                for (int p = 0; p < 2; ++p) {
                    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                        clear_hand_slot(state, p, i);
                        state.is_known_to_opp[p][i] = false;
                    }
                    for (int i = 0; i < original_counts[p]; ++i) {
                        if (pool_idx < (int)pool.size()) {
                            const auto &card = pool[pool_idx++];
                            if (is_any_dream) {
                                clear_hand_slot(state, p, i);
                                state.true_hand[p][i] = card.card_id;
                                DreamGroup grp = get_dream_group(card.card_id);
                                if (grp != DreamGroup::NONE) {
                                    state.is_confirmed[p][i] = false;
                                    state.apparent_hand[p][i] = get_fake_dream_card(state, card.card_id);
                                } else {
                                    state.is_confirmed[p][i] = true;
                                    state.apparent_hand[p][i] = card.card_id;
                                }
                            } else {
                                add_card_to_hand_slot(state, p, i, card.card_id, true);
                            }
                            
                            if (card.original_owner != p) {
                                state.is_known_to_opp[p][i] = true;
                            } else {
                                state.is_known_to_opp[p][i] = card.original_known;
                            }
                        }
                    }
                }
            }
            else if (phenomenon == 9) { // 日食: 重複しない守護神割り当て
                int g0 = std::uniform_int_distribution<int>(1, 10)(state.rng);
                int g1 = std::uniform_int_distribution<int>(1, 9)(state.rng);
                if (g1 >= g0) {
                    g1 += 1;
                }
                state.guardian[0] = static_cast<GuardianType>(g0);
                state.guardian[1] = static_cast<GuardianType>(g1);
            }
        }
    }

    state.hp[target_id] = std::clamp(state.hp[target_id] + hp_diff, 0, 99);
    state.mp[target_id] = std::clamp(state.mp[target_id] + mp_diff, 0, 99);

    if (state.hp[target_id] <= 0) {
        state.hp[target_id] = 0;
        state.current_phase = GamePhase::PHASE_END;
    }
}

/**
 * @brief 「売る」アクションにおける商品の引き渡しおよび決済の解決を行います。
 */
void execute_sell_resolution(InternalState &state, int seller, int buyer) {
    // 1. 最初に対象アイテムを売り出したオリジナル売り手を特定する
    // スーパーミラーによる反射が発生している可能性があるため、staged_cards を見て "売る" カードを所持している側を探す
    int original_seller = -1;
    if (state.num_staged_cards[0] > 0 && state.staged_cards[0][0] >= 0 && state.staged_cards[0][0] < MAX_HAND_SIZE && state.true_hand[0][state.staged_cards[0][0]] == ID_SELL) {
        original_seller = 0;
    } else if (state.num_staged_cards[1] > 0 && state.staged_cards[1][0] >= 0 && state.staged_cards[1][0] < MAX_HAND_SIZE && state.true_hand[1][state.staged_cards[1][0]] == ID_SELL) {
        original_seller = 1;
    } else if (state.num_staged_cards[0] >= 2 && state.staged_cards[0][0] == -1 && state.staged_cards[0][1] == ID_SELL) {
        original_seller = 0;
    } else if (state.num_staged_cards[1] >= 2 && state.staged_cards[1][0] == -1 && state.staged_cards[1][1] == ID_SELL) {
        original_seller = 1;
    }
    
    // 見つからなかった場合のセーフティフォールバック
    if (original_seller == -1) {
        original_seller = seller;
    }

    // 2. 売り出したアイテムカードのIDと、その価格を取得する
    // staged_cards[original_seller][1] には売り出すアイテムの手札インデックスが入っている
    int idx = state.staged_cards[original_seller][1];
    int card_id = state.true_hand[original_seller][idx];
    CardFeatures &f_sold = g_card_registry[card_id];
    int price = f_sold.price;

    int remaining_pay = price; // 残りの支払うべき代金
    
    // 3. 買い手の支払いを処理する
    // 優先度 1: 所持金（Money）から支払う
    int money_paid = std::min(state.money[buyer], remaining_pay);
    state.money[buyer] -= money_paid;
    remaining_pay -= money_paid;

    // 優先度 2: 所持金で足りない分を MP から支払う
    if (remaining_pay > 0) {
        int mp_paid = std::min(state.mp[buyer], remaining_pay);
        state.mp[buyer] -= mp_paid;
        remaining_pay -= mp_paid;
    }

    // 優先度 3: 所持金・MPでも足りない分を HP から支払う（HPでの支払いは直接ダメージとなる）
    if (remaining_pay > 0) {
        int hp_paid = std::min(state.hp[buyer], remaining_pay);
        state.hp[buyer] -= hp_paid;
        remaining_pay -= hp_paid;
    }

    // 4. 売り手への売却代金（お金）の支払い（上限は99円）
    state.money[seller] = std::clamp(state.money[seller] + price, 0, 99);
    
    // 売却イベントをログに記録
    push_event(state, original_seller, EventType::SELL_CARD, card_id, buyer, static_cast<float>(price));

    // 5. 売り手の手札から売却したカードを削除し、関連フラグを初期化する
    clear_hand_slot(state, original_seller, idx); 

    // 6. 買い手へ商品を引き渡す
    // 買い手の手札に空きスロットがあるか確認する
    int empty_slot = -1;
    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
        if (state.true_hand[buyer][j] == CARD_EMPTY) {
            empty_slot = j;
            break;
        }
    }

    if (empty_slot != -1) {
        // 空きスロットがある場合はそこに直接格納する（売り手から見えているため is_known_to_opp = true）
        add_card_to_hand_slot(state, buyer, empty_slot, card_id, false);
        state.is_known_to_opp[buyer][empty_slot] = true;
        state.is_used[buyer][empty_slot] = false;
    } else {
        // 手札が満杯の場合は、ランダムに1枚を破棄してそこに上書き格納する（同様に is_known_to_opp = true）
        std::vector<int> candidates;
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (state.true_hand[buyer][j] != CARD_EMPTY) {
                candidates.push_back(j);
            }
        }
        if (!candidates.empty()) {
            std::shuffle(candidates.begin(), candidates.end(), state.rng);
            int replace_idx = candidates[0];
            add_card_to_hand_slot(state, buyer, replace_idx, card_id, false);
            state.is_known_to_opp[buyer][replace_idx] = true;
        }
    }

    // 7. 買い手のHP枯渇によるゲーム終了判定
    if (state.hp[buyer] <= 0) {
        state.hp[buyer] = 0;
        state.num_staged_cards[0] = 0;
        state.num_staged_cards[1] = 0;
        state.current_phase = GamePhase::PHASE_END;
        return;
    }

    // 8. 各種仮置き状態をリセットし、ターン終了処理フェイズへ移行する
    state.num_staged_cards[0] = 0;
    state.num_staged_cards[1] = 0;
    state.current_phase = GamePhase::PHASE_END;
}

/**
 * @brief 相手のアクションに対して「スーパーミラー」での反射を実行し、アクターIDとスロットをスワップします。
 */
bool try_execute_super_mirror_reflection(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        int idx = action - ACTION_SELECT_HAND_0;
        if (state.true_hand[me][idx] == ID_SUPER_MIRROR) {
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
            state.is_known_to_opp[me][idx] = true;
            push_event(state, me, EventType::REFLECT_DAMAGE, ID_SUPER_MIRROR, opp, 0.0f);
            
            std::swap(state.attacker_id, state.defender_id);
            state.current_actor_id = opp;
            return true;
        }
    }
    return false;
}

bool is_active_reaction_card(const InternalState &state, int card_id, GamePhase phase, Element attack_element) {
    if (card_id == CARD_EMPTY) return false;
    if (phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
        const CardFeatures &f = g_card_registry[card_id];
        return (f.reaction_type != REACTION_NONE) && (f.usage_timing & TIMING_MIRACLE_DEFENCE);
    }
    if (phase == GamePhase::PHASE_DEFENSE) {
        if (card_id == ID_SUPER_MIRROR) return true;
        if (attack_element == ELEM_NONE) {
            // 元の攻撃が存在し、かつそれが「武器」である場合のみ反射剣・壁・乱弾武剣を許可
            bool is_weapon_atk = false;
            if (state.pending_attack_source_id != CARD_EMPTY) {
                int src = state.pending_attack_source_id;
                is_weapon_atk = g_card_registry[src].is_weapon() ||
                                 src == ID_GIGANTIC_TUB ||
                                 src == ID_BLACK_HOLE ||
                                 src == ID_DIAMOND_AXE ||
                                 src == ID_FULL_MOON_BLADE;
            }
            if (is_weapon_atk) {
                return (card_id == ID_WALL || card_id == ID_REFLECTION_SWORD || card_id == ID_BOUNCING_SWORD);
            }
        }
    }
    return false;
}

std::pair<int, int> get_exchange_hp_range(int sum) {
    int hp_min = std::max(0, sum - 198);
    int hp_max = std::min(99, sum);
    return {hp_min, hp_max};
}

std::pair<int, int> get_exchange_mp_range(int sum, int hp) {
    int mp_min = std::max(0, sum - hp - 99);
    int mp_max = std::min(99, sum - hp);
    return {mp_min, mp_max};
}

void apply_defense_gear_effects(InternalState &state, int player_id) {
    int num_fever_masks = 0;
    bool has_dreaming_hat = false;

    for (int i = 0; i < state.num_staged_cards[player_id]; ++i) {
        int h_idx = state.staged_cards[player_id][i];
        int card_id = state.true_hand[player_id][h_idx];
        if (card_id == ID_FEVER_MASK) {
            num_fever_masks++;
        } else if (card_id == ID_DREAMING_HAT) {
            has_dreaming_hat = true;
        }
    }

    for (int f = 0; f < num_fever_masks; ++f) {
        apply_sickness(state, player_id, SICKNESS_FEVER);
    }

    if (has_dreaming_hat) {
        state.curses[player_id][CURSE_TYPE_DREAM] = true;
        bool is_staged[MAX_HAND_SIZE] = {false};
        for (int k = 0; k < state.num_staged_cards[player_id]; ++k) {
            is_staged[state.staged_cards[player_id][k]] = true;
        }
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (!is_staged[j]) {
                if (state.true_hand[player_id][j] != CARD_EMPTY || state.is_deployed[player_id][j]) {
                    clear_hand_slot(state, player_id, j);
                    state.is_used[player_id][j] = true;
                }
            }
        }
    }
}

bool run_immediate_revive(InternalState &state) {
    bool revived = false;
    for (int p = 0; p < 2; ++p) {
        if (state.hp[p] == 0) {
            int amulet_slot = -1;
            for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                if (state.true_hand[p][i] == ID_SUN_AMULET) {
                    amulet_slot = i;
                    break;
                }
            }
            if (amulet_slot != -1) {
                state.hp[p] = 10;
                clear_hand_slot(state, p, amulet_slot);
                state.is_used[p][amulet_slot] = true;
                state.is_known_to_opp[p][amulet_slot] = true;
                revived = true;
            }
        }
    }
    if (revived) {
        run_immediate_revive(state);
    }
    return revived;
}

bool run_death_check(InternalState &state) {
    // 0. 両者死亡していて、どちらも太陽のお守りを持っていない場合は、即座に引き分け終了
    if (state.hp[0] == 0 && state.hp[1] == 0) {
        bool has_amulet[2] = {false, false};
        for (int p = 0; p < 2; ++p) {
            for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                if (state.true_hand[p][i] == ID_SUN_AMULET) {
                    has_amulet[p] = true;
                    break;
                }
            }
        }
        if (!has_amulet[0] && !has_amulet[1]) {
            if (state.remaining_attacks > 0) return false;
            state.is_done = true;
            state.p0_reward = 0.0f;
            state.p1_reward = 0.0f;
            return false;
        }
    }

    // 1. 各プレイヤーについて、もし保留中の昇天弓があるなら、そのうちの1つを発射する
    for (int p = 0; p < 2; ++p) {
        while (state.pending_ascension_bows[p] > 0) {
            state.pending_ascension_bows[p]--;
            int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
            if (roll < 75) {
                state.current_phase = GamePhase::PHASE_DEFENSE;
                state.attacker_id = p;
                state.defender_id = 1 - p;
                state.current_actor_id = 1 - p;
                state.num_staged_cards[1 - p] = 0; // 防御側の仮置き場をクリア
                state.pending_attack_power = 30;
                state.pending_attack_element = ELEM_LIGHT;
                state.pending_absorption = false;
                state.pending_deal_same_damage = false;
                state.pending_is_group_attack = false;
                state.pending_attack_source_id = ID_ASCENSION_BOW;
                return true; // 防御フェイズへ移行するため一時中断
            }
            // 命中しなかった場合はwhileにより次の保留中の弓を処理
        }
    }

    // 2. HPが0のプレイヤーに対して、太陽のお守りによる復活、または昇天弓のキューイングを行う
    for (int p = 0; p < 2; ++p) {
        if (state.hp[p] == 0) {
            // 太陽のお守りを探す
            int amulet_slot = -1;
            for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                if (state.true_hand[p][i] == ID_SUN_AMULET) {
                    amulet_slot = i;
                    break;
                }
            }
            if (amulet_slot != -1) {
                // 復活！
                state.hp[p] = 10;
                clear_hand_slot(state, p, amulet_slot);
                state.is_used[p][amulet_slot] = true;
                state.is_known_to_opp[p][amulet_slot] = true;
                // 復活したので、再チェックするために再帰呼び出し
                return run_death_check(state);
            }

            // 昇天弓を探す
            int bow_count = 0;
            std::vector<int> bow_slots;
            for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                if (state.true_hand[p][i] == ID_ASCENSION_BOW) {
                    bow_count++;
                    bow_slots.push_back(i);
                }
            }
            if (bow_count > 0) {
                state.pending_ascension_bows[p] = bow_count;
                for (int slot : bow_slots) {
                    clear_hand_slot(state, p, slot);
                    state.is_used[p][slot] = true;
                    state.is_known_to_opp[p][slot] = true;
                }
                // キューイング完了したので、最初の1発を撃つために再帰呼び出し
                return run_death_check(state);
            }
        }
    }

    // 3. 復活やお守り・弓がすべて終了した時点で、依然として死亡しているプレイヤーがあるか確認
    int active = state.current_actor_id;
    int passive = 1 - active;

    if (state.hp[0] == 0 && state.hp[1] == 0) {
        if (state.remaining_attacks > 0) return false;
        state.is_done = true;
        state.p0_reward = 0.0f;
        state.p1_reward = 0.0f;
        return false;
    }
    
    if (state.hp[active] == 0) {
        if (state.remaining_attacks > 0) return false;
        // 手番プレイヤーが死亡した場合は即座にゲーム終了（待機プレイヤーの勝利）
        state.is_done = true;
        state.p0_reward = (passive == 0) ? 1.0f : -1.0f;
        state.p1_reward = (passive == 1) ? 1.0f : -1.0f;
        return false;
    }
    
    if (state.hp[passive] == 0) {
        // もしターンエンドの病気解決（State 3）に達していないなら、まだ終了させず、
        // 手番プレイヤーの病気ダメージ（State 1, 2）を解決させるためスルーする。
        if (state.turn_end_state < 3) {
            return false;
        }
        if (state.remaining_attacks > 0) return false;
        state.is_done = true;
        state.p0_reward = (active == 0) ? 1.0f : -1.0f;
        state.p1_reward = (active == 1) ? 1.0f : -1.0f;
        return false;
    }

    return false;
}

static bool setup_guardian_attack_defense(InternalState &state, int attacker, int defender, int source_id, GamePhase phase, bool absorption = false, int override_power = -1) {
    const CardFeatures &feat = g_card_registry[source_id];

    // 命中率（accuracy）チェック。暗雲がかかっていない場合で確率計算
    if (feat.accuracy < 100 && !state.curses[defender][CURSE_TYPE_DARK_CLOUD]) {
        std::uniform_int_distribution<int> dist(0, 99);
        if (dist(state.rng) >= feat.accuracy) {
            state.turn_end_state = 5;
            return false; // ミス：防御フェイズを起動せず終了
        }
    }

    state.pending_attack_source_id = source_id;
    state.pending_attack_curse = feat.hit_curse;
    
    if (feat.type == CardType::GUARDIAN && (source_id == ID_FINE || source_id == ID_BRIBE || (feat.attack_power == 0 && feat.hit_curse != CURSE_NONE))) {
        state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
    } else {
        state.current_phase = phase;
    }
    state.attacker_id = attacker;
    state.defender_id = defender;
    state.current_actor_id = defender;
    state.pending_attack_power = (override_power != -1) ? override_power : feat.attack_power;
    state.pending_attack_element = feat.element;
    state.pending_absorption = absorption;
    state.pending_deal_same_damage = false;
    state.pending_is_group_attack = feat.is_group_attack;
    state.turn_end_state = 5;
    return true;
}

bool execute_dangerous_pestle(InternalState &state, int attacker, int defender, bool is_guardian) {
    int count_attacker = 0;
    int count_defender = 0;
    if (state.hp[attacker] > 0) {
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (state.true_hand[attacker][j] == ID_DANGEROUS_MORTAR && !state.is_used[attacker][j]) {
                count_attacker++;
            }
        }
    }
    if (state.hp[defender] > 0) {
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (state.true_hand[defender][j] == ID_DANGEROUS_MORTAR && !state.is_used[defender][j]) {
                count_defender++;
            }
        }
    }
    int total_mortars = count_attacker + count_defender;

    if (total_mortars > 0) {
        // パターンB: ウスが存在する場合 (99被弾、1枚消費)
        int r = std::uniform_int_distribution<int>(0, total_mortars - 1)(state.rng);
        int victim = (r < count_attacker) ? attacker : defender;

        state.hp[victim] = std::clamp(state.hp[victim] - 99, 0, 99);
        for (int j = 0; j < MAX_HAND_SIZE; ++j) {
            if (state.true_hand[victim][j] == ID_DANGEROUS_MORTAR && !state.is_used[victim][j]) {
                state.is_used[victim][j] = true;
                break;
            }
        }
        run_death_check(state);
        state.current_phase = GamePhase::PHASE_END;
        if (is_guardian) state.turn_end_state = 5;
        return true;
    } else {
        // パターンA: ウスが存在しない場合 (生存プレイヤーからランダム選定)
        std::vector<int> alive_players;
        if (state.hp[attacker] > 0) alive_players.push_back(attacker);
        if (state.hp[defender] > 0) alive_players.push_back(defender);

        int actual_target = attacker;
        if (!alive_players.empty()) {
            int r = std::uniform_int_distribution<int>(0, alive_players.size() - 1)(state.rng);
            actual_target = alive_players[r];
        }

        if (actual_target == attacker) {
            // 自傷：直撃ダメージ
            state.hp[attacker] = std::clamp(state.hp[attacker] - 30, 0, 99);
            run_death_check(state);
            state.current_phase = GamePhase::PHASE_END;
            if (is_guardian) state.turn_end_state = 5;
            return true;
        } else {
            // 相手ターゲット：物理防御フェイズ起動
            bool ok = setup_guardian_attack_defense(state, attacker, defender, ID_DANGEROUS_PESTLE, GamePhase::PHASE_DEFENSE);
            if (!ok) {
                state.current_phase = GamePhase::PHASE_END;
                if (is_guardian) state.turn_end_state = 5;
            }
            return true;
        }
    }
}

bool execute_attack_from_staged_cards(InternalState &state, int attacker, int target, bool is_guardian) {
    auto used_cards = get_staged_card_ids(state, attacker);

    // あぶないキネの特別判定
    bool has_pestle = false;
    for (int cid : used_cards) {
        if (cid == ID_DANGEROUS_PESTLE) {
            has_pestle = true;
            break;
        }
    }
    if (has_pestle) {
        return execute_dangerous_pestle(state, attacker, target, is_guardian);
    }

    // 攻撃の評価 (MP消費、攻撃力、属性、命中率)
    StagedAttackInfo info = evaluate_staged_attack(state, attacker);
    if (!is_guardian) {
        state.mp[attacker] = std::clamp(state.mp[attacker] - info.mp_cost, 0, 99);
    }

    if (!info.hit) {
        // ミス：防御フェイズを起動せず終了
        state.current_phase = GamePhase::PHASE_END;
        if (is_guardian) state.turn_end_state = 5;
        return true;
    }

    if (!is_guardian) {
        setup_multiple_attacks(state, attacker, target, info);
    }

    state.pending_attack_power = info.attack_power;
    state.pending_attack_element = info.element;
    state.pending_absorption = info.absorption;
    state.pending_deal_same_damage = info.deal_same_damage;
    state.defender_id = target;

    int first_card_id = !used_cards.empty() ? used_cards[0] : CARD_EMPTY;
    state.pending_attack_source_id = first_card_id;
    state.pending_attack_curse = (first_card_id != CARD_EMPTY) ? g_card_registry[first_card_id].hit_curse : CURSE_NONE;

    if (target == attacker) {
        // 自傷解決
        int times = state.remaining_attacks;
        if (times <= 0) times = 1;
        for (int t = 0; t < times; ++t) {
            if (info.attack_power > 0) {
                int intended_damage = info.attack_power;
                state.hp[attacker] = std::clamp(state.hp[attacker] - info.attack_power, 0, 99);
                if (state.pending_absorption) {
                    state.hp[attacker] = std::clamp(state.hp[attacker] + intended_damage, 0, 99);
                }
                run_immediate_revive(state);
                if (state.pending_deal_same_damage) {
                    state.hp[attacker] = std::clamp(state.hp[attacker] - intended_damage, 0, 99);
                    run_immediate_revive(state);
                }
            }
            apply_card_effects_to_target(state, attacker, used_cards);
            if (state.pending_attack_curse != CURSE_NONE) {
                apply_curse_to_player(state, attacker, state.pending_attack_curse);
            }
        }
        state.remaining_attacks = 0;
        run_death_check(state);
        state.current_phase = GamePhase::PHASE_END;
        if (is_guardian) state.turn_end_state = 5;
    } else {
        // 相手ターゲット：防御フェイズへ移行
        state.attacker_id = attacker;
        state.current_actor_id = target;
        
        bool is_group_weapon = (!used_cards.empty() && g_card_registry[used_cards[0]].is_group_attack);
        bool is_mirage = false;
        for (int cid : used_cards) {
            if (cid == ID_MIRAGE) {
                is_mirage = true;
                break;
            }
        }
        if (is_group_weapon || is_mirage) {
            state.pending_is_group_attack = true;
        }
        if (is_mirage || (info.element == ELEM_NONE && is_group_weapon)) {
            state.current_phase = is_guardian ? GamePhase::PHASE_DEFENSE : GamePhase::PHASE_GROUP_WEAPON;
        } else {
            state.current_phase = GamePhase::PHASE_DEFENSE;
        }
        if (is_guardian) state.turn_end_state = 5;
    }
    return true;
}

bool resolve_turn_end_steps(InternalState &state) {
    bool is_apocalypse = (state.current_turn >= APOCALYPSE_TURN);
    while (state.current_phase == GamePhase::PHASE_END && !state.is_done) {
        switch (state.turn_end_state) {
            case 0: { // 死亡・お守り・昇天弓の判定
                if (!is_apocalypse) {
                    bool paused = run_death_check(state);
                    if (paused) return true; // 防御フェイズへ移行のため一時中断
                }
                state.turn_end_state = 1;
                break;
            }
            case 1: { // 病気悪化判定
                int me = state.current_actor_id;
                if (state.hp[me] > 0 && state.sickness[me] != SICKNESS_NONE) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < 5) {
                        if (state.sickness[me] == SICKNESS_HEAVEN) { // 天国病悪化 -> 死亡 (発作)
                            state.hp[me] = 0;
                            state.heaven_seizure_occurred[me] = true;
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, 4.0f);
                        } else if (state.sickness[me] == SICKNESS_COLD) { // 風邪 -> 熱病
                            state.sickness[me] = SICKNESS_FEVER;
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, 2.0f);
                        } else if (state.sickness[me] == SICKNESS_FEVER) { // 熱病 -> 地獄病
                            state.sickness[me] = SICKNESS_HELL;
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, 3.0f);
                        } else if (state.sickness[me] == SICKNESS_HELL) { // 地獄病 -> 天国病
                            state.sickness[me] = SICKNESS_HEAVEN;
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, 4.0f);
                        }
                    }
                }
                // 悪化によって死亡したプレイヤーがいるかチェック
                if (state.hp[me] == 0) {
                    if (!is_apocalypse) {
                        bool paused = run_death_check(state);
                        if (paused) return true;
                    }
                }
                state.turn_end_state = 2;
                break;
            }
            case 2: { // 病気ダメージ・回復処理
                int me = state.current_actor_id;
                int hp_before = state.hp[me];
                if (state.hp[me] > 0) {
                    if (state.sickness[me] == SICKNESS_COLD) { // 風邪: 1ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 1);
                        push_event(state, me, EventType::TAKE_DAMAGE, -1, me, 1.0f);
                    } else if (state.sickness[me] == SICKNESS_FEVER) { // 熱病: 2ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 2);
                        push_event(state, me, EventType::TAKE_DAMAGE, -1, me, 2.0f);
                    } else if (state.sickness[me] == SICKNESS_HELL) { // 地獄病: 5ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 5);
                        push_event(state, me, EventType::TAKE_DAMAGE, -1, me, 5.0f);
                    } else if (state.sickness[me] == SICKNESS_HEAVEN) { // 天国病: 5回復
                        if (!state.heaven_seizure_occurred[me]) {
                            state.hp[me] = std::min(99, state.hp[me] + 5);
                            push_event(state, me, EventType::HEAL_HP, -1, me, 5.0f);
                        }
                    }
                }
                // 被病気ダメージによる守護神退散（天国病回復は対象外）
                if (state.hp[me] < hp_before && state.guardian[me] > GUARDIAN_NONE) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < 10) {
                        state.guardian[me] = GUARDIAN_NONE;
                    }
                }
                // ダメージによって死亡したプレイヤーがあるかチェック
                if (state.hp[me] == 0) {
                    if (!is_apocalypse) {
                        bool paused = run_death_check(state);
                        if (paused) return true;
                    }
                }
                state.turn_end_state = 3;
                break;
            }
            case 3: { // 引き分け/勝敗の最終確定
                if (!is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused) return true;
                    }
                }
                state.turn_end_state = 4;
                break;
            }
            case 4: { // 相手の守護神の行動
                int opp = 1 - state.current_actor_id; // 次にターンが回る相手
                int me = state.current_actor_id;     // 現在手番が終了した側
                state.num_staged_cards[me] = 0;      // 被攻撃に備えて仮置き場をクリア
                
                if (state.hp[opp] > 0 && state.guardian[opp] > GUARDIAN_NONE) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < 25) { // 25%の確率で行動
                        int roll_act = std::uniform_int_distribution<int>(0, 99)(state.rng);
                        int act_idx = 0;
                        if (roll_act < 30) act_idx = 1;
                        else if (roll_act < 55) act_idx = 2;
                        else if (roll_act < 75) act_idx = 3;
                        else if (roll_act < 90) act_idx = 4;
                        else act_idx = 5;

                        GuardianType g_id = state.guardian[opp];
                        
                        if (g_id == GUARDIAN_MARS) { // 火星神
                            int source_id = (act_idx == 1) ? ID_FIRE_SHOUT :
                                            (act_idx == 2) ? ID_FIRE_ROAR :
                                            (act_idx == 3) ? ID_FIRE_BUZZ :
                                            (act_idx == 4) ? ID_FIRE_TWEET : ID_FIRE_WHISPER;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, false);
                        }
                        else if (g_id == GUARDIAN_MERCURY) { // 水星神
                            int source_id = (act_idx == 1) ? ID_HAIL :
                                            (act_idx == 2) ? ID_SPLASH :
                                            (act_idx == 3) ? ID_BUBBLES :
                                            (act_idx == 4) ? ID_MISTY_BREATH : ID_DRIZZLE;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, false);
                        }
                        else if (g_id == GUARDIAN_JUPITER) { // 木星神
                            int source_id = (act_idx == 1) ? ID_DANCE_OF_FALLEN_LEAVES :
                                            (act_idx == 2) ? ID_COLORED_LEAVES :
                                            (act_idx == 3) ? ID_TENTACLES :
                                            (act_idx == 4) ? ID_ROOT : ID_BRANCH;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, (source_id == ID_TENTACLES));
                        }
                        else if (g_id == GUARDIAN_SATURN) { // 土星神
                            int source_id = (act_idx == 1) ? ID_BOULDER :
                                            (act_idx == 2) ? ID_STONE :
                                            (act_idx == 3) ? ID_PEBBLE :
                                            (act_idx == 4) ? ID_BODY_PRESS : ID_DIAMOND_AXE;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, false);
                        }
                        else if (g_id == GUARDIAN_URANUS) { // 天王神
                            int source_id = (act_idx == 1) ? ID_LASER_BEAM :
                                            (act_idx == 2) ? ID_HALO :
                                            (act_idx == 3) ? ID_BLESSING :
                                            (act_idx == 4) ? ID_ELECTRIC_SHOCK : ID_TWINKLE;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, (source_id == ID_BLESSING));
                        }
                        else if (g_id == GUARDIAN_PLUTO) { // 冥王神
                            int source_id = (act_idx == 1) ? ID_WINK :
                                            (act_idx == 2) ? ID_THINKING :
                                            (act_idx == 3) ? ID_OMINOUS_PREMONITION :
                                            (act_idx == 4) ? ID_COUGH : ID_HAND_RAISING;
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE, false);
                        }
                        else if (g_id == GUARDIAN_NEPTUNE) { // 海王神
                            int source_id = CARD_EMPTY;
                            if (act_idx == 1) { state.hp[opp] = std::min(99, state.hp[opp] + 10); source_id = ID_HEALTHY_SEAFOOD_SOUP; }
                            else if (act_idx == 2) { state.hp[opp] = std::min(99, state.hp[opp] + 5); source_id = ID_SEAFOOD_SOUP; }
                            else if (act_idx == 3) { state.mp[opp] = std::min(99, state.mp[opp] + 10); source_id = ID_FRESH_BEACH_AROMA; }
                            else if (act_idx == 4) { state.mp[opp] = std::min(99, state.mp[opp] + 5); source_id = ID_BEACH_AROMA; }
                            else {
                                clear_all_status_effects(state, opp);
                                source_id = ID_SOUND_OF_RIPPLES;
                            }
                            state.pending_attack_source_id = source_id;
                        }
                        else if (g_id == GUARDIAN_VENUS) { // 金星神
                            int source_id = CARD_EMPTY;
                            if (act_idx == 1) { 
                                // お互いお金+1
                                state.money[0] = std::min(99, state.money[0] + 1);
                                state.money[1] = std::min(99, state.money[1] + 1);
                                source_id = ID_COIN_SCATTERING; 
                            }
                            else if (act_idx == 2) { 
                                // 自分(opp)にお金+20
                                state.money[opp] = std::min(99, state.money[opp] + 20);
                                source_id = ID_LUXURY_ACCESSORY; 
                            }
                            else if (act_idx == 3) { 
                                // わいろ (相手にお金+5、反射可能)
                                return setup_guardian_attack_defense(state, opp, me, ID_BRIBE, GamePhase::PHASE_DEFENSE, false, 5);
                            }
                            else if (act_idx == 4) { 
                                // 自分(opp)にお金+8
                                state.money[opp] = std::min(99, state.money[opp] + 8);
                                source_id = ID_LITTLE_SOMETHING; 
                            }
                            else { 
                                // 罰金 (没収3、反射可能)
                                return setup_guardian_attack_defense(state, opp, me, ID_FINE, GamePhase::PHASE_DEFENSE, false, 3);
                            }
                            
                            state.pending_attack_source_id = source_id;
                        }

                        else if (g_id == GUARDIAN_EARTH) { // 地球神
                            int drawn_card_id = draw_card_with_apocalypse(state, opp);
                            if (drawn_card_id != CARD_EMPTY) {
                                const CardFeatures &feat = g_card_registry[drawn_card_id];

                                // 1. 防具、奇跡、またはメインで使用できない雑貨 ➡ 手札に加わる
                                bool is_passive_sundry = feat.is_sundry() && !(feat.usage_timing & TIMING_MAIN_SUNDRY);
                                if (feat.is_defense() || feat.is_miracle() || is_passive_sundry) {
                                    int empty_slot = -1;
                                    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                                        if (state.true_hand[opp][i] == CARD_EMPTY) {
                                            empty_slot = i;
                                            break;
                                        }
                                    }
                                    if (empty_slot != -1) {
                                        add_card_to_hand_slot(state, opp, empty_slot, drawn_card_id, true);
                                        state.is_known_to_opp[opp][empty_slot] = false;
                                        state.is_used[opp][empty_slot] = false;
                                    } else {
                                        std::vector<int> candidates;
                                        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                                            if (!state.is_used[opp][i]) {
                                                candidates.push_back(i);
                                            }
                                        }
                                        if (!candidates.empty()) {
                                            int rand_idx = std::uniform_int_distribution<int>(0, candidates.size() - 1)(state.rng);
                                            int discard_slot = candidates[rand_idx];
                                            add_card_to_hand_slot(state, opp, discard_slot, drawn_card_id, true);
                                            state.is_known_to_opp[opp][discard_slot] = false;
                                            state.is_used[opp][discard_slot] = false;
                                        }
                                    }
                                    state.turn_end_state = 5;
                                }
                                // 2. 両替 (ID_EXCHANGE) ➡ 自分に使う
                                else if (drawn_card_id == ID_EXCHANGE) {
                                    int sum = state.hp[opp] + state.mp[opp] + state.money[opp];
                                    auto hp_range = get_exchange_hp_range(sum);
                                    if (hp_range.first <= hp_range.second) {
                                        int chosen_hp = std::uniform_int_distribution<int>(hp_range.first, hp_range.second)(state.rng);
                                        auto mp_range = get_exchange_mp_range(sum, chosen_hp);
                                        if (mp_range.first <= mp_range.second) {
                                            int chosen_mp = std::uniform_int_distribution<int>(mp_range.first, mp_range.second)(state.rng);
                                            state.hp[opp] = chosen_hp;
                                            state.mp[opp] = chosen_mp;
                                            state.money[opp] = sum - chosen_hp - chosen_mp;
                                        }
                                    }
                                    if (state.hp[opp] == 0) {
                                        run_death_check(state);
                                    }
                                    state.turn_end_state = 5;
                                }
                                // 3. 売る (ID_SELL) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_SELL) {
                                    if (can_sell_card(state, opp, -1)) {
                                        std::vector<int> sell_candidates;
                                        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                                            if (is_sellable_card(state, opp, i)) {
                                                sell_candidates.push_back(i);
                                            }
                                        }
                                        int rand_idx = std::uniform_int_distribution<int>(0, sell_candidates.size() - 1)(state.rng);
                                        int sell_slot = sell_candidates[rand_idx];
                                        
                                        state.attacker_id = opp;
                                        state.defender_id = me;
                                        state.current_actor_id = me;
                                        state.staged_cards[opp][0] = -1; // 地球神フラグ
                                        state.staged_cards[opp][1] = sell_slot;
                                        state.num_staged_cards[opp] = 2;
                                        state.current_phase = GamePhase::PHASE_SELL_SELECT_MIRROR;
                                        state.turn_end_state = 5;
                                        return true;
                                    }
                                    state.turn_end_state = 5;
                                }
                                // 4. 買う (ID_BUY) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_BUY) {
                                    state.attacker_id = opp;
                                    state.defender_id = me;
                                    state.current_actor_id = me;
                                    state.staged_cards[opp][0] = -1; // 地球神フラグ
                                    state.num_staged_cards[opp] = 1;
                                    state.current_phase = GamePhase::PHASE_BUY_SELECT_MIRROR;
                                    state.turn_end_state = 5;
                                    return true;
                                }
                                // 5. 武器 ➡ 対戦相手に使う
                                else if (feat.is_weapon()) {
                                    state.staged_cards[opp][0] = -1; // 地球神仮想仮想フラグ
                                    state.staged_cards[opp][1] = drawn_card_id;
                                    state.num_staged_cards[opp] = 2;
                                    return execute_attack_from_staged_cards(state, opp, me, true);
                                }
                                // 6. 夜空のホウキ (ID_NOCTURNAL_BROOM) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_NOCTURNAL_BROOM) {
                                    apply_card_effects_to_target(state, me, {drawn_card_id});
                                    state.turn_end_state = 5;
                                }
                                // 7. 女神の石けん (ID_GODDESS_S_SOAP) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_GODDESS_S_SOAP) {
                                    apply_card_effects_to_target(state, me, {drawn_card_id});
                                    state.turn_end_state = 5;
                                }
                                // 8. その他の雑貨 ➡ 自分に使う
                                else {
                                    apply_card_effects_to_target(state, opp, {drawn_card_id});
                                    if (state.current_phase == GamePhase::PHASE_DEFENSE || state.current_phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
                                        state.turn_end_state = 5;
                                        return true;
                                    }
                                    state.turn_end_state = 5;
                                }
                            } else {
                                state.turn_end_state = 5;
                            }
                        }
                        else if (g_id == GUARDIAN_MOON) { // 月神
                            // 28種類の奇跡（壁 ID_WALL と 乱気流 ID_TURBULENCE を除く）
                            const std::vector<int> MOON_MIRACLES = {
                                ID_FIREBALL, ID_ICE, ID_DARKNESS, ID_BIG_TREE, ID_ROCK, ID_FLAME, ID_ABSORPTION,
                                ID_METEOR, ID_WATERFALL, ID_WIND, ID_HEAVEN_WIND, ID_FOG, ID_DREAM, ID_DARK_CLOUD,
                                ID_FLASH, ID_SMOKE, ID_AVALANCHE, ID_THUNDER, ID_MUDFLOW, ID_MAGMA, ID_ICE_AGE,
                                ID_AURA, ID_MIRAGE, ID_SPRING, ID_TREASURE, ID_TONE, ID_SONG, ID_RELEASE
                            };
                            int rand_idx = std::uniform_int_distribution<int>(0, MOON_MIRACLES.size() - 1)(state.rng);
                            int chosen_miracle = MOON_MIRACLES[rand_idx];

                            if (chosen_miracle == ID_AURA) { // オーラ + 満月刀 (物理ATK20)
                                return setup_guardian_attack_defense(state, opp, me, ID_FULL_MOON_BLADE, GamePhase::PHASE_DEFENSE, false, 20);
                            }
                            else if (chosen_miracle == ID_MIRAGE) { // 蜃気楼 + 満月刀 (物理ATK10 全体)
                                setup_guardian_attack_defense(state, opp, me, ID_FULL_MOON_BLADE, GamePhase::PHASE_DEFENSE, false, 10);
                                state.pending_is_group_attack = true; // 全体攻撃
                                return true;
                            }
                            else if (chosen_miracle == ID_TONE || chosen_miracle == ID_SONG ||
                                     chosen_miracle == ID_RELEASE || chosen_miracle == ID_SPRING ||
                                     chosen_miracle == ID_TREASURE) {
                                apply_card_effects_to_target(state, opp, {chosen_miracle});
                                state.turn_end_state = 5;
                            }
                            else { // その他奇跡攻撃 21種類: 奇跡防御フェイズ起動
                                return setup_guardian_attack_defense(state, opp, me, chosen_miracle, GamePhase::PHASE_MIRACLE_DEFENSE, (chosen_miracle == ID_ABSORPTION));
                            }
                        }
                    }
                }
                state.turn_end_state = 5;
                break;
            }
            case 5: { // クリーンアップおよびターン移行
                bool is_apocalypse = (state.current_turn >= APOCALYPSE_TURN);

                if (!is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused || state.is_done) return true;
                    }
                }

                cleanup_phase_end(state);

                if (is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused || state.is_done) return true;
                    }
                }

                state.turn_end_state = 0;
                state.heaven_seizure_occurred[0] = false;
                state.heaven_seizure_occurred[1] = false;
                state.current_turn++;
                if (state.mushroom_turns > 0) {
                    state.mushroom_turns--;
                }
                state.current_actor_id = state.current_turn % 2;
                state.current_phase = GamePhase::PHASE_MAIN;
                return false;
            }
        }
    }
    return false;
}
