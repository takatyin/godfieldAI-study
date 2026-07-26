#include "game_logic.h"
#include "game_logic_internal.h"
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
#include <atomic>

// ============================================================================
// グローバル変数の実体定義 / Global Variable Instantiations
// ============================================================================

std::vector<CardFeatures> g_card_registry;
std::vector<std::string> g_card_names;
std::discrete_distribution<int> g_drop_distribution;

// g_drop_distribution が作り直された回数。draw_card() のスレッドローカルなコピーが
// 古くなっていないかを判定するために使う（init_game_logic は再呼び出しされうる）。
static std::atomic<uint64_t> g_distribution_generation{0};

static const std::unordered_map<std::string, CardType> type_map = {
    {"weapon", CardType::WEAPON},
    {"defense", CardType::DEFENSE},
    {"miracle", CardType::MIRACLE},
    {"sundry", CardType::SUNDRY},
    {"deal", CardType::DEAL},
    {"devil", CardType::DEVIL},
    {"phenomena", CardType::PHENOMENA},
    {"guardian", CardType::GUARDIAN}
};

static const std::unordered_map<std::string, uint32_t> timing_map = {
    {"main_atk_phase", TIMING_MAIN_ATK},
    {"main_miracle_phase", TIMING_MAIN_MIRACLE},
    {"main_sundry_phase", TIMING_MAIN_SUNDRY},
    {"main_deal_phase", TIMING_MAIN_DEAL},
    {"atk_plus_phase", TIMING_ATK_PLUS},
    {"miracle_plus_phase", TIMING_MIRACLE_PLUS},
    {"atk_defence_phase", TIMING_ATK_DEFENCE},
    {"miracle_defence_phase", TIMING_MIRACLE_DEFENCE},
    {"guardian_phase", TIMING_GUARDIAN}
};

static const std::unordered_map<std::string, Element> element_map = {
    {"火", ELEM_FIRE},
    {"水", ELEM_WATER},
    {"木", ELEM_WOOD},
    {"土", ELEM_STONE},
    {"光", ELEM_LIGHT},
    {"闇", ELEM_DARKNESS}
};

static const std::unordered_map<std::string, ReactionType> reaction_map = {
    {"bounce", REACTION_BOUNCE},
    {"reflect", REACTION_REFLECT},
    {"block", REACTION_BLOCK}
};

static const std::unordered_map<std::string, HitCurse> curse_map = {
    {"fog", CURSE_FOG},
    {"flash", CURSE_FLASH},
    {"dark_cloud", CURSE_DARK_CLOUD},
    {"dark cloud", CURSE_DARK_CLOUD},
    {"dream", CURSE_DREAM},
    {"cold", CURSE_COLD},
    {"fever", CURSE_FEVER},
    {"hell", CURSE_HELL},
    {"heaven", CURSE_HEAVEN}
};

/**
 * @brief Python側から渡されたカードデータリストを解析し、C++のグローバルレジストリ（g_card_registry）に登録します。
 *        同時に、カード出現の確率分布（g_drop_distribution）を生成します。
 *
 * @param cards Pythonのリストオブジェクト。各要素は辞書型で、カードの属性（type, usage_timing, price, drop_rate等）を保持。
 */
void init_game_logic(const pybind11::list &cards) {
    g_card_registry.clear();
    g_card_names.clear();
    std::vector<int> weights;

    for (auto item : cards) {
        pybind11::dict card = item.cast<pybind11::dict>();
        CardFeatures f = {};

        std::string type = card.contains("type") ? card["type"].cast<std::string>() : "sundry";
        auto type_it = type_map.find(type);
        if (type_it != type_map.end()) {
            f.type = type_it->second;
        } else {
            f.type = CardType::SUNDRY;
        }

        if (card.contains("usage_timing")) {
            pybind11::list timings = card["usage_timing"].cast<pybind11::list>();
            for (auto timing : timings) {
                std::string t = timing.cast<std::string>();
                auto timing_it = timing_map.find(t);
                if (timing_it != timing_map.end()) {
                    f.usage_timing |= timing_it->second;
                }
            }
        }

        f.price = card.contains("price") ? card["price"].cast<int>() : 0;
        f.drop_rate = card.contains("drop_rate") ? card["drop_rate"].cast<int>() : 0;
        f.attack_power = card.contains("attack_power") ? card["attack_power"].cast<int>() : 0;
        f.defense_power = card.contains("defense_power") ? card["defense_power"].cast<int>() : 0;
        f.accuracy = card.contains("accuracy") ? card["accuracy"].cast<int>() : 100;
        f.mp_cost = card.contains("mp_cost") ? card["mp_cost"].cast<int>() : 0;

        if (card.contains("element")) {
            std::string el = card["element"].cast<std::string>();
            auto el_it = element_map.find(el);
            if (el_it != element_map.end()) {
                f.element = el_it->second;
            } else {
                f.element = ELEM_NONE;
            }
        }

        if (card.contains("reaction_type")) {
            std::string rt = card["reaction_type"].cast<std::string>();
            auto rt_it = reaction_map.find(rt);
            if (rt_it != reaction_map.end()) {
                f.reaction_type = rt_it->second;
            }
        }

        if (card.contains("hit_curse")) {
            std::string hc = card["hit_curse"].cast<std::string>();
            auto hc_it = curse_map.find(hc);
            if (hc_it != curse_map.end()) {
                f.hit_curse = hc_it->second;
            }
        }

        f.is_group_attack = card.contains("is_group_attack") ? card["is_group_attack"].cast<bool>() : false;

        g_card_registry.push_back(f);
        std::string name = card.contains("name") ? card["name"].cast<std::string>() : "Unknown";
        g_card_names.push_back(name);
        weights.push_back(f.drop_rate);
    }

    for (size_t i = 0; i < g_card_registry.size(); ++i) {
        g_card_registry[i].dream_group = calculate_dream_group(static_cast<int>(i));
    }

    g_drop_distribution = std::discrete_distribution<int>(weights.begin(), weights.end());
    g_distribution_generation.fetch_add(1, std::memory_order_release);
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

    // EnvPool::step_all は OpenMP で並列化されており、全環境のドローがこの関数を通る。
    // 共有分布をロックで守ると数千環境分の抽選が直列化してしまうため、
    // スレッドごとに分布のコピーを持つ。分布は確率テーブルから決定的に抽選するので、
    // コピーでも消費する乱数と結果は共有インスタンスと同一になる。
    thread_local std::discrete_distribution<int> local_distribution;
    thread_local uint64_t local_generation = 0;

    uint64_t current_generation = g_distribution_generation.load(std::memory_order_acquire);
    if (local_generation != current_generation) {
        local_distribution = g_drop_distribution;
        local_generation = current_generation;
    }
    return local_distribution(rng);
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
