#include "game_logic.h"
#include "generated_card_ids.h"
#include <iostream>
#include <stdexcept>
#include <algorithm>
#include <cstring>
#include <vector>

std::vector<CardFeatures> g_card_registry;
std::vector<std::string> g_card_names;
std::discrete_distribution<int> g_drop_distribution;

void init_game_logic(pybind11::list cards) {
    g_card_registry.clear();
    g_card_names.clear();
    std::vector<int> weights;

    for (auto item : cards) {
        pybind11::dict card = item.cast<pybind11::dict>();
        CardFeatures f = {};
        std::memset(&f, 0, sizeof(f));

        std::string type = card["type"].cast<std::string>();
        f.is_weapon = (type == "weapon");
        f.is_defense = (type == "defense");
        f.is_miracle = (type == "miracle");
        f.is_sundry = (type == "sundry");
        f.is_deal = (type == "deal");

        pybind11::list timings = card["usage_timing"].cast<pybind11::list>();
        for (auto timing : timings) {
            std::string t = timing.cast<std::string>();
            if (t == "main_atk_phase") f.usage_timing |= TIMING_MAIN_ATK;
            else if (t == "main_miracle_phase") f.usage_timing |= TIMING_MAIN_MIRACLE;
            else if (t == "main_sundry_phase") f.usage_timing |= TIMING_MAIN_SUNDRY;
            else if (t == "main_deal_phase") f.usage_timing |= TIMING_MAIN_DEAL;
            else if (t == "atk_plus_phase") f.usage_timing |= TIMING_ATK_PLUS;
            else if (t == "miracle_plus_phase") f.usage_timing |= TIMING_MIRACLE_PLUS;
            else if (t == "atk_defence_phase") f.usage_timing |= TIMING_ATK_DEFENCE;
            else if (t == "miracle_defence_phase") f.usage_timing |= TIMING_MIRACLE_DEFENCE;
        }

        f.price = card.contains("price") ? card["price"].cast<int>() : 0;
        f.drop_rate = card.contains("drop_rate") ? card["drop_rate"].cast<int>() : 0;
        f.attack_power = card.contains("attack_power") ? card["attack_power"].cast<int>() : 0;
        f.defense_power = card.contains("defense_power") ? card["defense_power"].cast<int>() : 0;
        f.accuracy = card.contains("accuracy") ? card["accuracy"].cast<int>() : 100;
        f.mp_cost = card.contains("mp_cost") ? card["mp_cost"].cast<int>() : 0;
        f.hp_recovery = card.contains("hp_recovery") ? card["hp_recovery"].cast<int>() : 0;
        f.mp_recovery = card.contains("mp_recovery") ? card["mp_recovery"].cast<int>() : 0;

        if (card.contains("element")) {
            std::string el = card["element"].cast<std::string>();
            if (el == "火") f.element = ELEM_FIRE;
            else if (el == "水") f.element = ELEM_WATER;
            else if (el == "木") f.element = ELEM_WOOD;
            else if (el == "土") f.element = ELEM_STONE;
            else if (el == "光") f.element = ELEM_LIGHT;
            else if (el == "闇") f.element = ELEM_DARKNESS;
            else f.element = ELEM_NONE;
        }

        if (card.contains("reaction_type")) {
            std::string rt = card["reaction_type"].cast<std::string>();
            if (rt == "bounce") f.reaction_type = REACTION_BOUNCE;
            else if (rt == "reflect") f.reaction_type = REACTION_REFLECT;
            else if (rt == "block") f.reaction_type = REACTION_BLOCK;
        }

        if (card.contains("hit_curse")) {
            std::string hc = card["hit_curse"].cast<std::string>();
            if (hc == "fog") f.hit_curse = CURSE_FOG;
            else if (hc == "flash") f.hit_curse = CURSE_FLASH;
            else if (hc == "dark_cloud" || hc == "dark cloud") f.hit_curse = CURSE_DARK_CLOUD;
            else if (hc == "dream") f.hit_curse = CURSE_DREAM;
            else if (hc == "cold") f.hit_curse = CURSE_COLD;
            else if (hc == "fever") f.hit_curse = CURSE_FEVER;
            else if (hc == "hell") f.hit_curse = CURSE_HELL;
            else if (hc == "heaven") f.hit_curse = CURSE_HEAVEN;
        }

        g_card_registry.push_back(f);
        g_card_names.push_back(card["name"].cast<std::string>());
        weights.push_back(f.drop_rate);
    }

    g_drop_distribution = std::discrete_distribution<int>(weights.begin(), weights.end());
    std::cout << "Successfully loaded " << g_card_registry.size() << " cards into game_logic registry." << std::endl;
}

