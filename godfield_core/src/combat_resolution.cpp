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
}

void undeploy_miracle(InternalState &state, int player_id, int slot_idx) {
    if (!state.is_deployed[player_id][slot_idx]) {
        return;
    }
    state.is_deployed[player_id][slot_idx] = false;
}

void clear_hand_slot(InternalState &state, int player_id, int slot_idx) {
    state.true_hand[player_id][slot_idx] = CARD_EMPTY;
    state.apparent_hand[player_id][slot_idx] = CARD_EMPTY;
    state.is_confirmed[player_id][slot_idx] = true;
    state.is_known_to_opp[player_id][slot_idx] = false;
    state.is_used[player_id][slot_idx] = false;
    undeploy_miracle(state, player_id, slot_idx);
}

/**
 * @brief 保留中の攻撃パラメータ（pending_attack_* 一式）をまとめて設定します。
 *
 * これらのフィールドを個別に代入すると、指定し忘れたものが直前の攻撃の値を持ち越します
 * （実際に昇天弓が前の攻撃の状態異常を引き継ぐ不具合が発生していました）。
 * それを構造的に防ぐため、呼び出し側が渡さないフィールドも必ず既定値で上書きします。
 *
 * フェイズ遷移・攻守の割り当て・ターン終了サブステップは呼び出し箇所ごとに異なるため、
 * ここでは扱わず呼び出し側の責務とします。
 */
static void set_pending_attack(InternalState &state, int source_id, int power, Element element,
                               bool is_group, bool absorption = false,
                               HitCurse curse = CURSE_NONE, bool deal_same_damage = false,
                               bool take_cp = false) {
    state.pending_attack_source_id = source_id;
    state.pending_attack_power = power;
    state.pending_attack_element = element;
    state.pending_is_group_attack = is_group;
    state.pending_absorption = absorption;
    state.pending_attack_curse = curse;
    state.pending_deal_same_damage = deal_same_damage;
    state.pending_take_cp = take_cp;
}

/**
 * @brief HPを増減させます（0〜99にクランプ）。負の値を渡すと減少します。
 */
static void add_hp(InternalState &state, int player_id, int amount) {
    state.hp[player_id] = std::clamp(state.hp[player_id] + amount, 0, 99);
}

/**
 * @brief MPを増減させます（0〜99にクランプ）。
 */
static void add_mp(InternalState &state, int player_id, int amount) {
    state.mp[player_id] = std::clamp(state.mp[player_id] + amount, 0, 99);
}

/**
 * @brief 所持金を増減させます（0〜99にクランプ）。
 */
static void add_money(InternalState &state, int player_id, int amount) {
    state.money[player_id] = std::clamp(state.money[player_id] + amount, 0, 99);
}

/**
 * @brief 対象プレイヤーの手札からランダムに最大 count 枚を破棄します。
 * @param deployed_only true なら展開済みの奇跡のみ、false なら未使用かつ未展開のカードのみを対象にします。
 */
static void discard_random_cards(InternalState &state, int player_id, int count, bool deployed_only) {
    std::vector<int> candidates;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] == CARD_EMPTY) continue;
        bool matches = deployed_only
                           ? state.is_deployed[player_id][i]
                           : (!state.is_deployed[player_id][i] && !state.is_used[player_id][i]);
        if (matches) {
            candidates.push_back(i);
        }
    }
    if (candidates.empty()) return;

    std::shuffle(candidates.begin(), candidates.end(), state.rng);
    int num_to_discard = std::min(count, static_cast<int>(candidates.size()));
    for (int k = 0; k < num_to_discard; ++k) {
        clear_hand_slot(state, player_id, candidates[k]);
    }
}

/**
 * @brief 守護神を入れ替え、対応するイベントを発行します。
 *
 * 既に守護神が就いていれば GUARDIAN_LEAVE を、新たに就く守護神があれば GUARDIAN_ENTER を発行します。
 * GUARDIAN_NONE を渡すと離脱のみを行います。同じ守護神を渡した場合も離脱→登場として扱います。
 */
static void change_guardian(InternalState &state, int player_id, GuardianType new_guardian) {
    if (state.guardian[player_id] > GUARDIAN_NONE) {
        push_event(state, player_id, EventType::GUARDIAN_LEAVE, -1, -1,
                   static_cast<float>(state.guardian[player_id]));
    }
    state.guardian[player_id] = new_guardian;
    if (new_guardian > GUARDIAN_NONE) {
        push_event(state, player_id, EventType::GUARDIAN_ENTER, -1, -1,
                   static_cast<float>(new_guardian));
    }
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
        remove_curse(state, player_id, static_cast<CurseType>(j));
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
            int slot = temp.staged_cards[player_id][i];
            // 守護神由来の仮置きは番兵 -1 を置くため、手札スロットとして使う前に範囲を検査する
            if (slot >= 0 && slot < MAX_HAND_SIZE) {
                is_staged[slot] = true;
            }
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
    apply_damage(state, player_id, 10);
}

void apply_devil_medium(InternalState &state, int player_id) {
    apply_damage(state, player_id, 20);
}

