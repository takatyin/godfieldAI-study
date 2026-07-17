#include "game_logic.h"
#include "game_logic_internal.h"
#include "generated_card_ids.h"
#include <algorithm>
#include <cstring>
#include <vector>
#include <random>

/**
 * @brief 指定されたカードが「捨てる」ことが可能なカード（武器・太陽のお守り・あぶないウス以外）かを判定します。
 */
bool is_discardable_card(int card_id) {
    if (card_id == CARD_EMPTY) return false;
    return !g_card_registry[card_id].is_weapon && card_id != ID_SUN_AMULET && card_id != ID_DANGEROUS_MORTAR;
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

/**
 * @brief 対象プレイヤーの仮置き場の最後に置かれたカードが「奇跡」であるかを判定します。
 */
bool is_last_staged_card_miracle(const InternalState &state, int player_id) {
    if (state.num_staged_cards[player_id] <= 0) {
        return false;
    }
    int last_staged_idx = state.staged_cards[player_id][state.num_staged_cards[player_id] - 1];
    int card_id = state.true_hand[player_id][last_staged_idx];
    if (card_id == CARD_EMPTY) return false;
    return g_card_registry[card_id].is_miracle;
}

/**
 * @brief 現在の仮置き場のカードから、今回の攻撃が「武器（物理）攻撃」であるかを判定します。
 *        （武器が含まれている、または攻撃奇跡が2枚以上の場合に武器攻撃扱いとなります）
 */
bool is_weapon_attack(const InternalState &state, int player_id) {
    int attack_weapons_count = 0;
    int attack_miracles_count = 0;
    for (int i = 0; i < state.num_staged_cards[player_id]; ++i) {
        int staged_idx = state.staged_cards[player_id][i];
        int card_id = state.true_hand[player_id][staged_idx];
        if (card_id == CARD_EMPTY) continue;
        CardFeatures &f = g_card_registry[card_id];
        if (f.is_weapon && !is_spiritual_zero_mp_card(card_id)) {
            attack_weapons_count++;
        }
        if (f.is_miracle && f.attack_power > 0) {
            attack_miracles_count++;
        }
    }
    if (attack_weapons_count > 0) return true;
    if (attack_miracles_count >= 2) return true;
    return false;
}

/**
 * @brief 仮置き場のカードの合計消費MPを計算します（精霊による奇跡コスト0化ルールを適用）。
 */
int calculate_staged_mp_cost(const InternalState &state, int player_id) {
    int total_cost = 0;
    int num_cards = state.num_staged_cards[player_id];

    for (int i = 0; i < num_cards; ++i) {
        int card_id = state.true_hand[player_id][state.staged_cards[player_id][i]];
        const CardFeatures &f = g_card_registry[card_id];

        // 奇跡カードであり、かつ直後（i + 1）に精霊系カードが置かれている場合はMP消費を0にする
        if (f.is_miracle && (i + 1 < num_cards)) {
            int next_card_id = state.true_hand[player_id][state.staged_cards[player_id][i + 1]];
            if (is_spiritual_zero_mp_card(next_card_id)) {
                continue; // コストが0になるため加算をスキップ
            }
        }
        total_cost += f.mp_cost;
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
    temp.staged_cards[player_id][temp.num_staged_cards[player_id]] = next_hand_idx;
    temp.num_staged_cards[player_id]++;
    
    // 1. 仮置き場以外の手札に残っている、未使用の「消費MPを0にする精霊系カード」の個数 U をカウント
    int U = 0;
    bool is_staged[MAX_HAND_SIZE];
    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
        is_staged[j] = false;
    }
    for (int i = 0; i < temp.num_staged_cards[player_id]; ++i) {
        is_staged[temp.staged_cards[player_id][i]] = true;
    }
    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
        if (temp.true_hand[player_id][j] != CARD_EMPTY && !temp.is_used[player_id][j] && !is_staged[j]) {
            if (is_spiritual_zero_mp_card(temp.true_hand[player_id][j])) {
                U++;
            }
        }
    }

    // 2. 仮置き場にある奇跡カードのうち、直後に精霊系カードが置かれていないもののMPコストをリスト化
    std::vector<int> miracle_costs;
    int base_non_miracle_cost = 0;
    int num_cards = temp.num_staged_cards[player_id];
    for (int i = 0; i < num_cards; ++i) {
        int card_id = temp.true_hand[player_id][temp.staged_cards[player_id][i]];
        const CardFeatures &f = g_card_registry[card_id];
        if (f.is_miracle) {
            bool followed_by_spiritual = false;
            if (i + 1 < num_cards) {
                int next_card_id = temp.true_hand[player_id][temp.staged_cards[player_id][i + 1]];
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
        int card_id = state.true_hand[player_id][i];
        if (card_id != CARD_EMPTY && !state.is_used[player_id][i]) {
            if (g_card_registry[card_id].is_weapon) return false;
        }
    }
    return true;
}

/**
 * @brief メインフェイズにおいて「捨てる」（捨てられるカードが1枚以上ある）が可能かを判定します。
 */
bool can_discard(const InternalState &state, int player_id) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.true_hand[player_id][i];
        if (card_id != CARD_EMPTY && !state.is_used[player_id][i]) {
            if (is_discardable_card(card_id)) return true;
        }
    }
    return false;
}