int draw_card(std::mt19937 &rng) {
    if (g_card_registry.empty()) {
        throw std::runtime_error("Cannot draw card: registry is empty. Call init_game_logic first.");
    }
    return g_drop_distribution(rng);
}

int get_registry_size() { return static_cast<int>(g_card_registry.size()); }

std::string get_card_name(int card_id) {
    if (card_id < 0 || card_id >= g_card_names.size())
        return "";
    return g_card_names[card_id];
}

static void cleanup_phase_end(InternalState &state) {
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
            for (int h = 0; h < MAX_HAND_SIZE; ++h) {
                if (state.true_hand[p][h] == CARD_EMPTY) {
                    state.true_hand[p][h] = draw_card(state.rng);
                    state.is_known_to_opp[p][h] = false;
                    state.is_used[p][h] = false;
                    state.is_deployed[p][h] = false;
                    state.miracle_used_this_turn[p][h] = false;
                    break;
                }
            }
        }
        state.num_staged_cards[p] = 0;
    }
    state.pending_attack_power = 0;
    state.pending_attack_element = ELEM_NONE;
    state.pending_absorption = false;
}

static void discard_card_for_pray(InternalState &state, int me) {
    std::vector<int> candidate_indices;
    int empty_slot_idx = -1;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[me][i] == CARD_EMPTY) {
            empty_slot_idx = i;
            break;
        }
        if (!state.is_used[me][i]) {
            candidate_indices.push_back(i);
        }
    }

    if (empty_slot_idx != -1) {
        state.true_hand[me][empty_slot_idx] = draw_card(state.rng);
        state.is_known_to_opp[me][empty_slot_idx] = false;
        state.is_used[me][empty_slot_idx] = false;
    } else {
        if (candidate_indices.empty()) return;

        std::uniform_int_distribution<int> dist(0, (int)candidate_indices.size() - 1);
        int initial_pick_idx = candidate_indices[dist(state.rng)];
        int target_card_id = state.true_hand[me][initial_pick_idx];

        int best_idx = initial_pick_idx;
        for (int idx : candidate_indices) {
            if (state.true_hand[me][idx] == target_card_id && state.is_known_to_opp[me][idx]) {
                best_idx = idx;
                break;
            }
        }

        state.true_hand[me][best_idx] = draw_card(state.rng);
        state.is_known_to_opp[me][best_idx] = false;
        state.is_used[me][best_idx] = false;
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
static std::vector<int> get_staged_card_ids(const InternalState &state, int player) {
    std::vector<int> ids;
    for (int i = 0; i < state.num_staged_cards[player]; ++i) {
        ids.push_back(state.true_hand[player][state.staged_cards[player][i]]);
    }
    return ids;
}

// 効果適用を一元化。ゴッドフィールドの原作仕様に基づく。
static void apply_card_effects_to_target(InternalState &state, int target_id, const std::vector<int>& used_card_ids) {
    int hp_diff = 0;
    int mp_diff = 0;
    for (int card_id : used_card_ids) {
        CardFeatures &f = g_card_registry[card_id];
        hp_diff += f.hp_recovery;
        mp_diff += f.mp_recovery;

        // 状態異常付与 (奇跡などの状態異常効果は相手にも適用可能)
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

        // --- 特殊回復カード ---
        if (card_id == ID_TONE) {
            state.sickness[target_id] = (state.sickness[target_id] == 1 || state.sickness[target_id] == 2) ? 0 : state.sickness[target_id];
            state.curses[target_id][0] = false;
            state.curses[target_id][1] = false;
        } else if (card_id == ID_SONG || card_id == ID_HEART_SHELL) {
            state.sickness[target_id] = 0;
            for (int j = 0; j < 4; ++j) state.curses[target_id][j] = false;
        } else if (card_id == ID_SMILE_SHELL) {
            if (state.sickness[target_id] == 1 || state.sickness[target_id] == 2) state.sickness[target_id] = 0;
            state.curses[target_id][0] = false;
            state.curses[target_id][1] = false;
        }

        // --- その他の特殊効果 ---
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

// ---------------------------------------------------------------------------
// Phase Step Functions
// ---------------------------------------------------------------------------

static void step_phase_main(InternalState &state, ActionType action, int me, int opp) {
    if (action == ACTION_PRAY) {
        discard_card_for_pray(state, me);
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
                // 両替は即時移行
                state.exchange_sum = state.hp[me] + state.mp[me] + state.money[me];
                state.exchange_hp = -1;
                state.current_phase = GamePhase::PHASE_EXCHANGE_HP;
                return;
            } else if (f.usage_timing & TIMING_MAIN_ATK) {
                state.current_phase = GamePhase::PHASE_ATTACK_PLUS;
                state.attacker_id = me;
                return;
            } else if (f.usage_timing & TIMING_MAIN_MIRACLE) {
                state.current_phase = GamePhase::PHASE_MIRACLE_PLUS;
                state.attacker_id = me;
                return;
            }
            // 雑貨、売る、買う はそのまま PHASE_MAIN に留まり TARGET を待つ
        }
    } else if (action == ACTION_TARGET_SELF || action == ACTION_TARGET_OPP) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;
        if (state.num_staged_cards[me] > 0) {
            int card_id = state.true_hand[me][state.staged_cards[me][0]];
            if (card_id == ID_SELL) {
                state.attacker_id = me;
                state.defender_id = target;
                state.current_phase = GamePhase::PHASE_SELL;
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
                    state.current_phase = GamePhase::PHASE_BUY;
                    std::vector<int> candidates;
                    for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                        if (state.true_hand[opp][j] != CARD_EMPTY && !state.is_deployed[opp][j]) {
                            candidates.push_back(j);
                        }
                    }
                    if (!candidates.empty()) {
                        std::shuffle(candidates.begin(), candidates.end(), state.rng);
                        int revealed_idx = candidates[0];
                        state.is_known_to_opp[opp][revealed_idx] = true;
                        state.staged_cards[opp][0] = revealed_idx;
                        state.num_staged_cards[opp] = 1;
                    } else {
                        state.num_staged_cards[me] = 0;
                        state.current_phase = GamePhase::PHASE_END;
                    }
                }
                return;
            }
            
            // 雑貨カードの効果適用
            auto used_cards = get_staged_card_ids(state, me);
            apply_card_effects_to_target(state, target, used_cards);
        }
        
        state.num_staged_cards[me] = 0;
        if (!state.is_done) {
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

static void step_phase_attack_plus(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

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
        }

        Element atk_element = ELEM_NONE;
        if (has_non_element || has_multiple_different_elements) atk_element = ELEM_NONE;
        else if (base_element != ELEM_NONE) atk_element = base_element;
        else if (has_light) atk_element = ELEM_LIGHT;

        state.pending_attack_power = total_atk;
        state.pending_attack_element = atk_element;
        state.defender_id = target;

        if (target == me) {
            state.hp[me] = std::clamp(state.hp[me] - total_atk, 0, 99);
            if (state.hp[me] <= 0) {
                state.hp[me] = 0;
                state.is_done = true;
                state.p0_reward = (me == 0) ? -1.0f : 1.0f;
                state.p1_reward = (me == 1) ? -1.0f : 1.0f;
            } else {
                auto used_cards = get_staged_card_ids(state, me);
                apply_card_effects_to_target(state, me, used_cards);
            }
            state.current_phase = GamePhase::PHASE_END;
        } else {
            state.current_actor_id = target;
            state.current_phase = GamePhase::PHASE_DEFENSE;
        }
    }
}