void apply_devil_large(InternalState &state, int player_id) {
    apply_damage(state, player_id, 30);
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
                return CARD_EMPTY;
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
StagedCardIds get_staged_card_ids(const InternalState &state, int player) {
    StagedCardIds result;
    for (int i = 0; i < state.num_staged_cards[player]; ++i) {
        int idx = state.staged_cards[player][i];
        if (idx >= 0 && idx < MAX_HAND_SIZE) {
            int card_id = state.apparent_hand[player][idx];
            if (card_id < 0) card_id = state.true_hand[player][idx];
            result.ids[result.count++] = card_id;
        }
    }
    return result;
}

// Note: Sickness/Curse status values and event flags (such as FLAG_WORSENED)
// are bitwise OR-ed and packed into the float `value` field of GameEvent
// to keep the observation representation uniform for RL neural network input.
void apply_sickness(InternalState &state, int player_id, SicknessType new_sick) {
    if (new_sick <= SICKNESS_NONE) return;
    SicknessType cur_sick = state.sickness[player_id];
    if (cur_sick == SICKNESS_NONE) {
        state.sickness[player_id] = new_sick;
        push_event(state, player_id, EventType::EFFECT_SICKNESS, -1, player_id,
                   static_cast<float>(static_cast<int>(new_sick) | SicknessEvent::FLAG_WORSENED));
    } else {
        SicknessType target_sick;
        if (new_sick > cur_sick) {
            target_sick = new_sick;
        } else {
            if (cur_sick == SICKNESS_HEAVEN) {
                state.hp[player_id] = 0;
                push_event(state, player_id, EventType::EFFECT_SICKNESS, -1, player_id,
                           static_cast<float>(SicknessEvent::TYPE_HEAVEN | SicknessEvent::FLAG_SEIZURE));
                return;
            } else {
                target_sick = static_cast<SicknessType>(cur_sick + 1);
            }
        }
        state.sickness[player_id] = target_sick;
        push_event(state, player_id, EventType::EFFECT_SICKNESS, -1, player_id,
                   static_cast<float>(static_cast<int>(target_sick) | SicknessEvent::FLAG_WORSENED));
    }
}

void apply_curse(InternalState &state, int player_id, CurseType type) {
    if (!state.curses[player_id][type]) {
        state.curses[player_id][type] = true;
        push_event(state, player_id, EventType::EFFECT_CURSE, -1, player_id,
                   static_cast<float>((static_cast<int>(type) + 1) | CurseEvent::FLAG_APPLIED));
    }
}

void remove_curse(InternalState &state, int player_id, CurseType type) {
    if (state.curses[player_id][type]) {
        state.curses[player_id][type] = false;
        push_event(state, player_id, EventType::EFFECT_CURSE, -1, player_id,
                   static_cast<float>((static_cast<int>(type) + 1) | CurseEvent::FLAG_CLEARED));
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
            apply_curse(state, player_id, CURSE_TYPE_FOG);
        } else if (curse == CURSE_FLASH) {
            apply_curse(state, player_id, CURSE_TYPE_FLASH);
        } else if (curse == CURSE_DARK_CLOUD) {
            apply_curse(state, player_id, CURSE_TYPE_DARK_CLOUD);
        } else if (curse == CURSE_DREAM) {
            apply_curse(state, player_id, CURSE_TYPE_DREAM);
        }
    }
}


/**
 * @brief 「運命のひも」による超常現象の抽選と解決を行います。
 *
 * 10種類の超常現象を等確率で抽選し、その効果を適用します。効果の対象は現象ごとに異なり、
 * 使用者のみ・両プレイヤー・相手のみのいずれもあります。
 * 巨大なタライとブラックホールは「対象への効果適用」ではなく攻撃であり、
 * 相手を狙った場合は防御フェイズを起動します。
 *
 * @param user_id 「運命のひも」の効果を受けたプレイヤー（現象の起点）。
 */
