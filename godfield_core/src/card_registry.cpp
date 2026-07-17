#include "game_logic.h"
#include "game_logic_internal.h"
#include <cstring>
#include <iostream>
#include <stdexcept>

// ============================================================================
// グローバル変数の実体定義 / Global Variable Instantiations
// ============================================================================

std::vector<CardFeatures> g_card_registry;
std::vector<std::string> g_card_names;
std::discrete_distribution<int> g_drop_distribution;

/**
 * @brief Python側から渡されたカードデータリストを解析し、C++のグローバルレジストリ（g_card_registry）に登録します。
 *        同時に、カード出現の確率分布（g_drop_distribution）を生成します。
 *
 * @param cards Pythonのリストオブジェクト。各要素は辞書型で、カードの属性（type, usage_timing, price, drop_rate等）を保持。
 */
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

/**
 * @brief ゲーム中に山札から新しくカードを引きます。
 *        出現確率（drop_rateの重み）に従ってランダムにカードIDが選ばれます。
 *
 * @param rng 乱数生成器（std::mt19937）への参照。
 * @return 抽選されたカードID（0以上の整数）。
 * @throw std::runtime_error カードレジストリが初期化されていない場合にスローされます。
 */
int draw_card(std::mt19937 &rng) {
    if (g_card_registry.empty()) {
        throw std::runtime_error("Cannot draw card: registry is empty. Call init_game_logic first.");
    }
    return g_drop_distribution(rng);
}

/**
 * @brief 登録されているカードの総数（レジストリサイズ）を返します。
 * @return カード種類数。
 */
int get_registry_size() {
    return static_cast<int>(g_card_registry.size());
}

/**
 * @brief カードIDに対応するカード名を取得します。IDが範囲外の場合は空文字列を返します。
 * @param card_id 対象のカードID。
 * @return カード名の文字列。
 */
std::string get_card_name(int card_id) {
    if (card_id < 0 || card_id >= static_cast<int>(g_card_names.size())) {
        return "";
    }
    return g_card_names[card_id];
}