static void step_phase_defense(InternalState &state, ActionType action, int me, int opp) {
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

            // 攻撃が通った場合(または当たった場合)、武器の付随効果（hit_curse等）を適用する
            auto attacker_used_cards = get_staged_card_ids(state, state.attacker_id);
            apply_card_effects_to_target(state, me, attacker_used_cards);
        }

        state.current_phase = GamePhase::PHASE_END;
    }
}

static void step_phase_miracle_plus(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            state.staged_cards[me][state.num_staged_cards[me]++] = idx;
            state.is_used[me][idx] = true;
        }
    } else if (action == ACTION_TARGET_OPP || action == ACTION_TARGET_SELF) {
        int target = (action == ACTION_TARGET_SELF) ? me : opp;

        int total_mp_cost = 0;
        int total_atk = 0;
        Element base_element = ELEM_NONE;
        bool has_non_element = false, has_light = false, has_multiple_different_elements = false;
        bool has_spiritual_doll = false;

        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            if (state.true_hand[me][state.staged_cards[me][i]] == ID_SPIRITUAL_DOLL) {
                has_spiritual_doll = true;
            }
        }
        
        for (int i = 0; i < state.num_staged_cards[me]; ++i) {
            int h_idx = state.staged_cards[me][i];
            state.is_known_to_opp[me][h_idx] = true;
            int card_id = state.true_hand[me][h_idx];
            CardFeatures &f = g_card_registry[card_id];
            
            if (!has_spiritual_doll) total_mp_cost += f.mp_cost;
            total_atk += f.attack_power;
            
            Element e = f.element;
            if (e == ELEM_NONE) has_non_element = true;
            else if (e == ELEM_LIGHT) has_light = true;
            else {
                if (base_element == ELEM_NONE) base_element = e;
                else if (base_element != e) has_multiple_different_elements = true;
            }
            
            if (card_id == ID_ABSORPTION) state.pending_absorption = true;
        }
        
        state.mp[me] = std::clamp(state.mp[me] - total_mp_cost, 0, 99);
        
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
                state.current_phase = GamePhase::PHASE_MIRACLE_DEFENSE;
            }
        }
    }
}