static void resolve_string_of_fate(InternalState &state, int user_id) {
    std::uniform_int_distribution<int> dist(0, 9);
    PhenomenonType phenomenon = static_cast<PhenomenonType>(dist(state.rng));
    int opp = 1 - user_id;
    push_event(state, user_id, EventType::TRIGGER_PHENOMENON, ID_STRING_OF_FATE, -1, static_cast<float>(phenomenon));

    if (phenomenon == PHENOMENON_SUNSET) { // 夕焼け: 全員熱病
        apply_sickness(state, 0, SICKNESS_FEVER);
        apply_sickness(state, 1, SICKNESS_FEVER);
    }
    else if (phenomenon == PHENOMENON_DENSE_FOG) { // 濃霧: 全員霧
        apply_curse(state, 0, CURSE_TYPE_FOG);
        apply_curse(state, 1, CURSE_TYPE_FOG);
    }
    else if (phenomenon == PHENOMENON_MUSHROOM) { // きのこ大発生
        state.mushroom_turns += 6;
    }
    else if (phenomenon == PHENOMENON_TORNADO) { // 竜巻: 全員HP ➡ 1
        state.hp[0] = 1;
        state.hp[1] = 1;
    }
    else if (phenomenon == PHENOMENON_GIGANTIC_TUB) { // 巨大なタライ: 自分か相手に光属性攻50
        int target_player = std::uniform_int_distribution<int>(0, 1)(state.rng);
        if (target_player == user_id) { // 自分自身: 防御不可で50ダメ
            apply_damage(state, user_id, 50);
        } else { // 相手: 防御フェイズ起動
            state.attacker_id = user_id;
            state.defender_id = opp;
            state.current_actor_id = opp;
            state.current_phase = GamePhase::PHASE_DEFENSE;
            set_pending_attack(state, ID_GIGANTIC_TUB, 50, ELEM_LIGHT, false);
            state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
        }
    }
    else if (phenomenon == PHENOMENON_BLACK_HOLE) { // ブラックホール: 自分が撃った全体攻撃
        state.attacker_id = user_id;
        state.defender_id = opp;
        state.current_actor_id = opp;
        state.current_phase = GamePhase::PHASE_DEFENSE;
        set_pending_attack(state, ID_BLACK_HOLE, 30, ELEM_DARKNESS, true); // 全体攻撃
        state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
    }
    else if (phenomenon == PHENOMENON_WARM_CURRENT) { // 暖流: 自身HP+50
        add_hp(state, user_id, 50);
    }
    else if (phenomenon == PHENOMENON_GOLD_MINE) { // 金山: お金集約
        int total_money = state.money[0] + state.money[1];
        int lucky = std::uniform_int_distribution<int>(0, 1)(state.rng);
        state.money[lucky] = std::clamp(total_money, 0, 99);
        state.money[1 - lucky] = 0;
    }
    else if (phenomenon == PHENOMENON_MAGNETIC_STORM) { // 磁気嵐: 手札相互交換 & known_to_opp 追跡
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
    else if (phenomenon == PHENOMENON_ECLIPSE) { // 日食: 重複しない守護神割り当て
        int g0 = std::uniform_int_distribution<int>(1, 10)(state.rng);
        int g1 = std::uniform_int_distribution<int>(1, 9)(state.rng);
        if (g1 >= g0) {
            g1 += 1;
        }
        change_guardian(state, 0, static_cast<GuardianType>(g0));
        change_guardian(state, 1, static_cast<GuardianType>(g1));
    }
}

/**
 * @brief カード1枚の効果を対象プレイヤーへ適用します。
 *
 * 効果の適用のみを行い、フェイズ遷移や死亡確定は扱いません。
 * HPが0になった場合の復活・勝敗判定は、ターン終了処理の run_death_check() が担当します。
 * （「運命のひも」から巨大なタライ等が発動した場合のみ、resolve_string_of_fate() が
 * 　防御フェイズを起動します）
 *
 * カードIDごとの効果定義はここに集約されています。守護神の行動カードもこの経路を通ります。
 */
void apply_card_effect_to_target(InternalState &state, int target_id, int card_id) {
    CardFeatures &f = g_card_registry[card_id];

    // 武器・奇跡の hit_curse は pending_attack_curse 経由で付与されるため、ここでは二重付与を避ける
    if (f.hit_curse != CURSE_NONE && !f.is_weapon() && !f.is_miracle()) {
        apply_curse_to_player(state, target_id, f.hit_curse);
    }

    // 以降はカードIDごとの固有効果。1枚が該当するのは高々1つなので排他チェーンで判定する。
    if (card_id == ID_SMILE_DEW) {
        add_hp(state, target_id, 5);
    } else if (card_id == ID_HEART_DEW) {
        add_hp(state, target_id, 10);
    } else if (card_id == ID_ROMANCE_WATER) {
        add_hp(state, target_id, 15);
    } else if (card_id == ID_GALAXY_GEYSER) {
        add_hp(state, target_id, 20);
    } else if (card_id == ID_SPRING) {
        add_hp(state, target_id, 10);
    } else if (card_id == ID_THUMP_THUMP_TEAR) {
        std::uniform_int_distribution<int> dist(0, 1);
        int hp_before = state.hp[target_id];
        add_hp(state, target_id, (dist(state.rng) == 0) ? 10 : -10);
        // HPが減った場合はダメージ扱いとし、守護神の離脱判定を行う
        try_guardian_leave(state, target_id, state.hp[target_id] < hp_before);
    } else if (card_id == ID_SMILE_FLOWER) {
        add_mp(state, target_id, 5);
    } else if (card_id == ID_HEART_FLOWER) {
        add_mp(state, target_id, 10);
    } else if (card_id == ID_ROMANCE_FRAGRANCE) {
        add_mp(state, target_id, 15);
    } else if (card_id == ID_HEAVEN_HERB) {
        add_mp(state, target_id, 20);
    } else if (card_id == ID_HEALTHY_SEAFOOD_SOUP) { // 海王神
        add_hp(state, target_id, 10);
    } else if (card_id == ID_SEAFOOD_SOUP) { // 海王神
        add_hp(state, target_id, 5);
    } else if (card_id == ID_FRESH_BEACH_AROMA) { // 海王神
        add_mp(state, target_id, 10);
    } else if (card_id == ID_BEACH_AROMA) { // 海王神
        add_mp(state, target_id, 5);
    } else if (card_id == ID_SOUND_OF_RIPPLES) { // 海王神
        clear_all_status_effects(state, target_id);
    } else if (card_id == ID_TREASURE) {
        add_money(state, target_id, 10);
    } else if (card_id == ID_LUXURY_ACCESSORY) { // 金星神
        add_money(state, target_id, 20);
    } else if (card_id == ID_LITTLE_SOMETHING) { // 金星神
        add_money(state, target_id, 8);
    } else if (card_id == ID_COIN_SCATTERING) { // 金星神（両者に適用されるため呼び出し側が2回呼ぶ）
        add_money(state, target_id, 1);
    } else if (card_id == ID_TONE || card_id == ID_SMILE_SHELL) {
        // 風邪・熱病のみ治し、霧と閃光を解除する
        if (state.sickness[target_id] == SICKNESS_COLD || state.sickness[target_id] == SICKNESS_FEVER) {
            state.sickness[target_id] = SICKNESS_NONE;
        }
        remove_curse(state, target_id, CURSE_TYPE_FOG);
        remove_curse(state, target_id, CURSE_TYPE_FLASH);
    } else if (card_id == ID_SONG || card_id == ID_HEART_SHELL) {
        clear_all_status_effects(state, target_id);
    } else if (card_id == ID_RELEASE) {
        change_guardian(state, 0, GUARDIAN_NONE);
        change_guardian(state, 1, GUARDIAN_NONE);
    } else if (card_id == ID_GUARDIAN_POT) {
        std::uniform_int_distribution<int> dist(1, 10);
        change_guardian(state, target_id, static_cast<GuardianType>(dist(state.rng)));
    } else if (card_id == ID_NOCTURNAL_BROOM) {
        discard_random_cards(state, target_id, 3, false); // 未使用・未展開の手札を3枚
    } else if (card_id == ID_GODDESS_S_SOAP) {
        discard_random_cards(state, target_id, 2, true); // 展開済みの奇跡を2枚
    } else if (card_id == ID_STRING_OF_FATE) {
        resolve_string_of_fate(state, target_id);
    }
}

/**
 * @brief 仮置きされていたカード群の効果を、対象プレイヤーへ順に適用します。
 *
 * 武器の仮置きセットを渡す経路もありますが、武器そのものに対応する効果はないため実質何もしません
 * （武器の状態異常付与は pending_attack_curse 経由で防御解決側が扱います）。
 */
void apply_card_effects_to_target(InternalState &state, int target_id, const StagedCardIds& used_card_ids) {
    for (int card_id : used_card_ids) {
        apply_card_effect_to_target(state, target_id, card_id);
    }
}

void execute_money_deduction(InternalState &state, int player, int amount) {
    int remaining = amount;

    // 1. お金から支払う
    int money_paid = std::min(state.money[player], remaining);
    state.money[player] -= money_paid;
    remaining -= money_paid;

    // 2. MPから支払う
    if (remaining > 0) {
        int mp_paid = std::min(state.mp[player], remaining);
        state.mp[player] -= mp_paid;
        remaining -= mp_paid;
    }

    // 3. HPから支払う (直接ダメージ扱い)
    if (remaining > 0) {
        int hp_paid = std::min(state.hp[player], remaining);
        state.hp[player] -= hp_paid;
        remaining -= hp_paid;
        if (state.hp[player] == 0) {
            run_immediate_revive(state);
        }
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
    // 地球神が仕掛けた「売る」は、売るカード自体が手札に存在しないため staged_cards[p][0] に
    // -1 の番兵を置き、[1] に売り出すアイテムの手札インデックスを入れている。
    // （「買う」の番兵は num_staged_cards == 1 なので >= 2 の条件で区別できる）
    } else if (state.num_staged_cards[0] >= 2 && state.staged_cards[0][0] == -1) {
        original_seller = 0;
    } else if (state.num_staged_cards[1] >= 2 && state.staged_cards[1][0] == -1) {
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
    
    // 3. 買い手の支払いを処理する (お金 ➜ MP ➜ HP の順で徴収)
    execute_money_deduction(state, buyer, price);

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
            push_event(state, me, EventType::REFLECT_MIRROR, ID_SUPER_MIRROR, opp, 0.0f);
            
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
        apply_curse(state, player_id, CURSE_TYPE_DREAM);
        bool is_staged[MAX_HAND_SIZE] = {false};
        for (int k = 0; k < state.num_staged_cards[player_id]; ++k) {
            int slot = state.staged_cards[player_id][k];
            // 守護神由来の仮置きは番兵 -1 を置くため、手札スロットとして使う前に範囲を検査する
            if (slot >= 0 && slot < MAX_HAND_SIZE) {
                is_staged[slot] = true;
            }
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

/**
 * @brief 手札から指定カードを探し、最初に見つかったスロット番号を返します（見つからなければ -1）。
 */
static int find_card_in_hand(const InternalState &state, int player_id, int card_id) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] == card_id) {
            return i;
        }
    }
    return -1;
}

