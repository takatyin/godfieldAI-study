#include "state.h"

namespace godfield {

void GameState::reset() {
    players[0].reset();
    players[1].reset();
    current_turn = 0;
    
    // Initial hands
    for(int i=0; i<5; ++i) {
        players[0].hand.push_back(1);
        players[1].hand.push_back(2);
    }
}

void GameState::step(int action_player_0[4], int action_player_1[4]) {
    // Placeholder implementation
    players[1].hp -= 1;
    current_turn++;
}

void GameState::get_observation(int player_id, float* out_obs) {
    int opp_id = 1 - player_id;
    PlayerState& me = players[player_id];
    PlayerState& opp = players[opp_id];
    
    int idx = 0;
    
    // My stats
    out_obs[idx++] = me.hp;
    out_obs[idx++] = me.mp;
    out_obs[idx++] = me.money;
    out_obs[idx++] = me.is_fog ? 1.0f : 0.0f;
    out_obs[idx++] = me.is_dream ? 1.0f : 0.0f;
    
    // My active miracles (fixed size 5)
    for(int i=0; i<5; ++i) {
        out_obs[idx++] = (i < me.active_miracles.size()) ? me.active_miracles[i] : 0;
    }
    
    // My hand (fixed size 10)
    for(int i=0; i<10; ++i) {
        int card_id = (i < me.hand.size()) ? me.hand[i] : 0;
        if (card_id != 0 && me.is_dream) {
            // Noise logic for dream state
        }
        out_obs[idx++] = card_id;
    }
    
    // Opponent stats
    if (opp.is_fog) {
        out_obs[idx++] = 0; // hp
        out_obs[idx++] = 0; // mp
        out_obs[idx++] = 0; // money
        out_obs[idx++] = 1; // is_fog
        out_obs[idx++] = 0; // is_dream
        for(int i=0; i<5; ++i) out_obs[idx++] = 0;
    } else {
        out_obs[idx++] = opp.hp;
        out_obs[idx++] = opp.mp;
        out_obs[idx++] = opp.money;
        out_obs[idx++] = opp.is_fog ? 1.0f : 0.0f;
        out_obs[idx++] = opp.is_dream ? 1.0f : 0.0f;
        for(int i=0; i<5; ++i) {
            out_obs[idx++] = (i < opp.active_miracles.size()) ? opp.active_miracles[i] : 0;
        }
    }
}

bool GameState::is_done() const {
    return players[0].hp <= 0 || players[1].hp <= 0 || current_turn > 100;
}

std::string GameState::get_state_json() const {
    // Simple manual JSON string building for visualizer
    std::string json = "{";
    json += "\"current_turn\": " + std::to_string(current_turn) + ", ";
    json += "\"players\": [";
    for(int i=0; i<2; ++i) {
        json += "{";
        json += "\"hp\": " + std::to_string(players[i].hp) + ", ";
        json += "\"mp\": " + std::to_string(players[i].mp) + ", ";
        json += "\"money\": " + std::to_string(players[i].money) + ", ";
        json += "\"is_fog\": " + std::to_string(players[i].is_fog) + ", ";
        json += "\"is_dream\": " + std::to_string(players[i].is_dream) + ", ";
        
        json += "\"hand\": [";
        for(size_t j=0; j<players[i].hand.size(); ++j) {
            json += std::to_string(players[i].hand[j]);
            if(j < players[i].hand.size() - 1) json += ", ";
        }
        json += "], ";
        
        json += "\"active_miracles\": [";
        for(size_t j=0; j<players[i].active_miracles.size(); ++j) {
            json += std::to_string(players[i].active_miracles[j]);
            if(j < players[i].active_miracles.size() - 1) json += ", ";
        }
        json += "]";
        
        json += "}";
        if(i == 0) json += ", ";
    }
    json += "]";
    json += "}";
    return json;
}

}
