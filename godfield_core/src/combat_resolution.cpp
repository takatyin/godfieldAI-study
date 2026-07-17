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

void deploy_miracle(InternalState &state, int player_id, int slot_idx) {
    if (state.is_deployed[player_id][slot_idx]) {
        return;
    }
    state.is_deployed[player_id][slot_idx] = true;
    state.is_known_to_opp[player_id][slot_idx] = true;

    // 展開キューに積む
    state.deployed_miracles_order[player_id][state.num_deployed_miracles[player_id]] = slot_idx;
    state.num_deployed_miracles[player_id]++;

    // FIFO制限：展開数が6を超えたら、最も古い展開カードを未展開にし、手札から破棄する
    if (state.num_deployed_miracles[player_id] > 6) {
        int oldest_idx = state.deployed_miracles_order[player_id][0];
        
        clear_hand_slot(state, player_id, oldest_idx);

        // キューを左シフト
        for (int k = 1; k < state.num_deployed_miracles[player_id]; ++k) {
            state.deployed_miracles_order[player_id][k - 1] = state.deployed_miracles_order[player_id][k];
        }
        state.num_deployed_miracles[player_id]--;
    }
}

void undeploy_miracle(InternalState &state, int player_id, int slot_idx) {
    if (!state.is_deployed[player_id][slot_idx]) {
        return;
    }
    state.is_deployed[player_id][slot_idx] = false;

    // 展開キューから該当スロットを削除してシフト
    int found_idx = -1;
    for (int k = 0; k < state.num_deployed_miracles[player_id]; ++k) {
        if (state.deployed_miracles_order[player_id][k] == slot_idx) {
            found_idx = k;
            break;
        }
    }
}

void clear_hand_slot(InternalState &state, int player_id, int slot_idx) {
    state.true_hand[player_id][slot_idx] = CARD_EMPTY;
    state.is_known_to_opp[player_id][slot_idx] = false;
    state.is_used[player_id][slot_idx] = false;
    state.miracle_used_this_turn[player_id][slot_idx] = false;
    undeploy_miracle(state, player_id, slot_idx);
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
 *        （武器が含まれている場合に武器攻撃扱いとなります）
 */
bool is_weapon_attack(const InternalState &state, int player_id) {
    int attack_weapons_count = 0;
    for (int i = 0; i < state.num_staged_cards[player_id]; ++i) {
        int staged_idx = state.staged_cards[player_id][i];
        int card_id = state.true_hand[player_id][staged_idx];
        if (card_id == CARD_EMPTY) continue;
        CardFeatures &f = g_card_registry[card_id];
        if (f.is_weapon && !is_spiritual_zero_mp_card(card_id)) {
            attack_weapons_count++;
        }
    }
    if (attack_weapons_count > 0) return true;
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
        if (card_id == CARD_EMPTY) continue;
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

    clear_hand_slot(state, player_id, best_idx);
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
        int card_id = draw_card(state.rng);
        clear_hand_slot(state, player_id, empty_slot_idx);
        state.true_hand[player_id][empty_slot_idx] = card_id;
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
                if (card_id == CARD_EMPTY) {
                    int new_card = draw_card(state.rng);
                    clear_hand_slot(state, p, i);
                    state.true_hand[p][i] = new_card;
                    state.is_used[p][i] = false;
                    continue;
                }
                CardFeatures &f = g_card_registry[card_id];
                
                if (f.is_miracle) {
                    deploy_miracle(state, p, i);
                    state.is_used[p][i] = false;
                    draw_count++;
                } else {
                    int new_card = draw_card(state.rng);
                    clear_hand_slot(state, p, i);
                    state.true_hand[p][i] = new_card;
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
            int new_sick = 0;
            if (f.hit_curse == CURSE_COLD) new_sick = 1;
            else if (f.hit_curse == CURSE_FEVER) new_sick = 2;
            else if (f.hit_curse == CURSE_HELL) new_sick = 3;
            else if (f.hit_curse == CURSE_HEAVEN) new_sick = 4;

            if (new_sick > 0) {
                int cur_sick = state.sickness[target_id];
                if (cur_sick == 0) {
                    state.sickness[target_id] = new_sick;
                } else {
                    if (new_sick > cur_sick) {
                        state.sickness[target_id] = new_sick;
                    } else {
                        if (cur_sick == 4) {
                            state.hp[target_id] = 0;
                        } else {
                            state.sickness[target_id] = cur_sick + 1;
                        }
                    }
                }
            } else {
                if (f.hit_curse == CURSE_FOG) {
                    state.curses[target_id][static_cast<int>(CurseType::CURSE_FOG)] = true;
                } else if (f.hit_curse == CURSE_FLASH) {
                    state.curses[target_id][static_cast<int>(CurseType::CURSE_FLASH)] = true;
                } else if (f.hit_curse == CURSE_DARK_CLOUD) {
                    state.curses[target_id][static_cast<int>(CurseType::CURSE_DARK_CLOUD)] = true;
                } else if (f.hit_curse == CURSE_DREAM) {
                    state.curses[target_id][static_cast<int>(CurseType::CURSE_DREAM)] = true;
                }
            }
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
            clear_hand_slot(state, buyer, replace_idx);
            state.true_hand[buyer][replace_idx] = card_id;
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
            
            std::swap(state.attacker_id, state.defender_id);
            state.current_actor_id = opp;
            return true;
        }
    }
    return false;
}