static void step_phase_miracle_defense(InternalState &state, ActionType action, int me, int opp) {
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

        // Apply healing/curse effects of the miracle to the target (intended by GodField specification)
        auto attacker_used_cards = get_staged_card_ids(state, attacker);
        apply_card_effects_to_target(state, target, attacker_used_cards);
        
        if (!state.is_done) {
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

static void step_phase_sell(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        int idx = action - ACTION_SELECT_HAND_0;
        int card_id = state.true_hand[me][idx];
        if (card_id != CARD_EMPTY && !state.is_deployed[me][idx] && !state.is_used[me][idx]) {
            CardFeatures &f_sold = g_card_registry[card_id];
            int price = f_sold.price;
            int seller = me;
            int buyer = state.defender_id;

            int remaining_pay = price;
            int money_paid = std::min(state.money[buyer], remaining_pay);
            state.money[buyer] -= money_paid;
            remaining_pay -= money_paid;

            if (remaining_pay > 0) {
                int mp_paid = std::min(state.mp[buyer], remaining_pay);
                state.mp[buyer] -= mp_paid;
                remaining_pay -= mp_paid;
            }

            if (remaining_pay > 0) {
                int hp_paid = std::min(state.hp[buyer], remaining_pay);
                state.hp[buyer] -= hp_paid;
                remaining_pay -= hp_paid;
            }

            state.money[seller] = std::clamp(state.money[seller] + price, 0, 99);
            state.true_hand[seller][idx] = CARD_EMPTY;
            state.is_known_to_opp[seller][idx] = false;
            state.is_used[seller][idx] = false;

            int empty_slot = -1;
            for (int j = 0; j < MAX_HAND_SIZE; ++j) {
                if (state.true_hand[buyer][j] == CARD_EMPTY) {
                    empty_slot = j;
                    break;
                }
            }

            if (empty_slot != -1) {
                state.true_hand[buyer][empty_slot] = card_id;
                state.is_known_to_opp[buyer][empty_slot] = false;
                state.is_used[buyer][empty_slot] = false;
            } else {
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
                    state.is_known_to_opp[buyer][replace_idx] = false;
                    state.is_deployed[buyer][replace_idx] = false;
                    state.miracle_used_this_turn[buyer][replace_idx] = false;
                    state.is_used[buyer][replace_idx] = false;
                }
            }

            if (state.hp[buyer] <= 0) {
                state.hp[buyer] = 0;
                state.is_done = true;
                state.p0_reward = (buyer == 0) ? -1.0f : 1.0f;
                state.p1_reward = (buyer == 1) ? -1.0f : 1.0f;
                return;
            }

            state.num_staged_cards[me] = 0;
            state.current_phase = GamePhase::PHASE_END;
        }
    }
}

static void step_phase_buy(InternalState &state, ActionType action, int me, int opp) {
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
                state.is_known_to_opp[buyer][empty_slot] = false;
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
                    state.is_known_to_opp[buyer][replace_idx] = false;
                    state.is_deployed[buyer][replace_idx] = false;
                    state.miracle_used_this_turn[buyer][replace_idx] = false;
                    state.is_used[buyer][replace_idx] = false;
                }
            }
        }

        state.staged_cards[seller][0] = 0;
        state.num_staged_cards[seller] = 0;
        state.num_staged_cards[me] = 0;
        state.current_phase = GamePhase::PHASE_END;
    }
}

