#include "cards.h"
#include <unordered_map>

namespace godfield {

static std::unordered_map<int, Card> card_db = {
    {0, {0, "None", CardType::UNKNOWN, 0, 0, 0, 0, 0, 0}},
    {1, {1, "Wooden Sword", CardType::WEAPON, 1, 5, 0, 0, 0, 0}},
    {2, {2, "Leather Armor", CardType::ARMOR, 2, 0, 5, 0, 0, 0}},
    {3, {3, "Heal", CardType::MIRACLE, 3, 0, 0, 3, 0, 0}}
};

const Card& get_card(int id) {
    auto it = card_db.find(id);
    if (it != card_db.end()) return it->second;
    return card_db[0];
}

int get_random_card_in_group(int group_id) {
    // Placeholder for Dream state logic
    return 1;
}

}