/**
 * @brief 手札スロットのカードを消費し、使用済み・相手に公開済みの状態にします。
 */
static void consume_hand_card(InternalState &state, int player_id, int slot_idx) {
    clear_hand_slot(state, player_id, slot_idx);
    state.is_used[player_id][slot_idx] = true;
    state.is_known_to_opp[player_id][slot_idx] = true;
}

/**
 * @brief HPが0のプレイヤーが「太陽のお守り」を持っていれば、消費してHP10で復活させます。
 * @return 復活した場合 true。HPが0でない場合やお守りを持っていない場合は false。
 */
static bool try_revive_with_amulet(InternalState &state, int player_id) {
    if (state.hp[player_id] != 0) return false;
    int amulet_slot = find_card_in_hand(state, player_id, ID_SUN_AMULET);
    if (amulet_slot == -1) return false;

    state.hp[player_id] = 10;
    consume_hand_card(state, player_id, amulet_slot);
    return true;
}

bool run_immediate_revive(InternalState &state) {
    bool revived = false;
    for (int p = 0; p < 2; ++p) {
        if (try_revive_with_amulet(state, p)) {
            revived = true;
        }
    }
    if (revived) {
        run_immediate_revive(state);
    }
    return revived;
}

void try_guardian_leave(InternalState &state, int player_id, bool hp_decreased) {
    if (!hp_decreased || state.guardian[player_id] <= GUARDIAN_NONE) return;
    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
    if (roll < GUARDIAN_LEAVE_RATE) {
        change_guardian(state, player_id, GUARDIAN_NONE);
    }
}

void apply_damage(InternalState &state, int player_id, int damage, bool absorption, bool deal_same_damage) {
    if (damage <= 0) return;
    int hp_before = state.hp[player_id];

    state.hp[player_id] = std::max(0, state.hp[player_id] - damage);
    try_guardian_leave(state, player_id, state.hp[player_id] < hp_before);

    if (absorption) {
        state.hp[player_id] = std::min(99, state.hp[player_id] + damage);
    }

    run_immediate_revive(state);

    if (deal_same_damage) {
        int hp_before_recoil = state.hp[player_id];
        state.hp[player_id] = std::max(0, state.hp[player_id] - damage);
        try_guardian_leave(state, player_id, state.hp[player_id] < hp_before_recoil);
        run_immediate_revive(state);
    }
}