bool is_active_reaction_card(int card_id, GamePhase phase, Element attack_element) {
    if (card_id == CARD_EMPTY) return false;
    if (phase == GamePhase::PHASE_MIRACLE_DEFENSE) {
        const CardFeatures &f = g_card_registry[card_id];
        return f.reaction_type != REACTION_NONE;
    }
    if (phase == GamePhase::PHASE_DEFENSE) {
        if (card_id == ID_SUPER_MIRROR) return true;
        if (attack_element == ELEM_NONE) {
            return (card_id == ID_WALL || card_id == ID_SWORD_WARE || card_id == ID_REFLECTION_SWORD);
        }
    }
    return false;
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
                state.pending_is_group_attack = false;
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
                state.true_hand[p][amulet_slot] = CARD_EMPTY;
                state.is_used[p][amulet_slot] = true;
                state.is_deployed[p][amulet_slot] = false;
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
                    state.true_hand[p][slot] = CARD_EMPTY;
                    state.is_used[p][slot] = true;
                    state.is_deployed[p][slot] = false;
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
        state.is_done = true;
        state.p0_reward = 0.0f;
        state.p1_reward = 0.0f;
        return false;
    }
    
    if (state.hp[active] == 0) {
        // 手番プレイヤーが死亡した場合は即座にゲーム終了（待機プレイヤーの勝利）
        state.is_done = true;
        state.p0_reward = (passive == 0) ? 1.0f : -1.0f;
        state.p1_reward = (passive == 1) ? 1.0f : -1.0f;
        return false;
    }
    
    if (state.hp[passive] == 0) {
        // 待機プレイヤーのみが死亡している場合：
        // もしターンエンドの病気解決（State 3）に達していないなら、まだ終了させず、
        // 手番プレイヤーの病気ダメージ（State 1, 2）を解決させるためスルーする。
        if (state.turn_end_state < 3) {
            return false;
        }
        state.is_done = true;
        state.p0_reward = (active == 0) ? 1.0f : -1.0f;
        state.p1_reward = (active == 1) ? 1.0f : -1.0f;
        return false;
    }

    return false;
}