/**
 * @brief 「売る」カード自体を除いて、売却可能なカードが手札にあるかを判定します。
 */
bool can_sell_card(const InternalState &state, int player_id, int sell_card_index) {
    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
        if (j != sell_card_index) {
            if (state.true_hand[player_id][j] != CARD_EMPTY &&
                !state.is_deployed[player_id][j] &&
                !state.is_used[player_id][j]) {
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

    state.true_hand[player_id][best_idx] = CARD_EMPTY;
    state.is_known_to_opp[player_id][best_idx] = false;
    state.is_used[player_id][best_idx] = false;
    state.is_deployed[player_id][best_idx] = false;
    state.miracle_used_this_turn[player_id][best_idx] = false;
}

/**
 * @brief 空いている手札スロットに新しくカードをドローします。
 */
void draw_card_to_hand(InternalState &state, int player_id) {
    int empty_slot_idx = -1;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[player_id][i] == CARD_EMPTY) {
            empty_slot_idx = i;
            break;
        }
    }
    if (empty_slot_idx != -1) {
        state.true_hand[player_id][empty_slot_idx] = draw_card(state.rng);
        state.is_known_to_opp[player_id][empty_slot_idx] = false;
        state.is_used[player_id][empty_slot_idx] = false;
        state.is_deployed[player_id][empty_slot_idx] = false;
        state.miracle_used_this_turn[player_id][empty_slot_idx] = false;
    }
}

/**
 * @brief ターン終了時に使用済みフラグの解決や奇跡の再配置などを行います。
 */
void cleanup_phase_end(InternalState &state) {
    for (int p = 0; p < 2; ++p) {
        int draw_count = 0;
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.is_used[p][i]) {
                int card_id = state.true_hand[p][i];
                if (card_id == CARD_EMPTY) continue;
                CardFeatures &f = g_card_registry[card_id];
                
                if (f.is_miracle) {
                    state.is_deployed[p][i] = true;
                    state.is_known_to_opp[p][i] = true;
                    state.is_used[p][i] = false;
                    draw_count++;
                } else {
                    state.true_hand[p][i] = draw_card(state.rng);
                    state.is_known_to_opp[p][i] = false;
                    state.is_used[p][i] = false;
                    state.is_deployed[p][i] = false;
                    state.miracle_used_this_turn[p][i] = false;
                }
            }
        }
        
        for (int i = 0; i < draw_count; ++i) {
            draw_card_to_hand(state, p);
        }
        state.num_staged_cards[p] = 0;
    }
    state.pending_attack_power = 0;
    state.pending_attack_element = ELEM_NONE;
    state.pending_absorption = false;
    state.pending_is_group_attack = false;
}

/**
 * @brief 仮置きされているカードの実際のIDリストを取得します。
 */
std::vector<int> get_staged_card_ids(const InternalState &state, int player) {
    std::vector<int> ids;
    for (int i = 0; i < state.num_staged_cards[player]; ++i) {
        ids.push_back(state.true_hand[player][state.staged_cards[player][i]]);
    }
    return ids;
}

/**
 * @brief 適用対象プレイヤーに対して、使用されたカードの回復や状態異常、またはその他特殊カードの効果を処理します。
 */