bool run_death_check(InternalState &state) {
    while (true) {
        // 0. 両者死亡していて、どちらも太陽のお守りを持っていない場合は、即座に引き分け終了
        if (state.hp[0] == 0 && state.hp[1] == 0) {
            bool has_amulet[2] = {false, false};
            for (int p = 0; p < 2; ++p) {
                has_amulet[p] = (find_card_in_hand(state, p, ID_SUN_AMULET) != -1);
            }
            if (!has_amulet[0] && !has_amulet[1]) {
                if (state.remaining_attacks > 0) return false;
                state.is_done = true;
                state.p0_reward = DRAW_REWARD;
                state.p1_reward = DRAW_REWARD;
                return false;
            }
        }

        // 1. 各プレイヤーについて、もし保留中の昇天弓があるなら、そのうちの1つを発射する
        for (int p = 0; p < 2; ++p) {
            while (state.pending_ascension_bows[p] > 0) {
                state.pending_ascension_bows[p]--;
                int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                if (roll < ASCENSION_BOW_HIT_RATE) {
                    state.current_phase = GamePhase::PHASE_DEFENSE;
                    state.attacker_id = p;
                    state.defender_id = 1 - p;
                    state.current_actor_id = 1 - p;
                    state.num_staged_cards[1 - p] = 0; // 防御側の仮置き場をクリア
                    // 昇天弓は状態異常付与もCP奪取も行わない。cleanup_phase_end はターン終了処理の
                    // CLEANUP まで走らないため、直前の攻撃の効果はここで確実に打ち消す必要がある。
                    set_pending_attack(state, ID_ASCENSION_BOW, 30, ELEM_LIGHT, false);
                    return true; // 防御フェイズへ移行するため一時中断
                } else {
                    push_event(state, p, EventType::ATTACK_MISS, ID_ASCENSION_BOW, 1 - p, 0.0f);
                }
            }
        }

        // 2. HPが0のプレイヤーに対して、太陽のお守りによる復活、または昇天弓のキューイングを行う
        bool changed = false;
        for (int p = 0; p < 2; ++p) {
            if (state.hp[p] == 0) {
                // 太陽のお守りによる復活
                if (try_revive_with_amulet(state, p)) {
                    // 再チェックするためにループの最初へ
                    changed = true;
                    break;
                }

                // 昇天弓を探す
                std::vector<int> bow_slots;
                for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                    if (state.true_hand[p][i] == ID_ASCENSION_BOW) {
                        bow_slots.push_back(i);
                    }
                }
                if (!bow_slots.empty()) {
                    state.pending_ascension_bows[p] = static_cast<int>(bow_slots.size());
                    for (int slot : bow_slots) {
                        consume_hand_card(state, p, slot);
                        push_event(state, p, EventType::CONFIRM_ATTACK, ID_ASCENSION_BOW, 1 - p, 0.0f);
                    }
                    // 再チェックするためにループの最初へ
                    changed = true;
                    break;
                }
            }
        }

        if (changed) {
            continue;
        }

        // 3. 復活やお守り・弓がすべて終了した時点で、依然として死亡しているプレイヤーがあるか確認
        int active = state.current_actor_id;
        int passive = 1 - active;

        if (state.hp[0] == 0 && state.hp[1] == 0) {
            if (state.remaining_attacks > 0) return false;
            state.is_done = true;
            state.p0_reward = DRAW_REWARD;
            state.p1_reward = DRAW_REWARD;
            return false;
        }
        
        if (state.hp[active] == 0) {
            if (state.remaining_attacks > 0) return false;
            // 手番プレイヤーが死亡した場合は即座にゲーム終了（待機プレイヤーの勝利）
            state.is_done = true;
            state.p0_reward = (passive == 0) ? WIN_REWARD : LOSE_REWARD;
            state.p1_reward = (passive == 1) ? WIN_REWARD : LOSE_REWARD;
            return false;
        }
        
        if (state.hp[passive] == 0) {
            // もしターンエンドの病気解決（State 3）に達していないなら、まだ終了させず、
            // 手番プレイヤーの病気ダメージ（State 1, 2）を解決させるためスルーする。
            if (state.turn_end_state < TurnEndSubstep::FINAL_DEATH_CHECK) {
                return false;
            }
            if (state.remaining_attacks > 0) return false;
            state.is_done = true;
            state.p0_reward = (active == 0) ? WIN_REWARD : LOSE_REWARD;
            state.p1_reward = (active == 1) ? WIN_REWARD : LOSE_REWARD;
            return false;
        }

        return false;
    }
}

static bool setup_guardian_attack_defense(InternalState &state, int attacker, int defender, int source_id, GamePhase phase, bool absorption = false, int override_power = -1) {
    const CardFeatures &feat = g_card_registry[source_id];

    // 命中率（accuracy）チェック。暗雲がかかっていない場合で確率計算
    if (feat.accuracy < 100 && !state.curses[defender][CURSE_TYPE_DARK_CLOUD]) {
        std::uniform_int_distribution<int> dist(0, 99);
        if (dist(state.rng) >= feat.accuracy) {
            // 外れても「攻撃を仕掛けて外した」ことがログに残るようイベントを発行する
            push_event(state, attacker, EventType::EFFECT_GUARDIAN, source_id, defender, static_cast<float>(state.guardian[attacker]));
            push_event(state, attacker, EventType::ATTACK_MISS, source_id, defender, 0.0f);
            state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
            return false; // ミス：防御フェイズを起動せず終了
        }
    }

    if (feat.type == CardType::GUARDIAN && (source_id == ID_FINE || source_id == ID_BRIBE || (feat.attack_power == 0 && feat.hit_curse != CURSE_NONE))) {
        state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
    } else {
        state.current_phase = phase;
    }
    state.attacker_id = attacker;
    state.defender_id = defender;
    state.current_actor_id = defender;
    set_pending_attack(state, source_id,
                       (override_power != -1) ? override_power : feat.attack_power,
                       feat.element, feat.is_group_attack, absorption, feat.hit_curse);
    state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
    push_event(state, attacker, EventType::EFFECT_GUARDIAN, source_id, defender, static_cast<float>(state.guardian[attacker]));
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
        run_immediate_revive(state);
        state.current_phase = GamePhase::PHASE_END;
        if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
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
            run_immediate_revive(state);
            state.current_phase = GamePhase::PHASE_END;
            if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
            return true;
        } else {
            // 相手ターゲット：物理防御フェイズ起動
            bool ok = setup_guardian_attack_defense(state, attacker, defender, ID_DANGEROUS_PESTLE, GamePhase::PHASE_DEFENSE);
            if (!ok) {
                state.current_phase = GamePhase::PHASE_END;
                if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
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
        if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
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
        run_immediate_revive(state);
        state.current_phase = GamePhase::PHASE_END;
        if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
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
        if (is_guardian) state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
    }
    return true;
}

/**
 * @brief 攻撃系守護神の行動カード表。
 *
 * 火星・水星・木星・土星・天王・冥王の6神は、抽選された行動番号（act_idx: 1〜5）に
 * 対応するカードが異なるだけで、解決処理は setup_guardian_attack_defense() で共通です。
 * 配列の添字は act_idx - 1 に対応します。
 */
struct GuardianAttackActions {
    GuardianType guardian;
    int cards[5];
};