static void step_phase_exchange(InternalState &state, ActionType action, int me, int opp) {
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

static void step_phase_discard(InternalState &state, ActionType action, int me, int opp) {
    if (action >= ACTION_SELECT_HAND_0 && action <= ACTION_SELECT_HAND_17) {
        if (state.num_staged_cards[me] < MAX_HAND_SIZE) {
            int idx = action - ACTION_SELECT_HAND_0;
            int card_id = state.true_hand[me][idx];
            if (card_id != CARD_EMPTY && !state.is_deployed[me][idx] && !state.is_used[me][idx]) {
                bool is_discardable = !g_card_registry[card_id].is_weapon && card_id != ID_SUN_AMULET && card_id != ID_DANGEROUS_MORTAR;
                if (is_discardable) {
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

void step_game(InternalState& state, ActionType action) {
    if (state.is_done) return;

    int me = state.current_actor_id;
    int opp = 1 - me;

    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    if (action < 0 || action >= ACTION_SPACE_SIZE || !legal_actions[action]) return;

    switch (state.current_phase) {
        case GamePhase::PHASE_MAIN:
            step_phase_main(state, action, me, opp);
            break;
        case GamePhase::PHASE_ATTACK_PLUS:
            step_phase_attack_plus(state, action, me, opp);
            break;
        case GamePhase::PHASE_DEFENSE:
            step_phase_defense(state, action, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_PLUS:
            step_phase_miracle_plus(state, action, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_DEFENSE:
            step_phase_miracle_defense(state, action, me, opp);
            break;
        case GamePhase::PHASE_SELL:
            step_phase_sell(state, action, me, opp);
            break;
        case GamePhase::PHASE_BUY:
            step_phase_buy(state, action, me, opp);
            break;
        case GamePhase::PHASE_EXCHANGE_HP:
        case GamePhase::PHASE_EXCHANGE_MP:
            step_phase_exchange(state, action, me, opp);
            break;
        case GamePhase::PHASE_DISCARD:
            step_phase_discard(state, action, me, opp);
            break;
        default:
            break;
    }

    while (!state.is_done) {
        if (state.current_phase == GamePhase::PHASE_END) {
            cleanup_phase_end(state);
            state.current_turn++;
            state.current_actor_id = state.current_turn % 2;
            state.current_phase = GamePhase::PHASE_MAIN;
        } else {
            break;
        }
    }
}

// ---------------------------------------------------------------------------
// Legal Action Helpers
// ---------------------------------------------------------------------------

static void legal_phase_main(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    bool has_weapon = false;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (g_card_registry[state.true_hand[me][i]].is_weapon) has_weapon = true;
        }
    }
    if (!has_weapon) legal_actions[ACTION_PRAY] = true;

    bool has_discardable = false;
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.true_hand[me][i];
        if (card_id != CARD_EMPTY && !state.is_used[me][i]) {
            if (!g_card_registry[card_id].is_weapon && card_id != ID_SUN_AMULET && card_id != ID_DANGEROUS_MORTAR) {
                has_discardable = true;
                break;
            }
        }
    }
    if (has_discardable) legal_actions[ACTION_DISCARD] = true;

    if (state.num_staged_cards[me] == 0) {
        bool has_spiritual_doll = false;
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (!state.is_used[me][i] && state.true_hand[me][i] == ID_SPIRITUAL_DOLL) {
                has_spiritual_doll = true;
                break;
            }
        }

        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
                if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
                CardFeatures &f = g_card_registry[state.true_hand[me][i]];
                if (f.is_miracle && !has_spiritual_doll && state.mp[me] < f.mp_cost) continue;
                if (!f.is_miracle && state.mp[me] < f.mp_cost) continue;
                
                if ((f.usage_timing & TIMING_MAIN_SUNDRY) || (f.usage_timing & TIMING_MAIN_ATK) ||
                    (f.usage_timing & TIMING_MAIN_MIRACLE) || (f.usage_timing & TIMING_MAIN_DEAL)) {
                    legal_actions[ACTION_SELECT_HAND_0 + i] = true;
                }
            }
        }
    } else {
        int staged_card_id = state.true_hand[me][state.staged_cards[me][0]];
        if (staged_card_id != ID_EXCHANGE) { // Exchange transitions immediately, so this is just in case for Sundry/Buy/Sell
            legal_actions[ACTION_TARGET_SELF] = true;
            legal_actions[ACTION_TARGET_OPP] = true;
        }
    }
}

static void legal_phase_attack_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    int current_mp_cost = 0;
    bool has_unstable_accuracy = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        CardFeatures &f = g_card_registry[state.true_hand[me][state.staged_cards[me][i]]];
        current_mp_cost += f.mp_cost;
        if (f.accuracy < 100) has_unstable_accuracy = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            CardFeatures &f = g_card_registry[state.true_hand[me][i]];
            if (state.mp[me] < current_mp_cost + f.mp_cost) continue;

            if (f.usage_timing & TIMING_ATK_PLUS) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }

    legal_actions[ACTION_TARGET_OPP] = true;
    legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy;
}

