#pragma once
#include <vector>
#include "cards.h"

namespace godfield {

struct PlayerState {
    int hp;
    int mp;
    int money;
    
    bool is_fog;
    bool is_dream;
    
    std::vector<int> hand;
    std::vector<int> active_miracles;
    
    void reset() {
        hp = 40;
        mp = 10;
        money = 0;
        is_fog = false;
        is_dream = false;
        hand.clear();
        active_miracles.clear();
    }
};

class GameState {
public:
    PlayerState players[2];
    int current_turn;
    
    void reset();
    void step(int action_player_0[4], int action_player_1[4]);
    void get_observation(int player_id, float* out_obs);
    std::string get_state_json() const; // For visualization
    bool is_done() const;
};

}