static const GuardianAttackActions GUARDIAN_ATTACK_ACTIONS[] = {
    {GUARDIAN_MARS,    {ID_FIRE_SHOUT, ID_FIRE_ROAR, ID_FIRE_BUZZ, ID_FIRE_TWEET, ID_FIRE_WHISPER}},
    {GUARDIAN_MERCURY, {ID_HAIL, ID_SPLASH, ID_BUBBLES, ID_MISTY_BREATH, ID_DRIZZLE}},
    {GUARDIAN_JUPITER, {ID_DANCE_OF_FALLEN_LEAVES, ID_COLORED_LEAVES, ID_TENTACLES, ID_ROOT, ID_BRANCH}},
    {GUARDIAN_SATURN,  {ID_BOULDER, ID_STONE, ID_PEBBLE, ID_BODY_PRESS, ID_DIAMOND_AXE}},
    {GUARDIAN_URANUS,  {ID_LASER_BEAM, ID_HALO, ID_BLESSING, ID_ELECTRIC_SHOCK, ID_TWINKLE}},
    {GUARDIAN_PLUTO,   {ID_WINK, ID_THINKING, ID_OMINOUS_PREMONITION, ID_COUGH, ID_HAND_RAISING}},
};

/**
 * @brief 海王神の行動カード表（act_idx 1〜5 に対応）。
 *
 * いずれも持ち主自身を対象とした雑貨と同型の効果で、効果本体は
 * apply_card_effect_to_target() のカードID分岐が持ちます。
 */
static const int NEPTUNE_ACTIONS[5] = {
    ID_HEALTHY_SEAFOOD_SOUP, // HP+10
    ID_SEAFOOD_SOUP,         // HP+5
    ID_FRESH_BEACH_AROMA,    // MP+10
    ID_BEACH_AROMA,          // MP+5
    ID_SOUND_OF_RIPPLES,     // 状態異常を全解除
};

/**
 * @brief 指定した守護神が攻撃系（行動カード表を持つ）ならその表を返し、そうでなければ nullptr を返します。
 */
static const int *find_guardian_attack_actions(GuardianType guardian) {
    for (const GuardianAttackActions &entry : GUARDIAN_ATTACK_ACTIONS) {
        if (entry.guardian == guardian) {
            return entry.cards;
        }
    }
    return nullptr;
}

/**
 * @brief 月神が使用しうる奇跡の一覧（壁 ID_WALL と乱気流 ID_TURBULENCE を除く28種）。
 */
static const int MOON_MIRACLES[] = {
    ID_FIREBALL, ID_ICE, ID_DARKNESS, ID_BIG_TREE, ID_ROCK, ID_FLAME, ID_ABSORPTION,
    ID_METEOR, ID_WATERFALL, ID_WIND, ID_HEAVEN_WIND, ID_FOG, ID_DREAM, ID_DARK_CLOUD,
    ID_FLASH, ID_SMOKE, ID_AVALANCHE, ID_THUNDER, ID_MUDFLOW, ID_MAGMA, ID_ICE_AGE,
    ID_AURA, ID_MIRAGE, ID_SPRING, ID_TREASURE, ID_TONE, ID_SONG, ID_RELEASE,
};
static constexpr int MOON_MIRACLE_COUNT = static_cast<int>(sizeof(MOON_MIRACLES) / sizeof(MOON_MIRACLES[0]));

/**
 * @brief 相手を攻撃せず、使用者自身に効果を及ぼす補助系の奇跡かを判定します。
 */
static bool is_support_miracle(int card_id) {
    return card_id == ID_TONE || card_id == ID_SONG || card_id == ID_RELEASE ||
           card_id == ID_SPRING || card_id == ID_TREASURE;
}

bool is_absorption_source(int card_id) {
    return card_id == ID_ABSORPTION ||       // ＜吸収＞（奇跡）
           card_id == ID_VINE_SHOOT ||       // ツルの芽
           card_id == ID_GHOST_SWORD ||      // ゴーストソード
           card_id == ID_REAL_GHOST_SWORD || // 真ゴーストソード
           card_id == ID_TENTACLES ||        // 触手（木星神）
           card_id == ID_BLESSING;           // 祝福（天王神）
}