void apply_card_effects_to_target(InternalState &state, int target_id, const std::vector<int>& used_card_ids) {
    int hp_diff = 0;
    int mp_diff = 0;
    for (int card_id : used_card_ids) {
        CardFeatures &f = g_card_registry[card_id];
        hp_diff += f.hp_recovery;
        mp_diff += f.mp_recovery;

        if (f.hit_curse != CURSE_NONE) {
            if (f.hit_curse == CURSE_COLD) state.sickness[target_id] = static_cast<int>(SicknessType::SICKNESS_COLD);
            else if (f.hit_curse == CURSE_FEVER) state.sickness[target_id] = static_cast<int>(SicknessType::SICKNESS_FEVER);
            else if (f.hit_curse == CURSE_HELL) state.sickness[target_id] = static_cast<int>(SicknessType::SICKNESS_HELL);
            else if (f.hit_curse == CURSE_HEAVEN) state.sickness[target_id] = static_cast<int>(SicknessType::SICKNESS_HEAVEN);
            else if (f.hit_curse == CURSE_FOG) state.curses[target_id][static_cast<int>(CurseType::CURSE_FOG)] = true;
            else if (f.hit_curse == CURSE_FLASH) state.curses[target_id][static_cast<int>(CurseType::CURSE_FLASH)] = true;
            else if (f.hit_curse == CURSE_DARK_CLOUD) state.curses[target_id][static_cast<int>(CurseType::CURSE_DARK_CLOUD)] = true;
            else if (f.hit_curse == CURSE_DREAM) state.curses[target_id][static_cast<int>(CurseType::CURSE_DREAM)] = true;
        }

        if (card_id == ID_TONE || card_id == ID_SMILE_SHELL) {
            state.sickness[target_id] = (state.sickness[target_id] == 1 || state.sickness[target_id] == 2) ? 0 : state.sickness[target_id];
            state.curses[target_id][0] = false;
            state.curses[target_id][1] = false;
        } else if (card_id == ID_SONG || card_id == ID_HEART_SHELL) {
            state.sickness[target_id] = 0;
            for (int j = 0; j < 4; ++j) state.curses[target_id][j] = false;
        }

        if (card_id == ID_GUARDIAN_POT) {
            std::uniform_int_distribution<int> dist(1, 10);
            state.guardian[target_id] = dist(state.rng);
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
                    state.true_hand[target_id][discard_idx] = CARD_EMPTY;
                    state.is_known_to_opp[target_id][discard_idx] = false;
                    state.is_used[target_id][discard_idx] = false;
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
                    state.true_hand[target_id][discard_idx] = CARD_EMPTY;
                    state.is_known_to_opp[target_id][discard_idx] = false;
                    state.is_deployed[target_id][discard_idx] = false;
                    state.miracle_used_this_turn[target_id][discard_idx] = false;
                    state.is_used[target_id][discard_idx] = false;
                }
            }
        }
    }

    state.hp[target_id] = std::clamp(state.hp[target_id] + hp_diff, 0, 99);
    state.mp[target_id] = std::clamp(state.mp[target_id] + mp_diff, 0, 99);

    if (state.hp[target_id] <= 0) {
        state.hp[target_id] = 0;
        state.is_done = true;
        state.p0_reward = (target_id == 0) ? -1.0f : 1.0f;
        state.p1_reward = (target_id == 1) ? -1.0f : 1.0f;
    }
}

/**
 * @brief 「売る」アクションにおける商品の引き渡しおよび決済の解決を行います。
 */
void execute_sell_resolution(InternalState &state, int seller, int buyer) {
    // 1. 最初に対象アイテムを売り出したオリジナル売り手を特定する
    // スーパーミラーによる反射が発生している可能性があるため、staged_cards を見て "売る" カードを所持している側を探す
    int original_seller = -1;
    if (state.num_staged_cards[0] > 0 && state.true_hand[0][state.staged_cards[0][0]] == ID_SELL) {
        original_seller = 0;
    } else if (state.num_staged_cards[1] > 0 && state.true_hand[1][state.staged_cards[1][0]] == ID_SELL) {
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
    
    // 5. 売り手の手札から売却したカードを削除し、関連フラグを初期化する
    state.true_hand[original_seller][idx] = CARD_EMPTY;
    state.is_known_to_opp[original_seller][idx] = false;
    state.is_used[original_seller][idx] = false; 

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
        state.true_hand[buyer][empty_slot] = card_id;
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
            state.true_hand[buyer][replace_idx] = card_id;
            state.is_known_to_opp[buyer][replace_idx] = true;
            state.is_deployed[buyer][replace_idx] = false;
            state.miracle_used_this_turn[buyer][replace_idx] = false;
            state.is_used[buyer][replace_idx] = false;
        }
    }

    // 7. 買い手のHP枯渇によるゲーム終了判定
    if (state.hp[buyer] <= 0) {
        state.hp[buyer] = 0;
        state.is_done = true;
        state.p0_reward = (buyer == 0) ? -1.0f : 1.0f;
        state.p1_reward = (buyer == 1) ? -1.0f : 1.0f;
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
            
            std::swap(state.attacker_id, state.defender_id);
            state.current_actor_id = opp;
            return true;
        }
    }
    return false;
}
