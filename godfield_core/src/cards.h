#pragma once
#include <vector>
#include <string>

namespace godfield {

enum class CardType {
    WEAPON,
    ARMOR,
    MIRACLE,
    ARTIFACT,
    UNKNOWN
};

struct Card {
    int id;
    std::string name;
    CardType type;
    int group_id; // For Dream state replacement
    
    // Generic fields
    int attack;
    int defense;
    int mp_cost;
    int hp_cost;
    int money_cost;
};

const Card& get_card(int id);
int get_random_card_in_group(int group_id);

}