bool resolve_turn_end_steps(InternalState &state) {
    while (state.current_phase == GamePhase::PHASE_END && !state.is_done) {
        switch (state.turn_end_state) {
            case 0: { // 死亡・お守り・昇天弓の判定
                bool paused = run_death_check(state);
                if (paused) return true; // 防御フェイズへ移行のため一時中断
                state.turn_end_state = 1;
                break;
            }
            case 1: { // 病気悪化判定
                int me = state.current_actor_id;
                if (state.hp[me] > 0 && state.sickness[me] != 0) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < 5) {
                        if (state.sickness[me] == 4) { // 天国病悪化 -> 死亡
                            state.hp[me] = 0;
                            state.heaven_seizure_occurred[me] = true;
                        } else if (state.sickness[me] == 1) { // 風邪 -> 熱病
                            state.sickness[me] = 2;
                        } else if (state.sickness[me] == 2) { // 熱病 -> 地獄病
                            state.sickness[me] = 3;
                        } else if (state.sickness[me] == 3) { // 地獄病 -> 天国病
                            state.sickness[me] = 4;
                        }
                    }
                }
                // 悪化によって死亡したプレイヤーがいるかチェック
                if (state.hp[me] == 0) {
                    bool paused = run_death_check(state);
                    if (paused) return true;
                }
                state.turn_end_state = 2;
                break;
            }
            case 2: { // 病気ダメージ・回復処理
                int me = state.current_actor_id;
                if (state.hp[me] > 0) {
                    if (state.sickness[me] == 1) { // 風邪: 1ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 1);
                    } else if (state.sickness[me] == 2) { // 熱病: 2ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 2);
                    } else if (state.sickness[me] == 3) { // 地獄病: 5ダメ
                        state.hp[me] = std::max(0, state.hp[me] - 5);
                    } else if (state.sickness[me] == 4) { // 天国病: 5回復
                        if (!state.heaven_seizure_occurred[me]) {
                            state.hp[me] = std::min(99, state.hp[me] + 5);
                        }
                    }
                }
                // ダメージによって死亡したプレイヤーがあるかチェック
                if (state.hp[me] == 0) {
                    bool paused = run_death_check(state);
                    if (paused) return true;
                }
                state.turn_end_state = 3;
                break;
            }
            case 3: { // 引き分け/勝敗の最終確定
                if (state.hp[0] == 0 || state.hp[1] == 0) {
                    bool paused = run_death_check(state);
                    if (paused) return true;
                }
                state.turn_end_state = 4;
                break;
            }
            case 4: { // 相手の守護神の行動
                int opp = 1 - state.current_actor_id; // 次にターンが回る相手
                int me = state.current_actor_id;     // 現在手番が終了した側
                state.num_staged_cards[me] = 0;      // 被攻撃に備えて仮置き場をクリア
                
                if (state.hp[opp] > 0 && state.guardian[opp] > 0) {
                    int roll = std::uniform_int_distribution<int>(0, 99)(state.rng);
                    if (roll < 25) { // 25%の確率で行動
                        int roll_act = std::uniform_int_distribution<int>(0, 99)(state.rng);
                        int act_idx = 0;
                        if (roll_act < 30) act_idx = 1;
                        else if (roll_act < 55) act_idx = 2;
                        else if (roll_act < 75) act_idx = 3;
                        else if (roll_act < 90) act_idx = 4;
                        else act_idx = 5;

                        int g_id = state.guardian[opp];
                        
                        if (g_id == 1) { // 火星神
                            int power = 0;
                            if (act_idx == 1) power = 25;
                            else if (act_idx == 2) power = 20;
                            else if (act_idx == 3) power = 15;
                            else if (act_idx == 4) power = 10;
                            else power = 5;
                            
                            state.current_phase = GamePhase::PHASE_DEFENSE;
                            state.attacker_id = opp;
                            state.defender_id = me;
                            state.current_actor_id = me;
                            state.pending_attack_power = power;
                            state.pending_attack_element = ELEM_FIRE;
                            state.pending_absorption = false;
                            state.pending_is_group_attack = (act_idx < 5);
                            state.turn_end_state = 5;
                            return true;
                        }
                        else if (g_id == 2) { // 水星神
                            int power = 0;
                            if (act_idx == 1) power = 20;
                            else if (act_idx == 2) power = 15;
                            else if (act_idx == 3) power = 10;
                            else if (act_idx == 4) power = 5;
                            
                            state.curses[me][static_cast<int>(CurseType::CURSE_FOG)] = true;
                            if (power > 0) {
                                state.current_phase = GamePhase::PHASE_DEFENSE;
                                state.attacker_id = opp;
                                state.defender_id = me;
                                state.current_actor_id = me;
                                state.pending_attack_power = power;
                                state.pending_attack_element = ELEM_WATER;
                                state.pending_absorption = false;
                                state.pending_is_group_attack = (act_idx < 4);
                                state.turn_end_state = 5;
                                return true;
                            }
                        }
                        else if (g_id == 3) { // 木星神
                            int power = 0;
                            if (act_idx == 1) power = 15;
                            else if (act_idx == 2) power = 10;
                            else if (act_idx == 3) power = 5;
                            else if (act_idx == 5) power = 5;
                            
                            state.curses[me][static_cast<int>(CurseType::CURSE_DREAM)] = true;
                            if (power > 0) {
                                state.current_phase = GamePhase::PHASE_DEFENSE;
                                state.attacker_id = opp;
                                state.defender_id = me;
                                state.current_actor_id = me;
                                state.pending_attack_power = power;
                                state.pending_attack_element = ELEM_WOOD;
                                state.pending_absorption = false;
                                state.pending_is_group_attack = false;
                                state.turn_end_state = 5;
                                return true;
                            }
                        }
                        else if (g_id == 4) { // 土星神
                            int power = 0;
                            if (act_idx == 1) power = 30;
                            else if (act_idx == 2) power = 25;
                            else if (act_idx == 3) power = 20;
                            else if (act_idx == 4) power = 15;
                            else power = 10;
                            
                            state.current_phase = GamePhase::PHASE_DEFENSE;
                            state.attacker_id = opp;
                            state.defender_id = me;
                            state.current_actor_id = me;
                            state.pending_attack_power = power;
                            state.pending_attack_element = ELEM_STONE;
                            state.pending_absorption = false;
                            state.pending_is_group_attack = false;
                            state.turn_end_state = 5;
                            return true;
                        }
                        else if (g_id == 5) { // 天王神
                            int power = 0;
                            if (act_idx == 1) power = 20;
                            else if (act_idx == 2) power = 15;
                            else if (act_idx == 3) power = 10;
                            else if (act_idx == 4) power = 5;
                            
                            state.curses[me][static_cast<int>(CurseType::CURSE_FLASH)] = true;
                            if (power > 0) {
                                state.current_phase = GamePhase::PHASE_DEFENSE;
                                state.attacker_id = opp;
                                state.defender_id = me;
                                state.current_actor_id = me;
                                state.pending_attack_power = power;
                                state.pending_attack_element = ELEM_NONE;
                                state.pending_absorption = false;
                                state.pending_is_group_attack = (act_idx < 4);
                                state.turn_end_state = 5;
                                return true;
                            }
                        }
                        else if (g_id == 6) { // 冥王神
                            int power = 0;
                            if (act_idx == 1) power = 25;
                            else if (act_idx == 2) power = 20;
                            else if (act_idx == 3) power = 15;
                            else if (act_idx == 4) power = 10;
                            else power = 5;
                            
                            state.current_phase = GamePhase::PHASE_DEFENSE;
                            state.attacker_id = opp;
                            state.defender_id = me;
                            state.current_actor_id = me;
                            state.pending_attack_power = power;
                            state.pending_attack_element = ELEM_DARKNESS;
                            state.pending_absorption = false;
                            state.pending_is_group_attack = false;
                            state.turn_end_state = 5;
                            return true;
                        }
                        else if (g_id == 7) { // 海王神
                            if (act_idx == 1) state.hp[opp] = std::min(99, state.hp[opp] + 25);
                            else if (act_idx == 2) state.hp[opp] = std::min(99, state.hp[opp] + 15);
                            else if (act_idx == 3) state.mp[opp] = std::min(99, state.mp[opp] + 20);
                            else if (act_idx == 4) state.mp[opp] = std::min(99, state.mp[opp] + 10);
                            else {
                                state.sickness[opp] = 0;
                                for (int j = 0; j < 4; ++j) state.curses[opp][j] = false;
                            }
                        }
                        else if (g_id == 8) { // 金星神
                            int drain = 0;
                            if (act_idx == 1) drain = 15;
                            else if (act_idx == 2) drain = 10;
                            else if (act_idx == 3) drain = 8;
                            else if (act_idx == 4) drain = 5;
                            else drain = 2;
                            
                            int total_paid = 0;
                            if (state.money[me] >= drain) {
                                state.money[me] -= drain;
                                total_paid = drain;
                            } else {
                                total_paid += state.money[me];
                                int remaining = drain - state.money[me];
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
                            
                            if (state.hp[me] == 0) {
                                bool paused = run_death_check(state);
                                if (paused) {
                                    state.turn_end_state = 5;
                                    return true;
                                }
                            }
                        }
                        else if (g_id == 9) { // 地球神
                            draw_card_to_hand(state, opp);
                        }
                        else if (g_id == 10) { // 月神
                            Element random_elem = static_cast<Element>(std::uniform_int_distribution<int>(ELEM_FIRE, ELEM_DARKNESS)(state.rng));
                            state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
                            state.attacker_id = opp;
                            state.defender_id = me;
                            state.current_actor_id = me;
                            state.pending_attack_power = 10;
                            state.pending_attack_element = random_elem;
                            state.pending_absorption = false;
                            state.pending_is_group_attack = false;
                            state.turn_end_state = 5;
                            return true;
                        }
                    }
                }
                state.turn_end_state = 5;
                break;
            }
            case 5: { // クリーンアップおよびターン移行
                if (state.hp[0] == 0 || state.hp[1] == 0) {
                    bool paused = run_death_check(state);
                    if (paused) return true;
                }
                cleanup_phase_end(state);
                state.turn_end_state = 0;
                state.heaven_seizure_occurred[0] = false;
                state.heaven_seizure_occurred[1] = false;
                state.current_turn++;
                state.current_actor_id = state.current_turn % 2;
                state.current_phase = GamePhase::PHASE_MAIN;
                return false;
            }
        }
    }
    return false;
}