static void legal_phase_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
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

static void legal_phase_miracle_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    int current_mp_cost = 0;
    bool has_unstable_accuracy = false;
    bool has_spiritual_doll = false;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = state.true_hand[me][state.staged_cards[me][i]];
        CardFeatures &f = g_card_registry[card_id];
        current_mp_cost += f.mp_cost;
        if (f.accuracy < 100) has_unstable_accuracy = true;
        if (card_id == ID_SPIRITUAL_DOLL) has_spiritual_doll = true;
    }

    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (!state.is_used[me][i] && state.true_hand[me][i] != CARD_EMPTY) {
            if (state.is_deployed[me][i] && state.miracle_used_this_turn[me][i]) continue;
            CardFeatures &f = g_card_registry[state.true_hand[me][i]];
            int next_mp_cost = (has_spiritual_doll || state.true_hand[me][i] == ID_SPIRITUAL_DOLL) ? 0 : (current_mp_cost + f.mp_cost);
            if (state.mp[me] < next_mp_cost) continue;

            if (f.usage_timing & TIMING_MIRACLE_PLUS) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }

    legal_actions[ACTION_TARGET_OPP] = true;
    legal_actions[ACTION_TARGET_SELF] = !has_unstable_accuracy;
}

static void legal_phase_miracle_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
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

static void legal_phase_sell(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[me][i] != CARD_EMPTY && !state.is_deployed[me][i] && !state.is_used[me][i]) {
            legal_actions[ACTION_SELECT_HAND_0 + i] = true;
        }
    }
}

static void legal_phase_buy(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    legal_actions[ACTION_DEAL_NO] = true;
    int revealed_idx = state.staged_cards[opp][0];
    int card_id = state.true_hand[opp][revealed_idx];
    CardFeatures &f = g_card_registry[card_id];
    if (state.money[me] >= f.price) {
        legal_actions[ACTION_DEAL_YES] = true;
    }
}

static void legal_phase_exchange(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    if (state.current_phase == GamePhase::PHASE_EXCHANGE_HP) {
        int sum = state.exchange_sum;
        for (int x = 1; x <= 99; ++x) { // HP should be at least 1 in general, but x=0 means death. We might allow 0 but let's stick to original which allowed 0.
            if (x <= sum && (sum - x) <= 198) {
                legal_actions[ACTION_NUM_0 + x] = true;
            }
        }
        // If x=0 is valid
        if (0 <= sum && (sum - 0) <= 198) {
             legal_actions[ACTION_NUM_0] = true;
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

static void legal_phase_discard(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp) {
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        int card_id = state.true_hand[me][i];
        if (card_id != CARD_EMPTY && !state.is_deployed[me][i] && !state.is_used[me][i]) {
            bool is_discardable = !g_card_registry[card_id].is_weapon && card_id != ID_SUN_AMULET && card_id != ID_DANGEROUS_MORTAR;
            if (is_discardable) {
                legal_actions[ACTION_SELECT_HAND_0 + i] = true;
            }
        }
    }
    if (state.num_staged_cards[me] > 0) {
        legal_actions[ACTION_CONFIRM] = true;
    }
}

void get_legal_actions(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE]) {
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) legal_actions[i] = false;
    if (state.is_done) return;

    int me = state.current_actor_id;
    int opp = 1 - me;

    switch (state.current_phase) {
        case GamePhase::PHASE_MAIN: legal_phase_main(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_ATTACK_PLUS: legal_phase_attack_plus(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_DEFENSE: legal_phase_defense(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_MIRACLE_PLUS: legal_phase_miracle_plus(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_MIRACLE_DEFENSE: legal_phase_miracle_defense(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_SELL: legal_phase_sell(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_BUY: legal_phase_buy(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_EXCHANGE_HP:
        case GamePhase::PHASE_EXCHANGE_MP: legal_phase_exchange(state, legal_actions, me, opp); break;
        case GamePhase::PHASE_DISCARD: legal_phase_discard(state, legal_actions, me, opp); break;
        default: break;
    }
}

void resolve_events(InternalState &state) {
    // Placeholder for event resolution
}
