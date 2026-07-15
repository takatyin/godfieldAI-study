#include "game_logic.h"
#include <iostream>
#include <stdexcept>
#include <cstring>

std::vector<CardFeatures> g_card_registry;
std::discrete_distribution<int> g_drop_distribution;

void init_game_logic(pybind11::list cards) {
    g_card_registry.clear();
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
        
        if (card.contains("element")) {
            std::string el = card["element"].cast<std::string>();
            if (el == "火") f.element = ELEM_FIRE;
            else if (el == "水") f.element = ELEM_WATER;
            else if (el == "木") f.element = ELEM_WOOD;
            else if (el == "土") f.element = ELEM_EARTH;
            else if (el == "光") f.element = ELEM_LIGHT;
            else if (el == "闇") f.element = ELEM_DARK;
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
            else if (hc == "dark_cloud") f.hit_curse = CURSE_DARK_CLOUD;
            else if (hc == "dream") f.hit_curse = CURSE_DREAM;
            else if (hc == "cold") f.hit_curse = CURSE_COLD;
            else if (hc == "fever") f.hit_curse = CURSE_FEVER;
            else if (hc == "hell") f.hit_curse = CURSE_HELL;
            else if (hc == "heaven") f.hit_curse = CURSE_HEAVEN;
        }
        
        g_card_registry.push_back(f);
        weights.push_back(f.drop_rate);
    }
    
    g_drop_distribution = std::discrete_distribution<int>(weights.begin(), weights.end());
    std::cout << "Successfully loaded " << g_card_registry.size() << " cards into game_logic registry." << std::endl;
}

int draw_card(std::mt19937& rng) {
    if (g_card_registry.empty()) {
        throw std::runtime_error("Card registry not initialized! Call init_game_logic first.");
    }
    return g_drop_distribution(rng);
}

void step_game(InternalState& state, int action) {
    if (state.is_done) return;
    
    // For now, this is just a dummy implementation to verify the structure.
    // In the future, this will handle the complex GamePhase state machine.
    
    // Example: action 18 is "execute / attack"
    if (action == 18) {
        state.current_phase = GamePhase::STATE_4_ATK_DEF;
        state.attacker_id = state.current_actor_id;
        state.defender_id = 1 - state.current_actor_id;
        state.pending_attack_power = 1; // dummy damage
        
        // Switch actor to defender
        state.current_actor_id = state.defender_id;
    }
}

void resolve_events(InternalState& state) {
    // Placeholder for event resolution
}