bool resolve_turn_end_steps(InternalState &state) {
    bool is_apocalypse = (state.current_turn >= APOCALYPSE_TURN);
    while (state.current_phase == GamePhase::PHASE_END && !state.is_done) {
        switch (state.turn_end_state) {
            case TurnEndSubstep::DEATH_CHECK_START: { // 死亡・お守り・昇天弓の判定
                if (!is_apocalypse) {
                    bool paused = run_death_check(state);
                    if (paused) return true; // 防御フェイズへ移行のため一時中断
                }
                state.turn_end_state = TurnEndSubstep::SICKNESS_WORSEN;
                break;
            }
            case TurnEndSubstep::SICKNESS_WORSEN: { // 病気悪化判定
                int me = state.current_turn % 2;
                if (state.hp[me] > 0 && state.sickness[me] != SICKNESS_NONE) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < SICKNESS_WORSEN_RATE) {
                        if (state.sickness[me] == SICKNESS_HEAVEN) { // 天国病悪化 -> 死亡 (発作)
                            state.hp[me] = 0;
                            state.heaven_seizure_occurred[me] = true;
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, static_cast<float>(SicknessEvent::TYPE_HEAVEN | SicknessEvent::FLAG_SEIZURE));
                        } else if (state.sickness[me] == SICKNESS_COLD) { // 風邪 -> 熱病
                            apply_sickness(state, me, SICKNESS_FEVER);
                        } else if (state.sickness[me] == SICKNESS_FEVER) { // 熱病 -> 地獄病
                            apply_sickness(state, me, SICKNESS_HELL);
                        } else if (state.sickness[me] == SICKNESS_HELL) { // 地獄病 -> 天国病
                            apply_sickness(state, me, SICKNESS_HEAVEN);
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
                state.turn_end_state = TurnEndSubstep::SICKNESS_DAMAGE;
                break;
            }
            case TurnEndSubstep::SICKNESS_DAMAGE: { // 病気ダメージ・回復処理
                int me = state.current_turn % 2;
                int hp_before = state.hp[me];
                if (state.hp[me] > 0) {
                    if (state.sickness[me] == SICKNESS_COLD) { // 風邪: 1ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 1);
                        push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, static_cast<float>(SicknessEvent::TYPE_COLD | SicknessEvent::FLAG_DAMAGE));
                    } else if (state.sickness[me] == SICKNESS_FEVER) { // 熱病: 2ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 2);
                        push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, static_cast<float>(SicknessEvent::TYPE_FEVER | SicknessEvent::FLAG_DAMAGE));
                    } else if (state.sickness[me] == SICKNESS_HELL) { // 地獄病: 5ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 5);
                        push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, static_cast<float>(SicknessEvent::TYPE_HELL | SicknessEvent::FLAG_DAMAGE));
                    } else if (state.sickness[me] == SICKNESS_HEAVEN) { // 天国病: 5回復
                        if (!state.heaven_seizure_occurred[me]) {
                            state.hp[me] = std::min(99, state.hp[me] + 5);
                            push_event(state, me, EventType::EFFECT_SICKNESS, -1, me, static_cast<float>(SicknessEvent::TYPE_HEAVEN | SicknessEvent::FLAG_HEAL));
                        }
                    }
                }
                // 被病気ダメージによる守護神退散（天国病回復は対象外）
                try_guardian_leave(state, me, state.hp[me] < hp_before);
                // ダメージによって死亡したプレイヤーがあるかチェック
                if (state.hp[me] == 0) {
                    if (!is_apocalypse) {
                        bool paused = run_death_check(state);
                        if (paused) return true;
                    }
                }
                state.turn_end_state = TurnEndSubstep::FINAL_DEATH_CHECK;
                break;
            }
            case TurnEndSubstep::FINAL_DEATH_CHECK: { // 引き分け/勝敗の最終確定
                if (!is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused) return true;
                    }
                }
                state.turn_end_state = TurnEndSubstep::GUARDIAN_ACT;
                break;
            }
            case TurnEndSubstep::GUARDIAN_ACT: { // 相手の守護神の行動
                int me = state.current_turn % 2;     // 現在手番が終了した側
                int opp = 1 - me;                    // 次にターンが回る相手
                state.num_staged_cards[me] = 0;      // 被攻撃に備えて仮置き場をクリア
                
                if (state.hp[opp] > 0 && state.guardian[opp] > GUARDIAN_NONE) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < GUARDIAN_ACT_RATE) {
                        int roll_act = std::uniform_int_distribution<int>(0, 99)(state.rng);
                        int act_idx = 0;
                        if (roll_act < 30) act_idx = 1;
                        else if (roll_act < 55) act_idx = 2;
                        else if (roll_act < 75) act_idx = 3;
                        else if (roll_act < 90) act_idx = 4;
                        else act_idx = 5;

                        GuardianType g_id = state.guardian[opp];
                        
                        // 攻撃系の6神（火星・水星・木星・土星・天王・冥王）は行動カードのみが異なる
                        const int *action_cards = find_guardian_attack_actions(g_id);
                        if (action_cards != nullptr) {
                            int source_id = action_cards[act_idx - 1];
                            return setup_guardian_attack_defense(state, opp, me, source_id, GamePhase::PHASE_DEFENSE,
                                                                 is_absorption_source(source_id));
                        }

                        if (g_id == GUARDIAN_NEPTUNE) { // 海王神: 5行動すべてが持ち主自身への雑貨的な効果
                            int source_id = NEPTUNE_ACTIONS[act_idx - 1];
                            apply_card_effect_to_target(state, opp, source_id);
                            state.pending_attack_source_id = source_id;
                            push_event(state, opp, EventType::EFFECT_GUARDIAN, source_id, opp, static_cast<float>(g_id));
                        }
                        else if (g_id == GUARDIAN_VENUS) { // 金星神
                            // わいろ・罰金は相手を対象に取るため、スーパーミラー等で反射される機会がある
                            if (act_idx == 3) { // わいろ: 相手にお金+5
                                return setup_guardian_attack_defense(state, opp, me, ID_BRIBE, GamePhase::PHASE_DEFENSE, false, 5);
                            }
                            if (act_idx == 5) { // 罰金: 相手からお金3を没収
                                return setup_guardian_attack_defense(state, opp, me, ID_FINE, GamePhase::PHASE_DEFENSE, false, 3);
                            }

                            // 残る3行動はお金が増えるだけで、反射の機会はない
                            if (act_idx == 1) { // 小銭ばらまき: 両者にお金+1
                                apply_card_effect_to_target(state, 0, ID_COIN_SCATTERING);
                                apply_card_effect_to_target(state, 1, ID_COIN_SCATTERING);
                                state.pending_attack_source_id = ID_COIN_SCATTERING;
                                push_event(state, opp, EventType::EFFECT_GUARDIAN, ID_COIN_SCATTERING, -1, static_cast<float>(g_id));
                            } else { // 豪華なアクセサリー / ちょっとしたもの: 持ち主自身にお金
                                int source_id = (act_idx == 2) ? ID_LUXURY_ACCESSORY : ID_LITTLE_SOMETHING;
                                apply_card_effect_to_target(state, opp, source_id);
                                state.pending_attack_source_id = source_id;
                                push_event(state, opp, EventType::EFFECT_GUARDIAN, source_id, opp, static_cast<float>(g_id));
                            }
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
                                        bool paused = run_death_check(state);
                                        if (paused || state.is_done) return true;
                                    }
                                }
                                // 3. 売る (ID_SELL) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_SELL) {
                                    // can_sell_card(state, opp, -1) は「is_sellable_card な枠が1つ以上ある」と
                                    // 同値なので、候補を集めて空かどうかで判定すれば足りる
                                    std::vector<int> sell_candidates;
                                    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
                                        if (is_sellable_card(state, opp, i)) {
                                            sell_candidates.push_back(i);
                                        }
                                    }
                                    if (!sell_candidates.empty()) {
                                        int rand_idx = std::uniform_int_distribution<int>(0, static_cast<int>(sell_candidates.size()) - 1)(state.rng);
                                        int sell_slot = sell_candidates[rand_idx];

                                        state.attacker_id = opp;
                                        state.defender_id = me;
                                        state.current_actor_id = me;
                                        // 地球神は「売る」カード自体を手札に持たないため、番兵 -1 を置いて
                                        // [1] に出品カードの手札インデックスを入れる（execute_sell_resolution が参照）
                                        state.staged_cards[opp][0] = -1;
                                        state.staged_cards[opp][1] = sell_slot;
                                        state.num_staged_cards[opp] = 2;
                                        state.current_phase = GamePhase::PHASE_SELL_SELECT_MIRROR;
                                        state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                                        return true;
                                    }
                                }
                                // 4. 買う (ID_BUY) ➡ 対戦相手に使う
                                else if (drawn_card_id == ID_BUY) {
                                    state.attacker_id = opp;
                                    state.defender_id = me;
                                    state.current_actor_id = me;
                                    state.staged_cards[opp][0] = -1; // 地球神フラグ
                                    state.num_staged_cards[opp] = 1;
                                    state.current_phase = GamePhase::PHASE_BUY_SELECT_MIRROR;
                                    state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                                    return true;
                                }
                                // 5. 武器 ➡ 対戦相手に使う
                                else if (feat.is_weapon()) {
                                    if (drawn_card_id == ID_DANGEROUS_PESTLE) {
                                        // あぶないキネ: ランダムな対象へ光属性30ダメージ（専用解決）
                                        return execute_dangerous_pestle(state, opp, me, true);
                                    }
                                    // 引いた武器そのものの威力・属性・命中率で攻撃する。
                                    // 命中率が100未満の全体攻撃武器などは外れることもあり、その場合もイベントが残る。
                                    return setup_guardian_attack_defense(state, opp, me, drawn_card_id, GamePhase::PHASE_DEFENSE,
                                                                         is_absorption_source(drawn_card_id));
                                }
                                // 6. その他の雑貨
                                //    夜のホウキと女神の石けんは相手の手札を削るカードなので対戦相手へ、
                                //    それ以外（回復や状態異常解除など）は持ち主自身へ使う。
                                else {
                                    bool targets_opponent = (drawn_card_id == ID_NOCTURNAL_BROOM || drawn_card_id == ID_GODDESS_S_SOAP);
                                    if (targets_opponent) {
                                        // 相手に使う雑貨は、通常プレイと同様にスーパーミラーで跳ね返せる。
                                        // 効果の適用は受諾（または反射）の解決時に行う。
                                        state.attacker_id = opp;
                                        state.defender_id = me;
                                        state.current_actor_id = me;
                                        state.num_staged_cards[opp] = 0; // 守護神の仮想カードは仮置き場を使わない
                                        set_pending_attack(state, drawn_card_id, 0, ELEM_NONE, false);
                                        state.current_phase = GamePhase::PHASE_SUNDRY_SELECT_MIRROR;
                                        state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                                        push_event(state, opp, EventType::EFFECT_GUARDIAN, drawn_card_id, me, static_cast<float>(GUARDIAN_EARTH));
                                        return true;
                                    }

                                    push_event(state, opp, EventType::EFFECT_GUARDIAN, drawn_card_id, opp, static_cast<float>(GUARDIAN_EARTH));
                                    apply_card_effect_to_target(state, opp, drawn_card_id);

                                    // 「運命のひも」から巨大なタライ・ブラックホールが出た場合は防御フェイズが
                                    // 起動しているため、ターン終了処理を中断して防御の解決へ移る
                                    if (state.current_phase == GamePhase::PHASE_DEFENSE || state.current_phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
                                        state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                                        return true;
                                    }
                                }
                            }
                            // 早期 return しなかった経路は、いずれもクリーンアップ前の死亡判定へ進む
                            state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                        }
                        else if (g_id == GUARDIAN_MOON) { // 月神
                            int chosen_miracle = MOON_MIRACLES[std::uniform_int_distribution<int>(0, MOON_MIRACLE_COUNT - 1)(state.rng)];

                            // オーラ・蜃気楼は攻撃奇跡ではないため、満月刀の物理攻撃に読み替える
                            if (chosen_miracle == ID_AURA) { // オーラ: 威力2倍相当の ATK20
                                return setup_guardian_attack_defense(state, opp, me, ID_FULL_MOON_BLADE, GamePhase::PHASE_DEFENSE, false, 20);
                            }
                            else if (chosen_miracle == ID_MIRAGE) { // 蜃気楼: ATK10 の全体攻撃
                                setup_guardian_attack_defense(state, opp, me, ID_FULL_MOON_BLADE, GamePhase::PHASE_DEFENSE, false, 10);
                                state.pending_is_group_attack = true;
                                return true; // 満月刀は命中率100%のため常に防御フェイズへ移行する
                            }
                            else if (is_support_miracle(chosen_miracle)) { // 補助系: 持ち主自身へ効果を適用
                                push_event(state, opp, EventType::EFFECT_GUARDIAN, chosen_miracle, opp, static_cast<float>(GUARDIAN_MOON));
                                apply_card_effect_to_target(state, opp, chosen_miracle);
                            }
                            else { // 残る攻撃奇跡: 奇跡防御フェイズを起動
                                return setup_guardian_attack_defense(state, opp, me, chosen_miracle, GamePhase::PHASE_MIRACLE_DEFENSE,
                                                                     is_absorption_source(chosen_miracle));
                            }
                        }
                    }
                }
                state.turn_end_state = TurnEndSubstep::CLEANUP_DEATH_CHECK;
                break;
            }
            case TurnEndSubstep::CLEANUP_DEATH_CHECK: { // クリーンアップ前の死亡・お守り・昇天弓の判定
                if (!is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused || state.is_done) return true;
                    }
                }
                state.turn_end_state = TurnEndSubstep::CLEANUP;
                break;
            }
            case TurnEndSubstep::CLEANUP: { // クリーンアップ処理 (手札補充・奇跡の再配置など)
                cleanup_phase_end(state);
                state.turn_end_state = TurnEndSubstep::TURN_TRANSITION;
                break;
            }
            case TurnEndSubstep::TURN_TRANSITION: { // クリーンアップ後（黙示録ドロー時など）の死亡チェックおよびターン移行
                if (is_apocalypse) {
                    if (state.hp[0] == 0 || state.hp[1] == 0) {
                        bool paused = run_death_check(state);
                        if (paused || state.is_done) return true;
                    }
                }

                state.turn_end_state = TurnEndSubstep::DEATH_CHECK_START;
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
