#include "ismcts.h"

#include <algorithm>
#include <cmath>
#include <cstring>

#include "game_logic.h"
#include "game_logic_internal.h"

namespace ismcts {

namespace {

thread_local Stats g_stats;

constexpr uint8_t NO_SLOT = 255;
static_assert(ACTION_SPACE_SIZE < NO_SLOT, "スロット表が uint8_t に収まりません");

// ---------------------------------------------------------------------------
// 夢グループの逆引き表
//
// 夢状態で未確定の手札を引き直すには「同じ夢グループのカード」が要ります。
// 毎回レジストリ全体を走査すると 1 枚あたり O(レジストリ) かかり、
// 1万シミュレーション × 手札18枚では効いてきます。探索の頭で一度だけ作ります。
//
// 山札テーブル（重みを展開済み）から作るので、選ぶと自動的に出現率で重み付け
// されます。グループ内均等に引くより事後分布に近くなります。
// ---------------------------------------------------------------------------
struct DreamTable {
    std::vector<std::vector<int32_t>> members;  // DreamGroup -> 山札エントリの並び

    void build() {
        // DreamGroup に要素数を表す番兵は無いので、実際に現れる最大値から決めます
        // （番兵を足すと pybind が公開している enum にも現れてしまうため）。
        size_t highest = 0;
        for (int32_t card : g_draw_table) {
            highest = std::max(highest, static_cast<size_t>(get_dream_group(card)));
        }
        members.assign(highest + 1, {});
        for (int32_t card : g_draw_table) {
            const DreamGroup grp = get_dream_group(card);
            if (grp == DreamGroup::NONE) continue;
            members[static_cast<size_t>(grp)].push_back(card);
        }
    }

    const std::vector<int32_t>& pool_for(DreamGroup grp) const {
        static const std::vector<int32_t> empty;
        const size_t idx = static_cast<size_t>(grp);
        return idx < members.size() ? members[idx] : empty;
    }
};

// ---------------------------------------------------------------------------
// 木の格納
//
// ノードとエッジを別々の配列に持ちます（SoA）。PUCT の選択は 1 ノードのエッジ列を
// 連続に舐めるだけなので、ポインタ追跡が起きません。
//
// 局面は木に持ちません（InternalState は 2KB 超あり、10万ノードで数百MBになる）。
// 毎回ルートから step_game で再現します。エンジンは毎秒500万ステップ出るので、
// 深さ10でも数μsで済みます。
//
// ## エッジ集合が決定化ごとに変わることへの対処
//
// 相手の手札を引き直すと、同じノードでも合法手が変わります（「スロット5を選ぶ」が
// 非合法になる、など）。木に固定した手をそのまま step_game に渡すことはできません。
// そこで
//   - 選択は必ず「今回の決定化で合法な手」だけから行う
//   - 初めて現れた手はその場でエッジとして足す
//   - 探索項の分母には、今回合法だった手の訪問数の和を使う
//     （たまたま合法だった回数が少ない手を過剰に探索しないため）
// としています。Cowling らの ISMCTS が availability count でやっていることの
// PUCT 版です。
//
// エッジはノードごとに連続に置きますが、後から手が増えることがあるため容量に
// 余裕を持たせ、足りなくなったら配列末尾へ引っ越します（穴は残りますが、
// 引っ越しは実測でほとんど起きません）。行動IDからエッジ位置への逆引きは
// ノードごとの 122 バイトの表で O(1) にしています。
// ---------------------------------------------------------------------------
struct Tree {
    // --- ノード ---
    std::vector<int32_t> edge_begin;    // エッジ配列における開始位置（-1 なら未展開）
    std::vector<int16_t> edge_count;
    std::vector<int16_t> edge_cap;
    std::vector<int32_t> node_visits;
    std::vector<float> node_value_sum;  // 探索側視点の価値の総和
    std::vector<uint8_t> node_actor;    // このノードで行動権を持つプレイヤー
    std::vector<uint8_t> slot;          // ノードごと ACTION_SPACE_SIZE 個の逆引き表

    // --- エッジ ---
    std::vector<int32_t> child;         // 子ノードの添字（未生成なら -1）
    std::vector<int32_t> visits;
    std::vector<float> value_sum;
    std::vector<float> prior;           // 方策の生の確率（下限は選択時に足す）
    std::vector<uint8_t> action;

    void reserve(int nodes, int edges_per_node) {
        edge_begin.reserve(nodes);
        edge_count.reserve(nodes);
        edge_cap.reserve(nodes);
        node_visits.reserve(nodes);
        node_value_sum.reserve(nodes);
        node_actor.reserve(nodes);
        slot.reserve(static_cast<size_t>(nodes) * ACTION_SPACE_SIZE);
        const size_t e = static_cast<size_t>(nodes) * static_cast<size_t>(edges_per_node);
        child.reserve(e);
        visits.reserve(e);
        value_sum.reserve(e);
        prior.reserve(e);
        action.reserve(e);
    }

    int32_t new_node(int actor) {
        edge_begin.push_back(-1);
        edge_count.push_back(0);
        edge_cap.push_back(0);
        node_visits.push_back(0);
        node_value_sum.push_back(0.0f);
        node_actor.push_back(static_cast<uint8_t>(actor));
        slot.resize(slot.size() + ACTION_SPACE_SIZE, NO_SLOT);
        g_stats.nodes = static_cast<int64_t>(edge_begin.size());
        return static_cast<int32_t>(edge_begin.size()) - 1;
    }

    bool expanded(int32_t node) const { return edge_begin[node] >= 0; }

    // ノードのエッジ用に領域を確保する（既存分があれば引っ越す）
    void allocate_block(int32_t node, int capacity) {
        capacity = std::min(capacity, ACTION_SPACE_SIZE);
        const int32_t old_begin = edge_begin[node];
        const int count = edge_count[node];
        const int32_t new_begin = static_cast<int32_t>(child.size());

        for (int i = 0; i < capacity; ++i) {
            child.push_back(i < count ? child[old_begin + i] : -1);
            visits.push_back(i < count ? visits[old_begin + i] : 0);
            value_sum.push_back(i < count ? value_sum[old_begin + i] : 0.0f);
            prior.push_back(i < count ? prior[old_begin + i] : 0.0f);
            action.push_back(i < count ? action[old_begin + i] : 0);
        }
        edge_begin[node] = new_begin;
        edge_cap[node] = static_cast<int16_t>(capacity);
        g_stats.edges = static_cast<int64_t>(child.size());
    }

    // 合法手ぶんのエッジを作って、方策の確率を書き込む
    void expand(int32_t node, const std::vector<int>& legal, const std::vector<float>& priors) {
        const int n = static_cast<int>(legal.size());
        // 後から手が増えても引っ越さずに済むよう余裕を持たせる。相手ノードでは
        // 決定化のたびに使える手札スロットが入れ替わるため、実測では 12 ほど
        // 余らせると引っ越しがほぼ無くなる（1ノードあたり 192 バイトの追加）。
        allocate_block(node, std::min(ACTION_SPACE_SIZE, n + 12));
        uint8_t* slots = &slot[static_cast<size_t>(node) * ACTION_SPACE_SIZE];
        const int32_t begin = edge_begin[node];
        for (int i = 0; i < n; ++i) {
            const int32_t e = begin + i;
            child[e] = -1;
            visits[e] = 0;
            value_sum[e] = 0.0f;
            prior[e] = priors[i];
            action[e] = static_cast<uint8_t>(legal[i]);
            slots[legal[i]] = static_cast<uint8_t>(i);
        }
        edge_count[node] = static_cast<int16_t>(n);
    }

    // 行動に対応するエッジを返す。初めて現れた手ならその場で作る。
    int32_t edge_for(int32_t node, int a) {
        uint8_t* slots = &slot[static_cast<size_t>(node) * ACTION_SPACE_SIZE];
        if (slots[a] != NO_SLOT) return edge_begin[node] + slots[a];

        if (edge_count[node] >= edge_cap[node]) {
            allocate_block(node, std::max(edge_cap[node] * 2, edge_cap[node] + 4));
            slots = &slot[static_cast<size_t>(node) * ACTION_SPACE_SIZE];
            ++g_stats.edge_relocations;
        }
        const int idx = edge_count[node]++;
        const int32_t e = edge_begin[node] + idx;
        child[e] = -1;
        visits[e] = 0;
        value_sum[e] = 0.0f;
        // 方策が知らなかった手。下限ぶんの確率だけが残る（select_edge が足す）。
        prior[e] = 0.0f;
        action[e] = static_cast<uint8_t>(a);
        slots[a] = static_cast<uint8_t>(idx);
        return e;
    }
};

// 終端の価値を「探索プレイヤーから見た値」で返す（勝ち +1 / 負け -1 / 引き分け 0）
inline float terminal_value(const InternalState& state, int searching_player) {
    return searching_player == 0 ? state.p0_reward : state.p1_reward;
}

// PUCT で 1 手選ぶ（候補は今回の決定化で合法なエッジだけ）。
//
// 価値は常に探索プレイヤー視点で持っているので、相手の手番のノードでは符号を
// 反転してから最大化します。これをやらないと「相手がこちらに都合よく指してくれる」
// 前提の探索になり、有利な局面で負け筋を見落とします。
//
// FPU: 未訪問の子には「そのノードの平均価値 − fpu_reduction」を仮の Q として
// 与えます。0 にすると未訪問を楽観視しすぎ、大きすぎると探索が既知の手に固まります。
int select_edge(const Tree& tree, int32_t node, const std::vector<int32_t>& candidates,
                const Config& cfg, int searching_player) {
    const int n = static_cast<int>(candidates.size());

    // 事前分布は「今回合法な手」の上で正規化し直す。決定化ごとに合法手が変わるため、
    // 展開時の正規化をそのまま使うと合計が 1 からずれる。
    float prior_sum = 0.0f;
    int32_t total_visits = 0;
    for (int i = 0; i < n; ++i) {
        prior_sum += tree.prior[candidates[i]];
        total_visits += tree.visits[candidates[i]];
    }
    const float inv_prior = prior_sum > 1e-9f ? 1.0f / prior_sum : 0.0f;
    const float floor_share = cfg.prior_floor / static_cast<float>(n);
    const float sqrt_total = std::sqrt(static_cast<float>(total_visits) + 1.0f);

    const float sign =
        tree.node_actor[node] == static_cast<uint8_t>(searching_player) ? 1.0f : -1.0f;
    const int32_t nvisits = tree.node_visits[node];
    const float node_q =
        nvisits > 0 ? sign * tree.node_value_sum[node] / static_cast<float>(nvisits) : 0.0f;
    const float fpu = node_q - cfg.fpu_reduction;

    int best = 0;
    float best_score = -1e30f;
    for (int i = 0; i < n; ++i) {
        const int32_t e = candidates[i];
        const int32_t ev = tree.visits[e];
        const float q = ev > 0 ? sign * tree.value_sum[e] / static_cast<float>(ev) : fpu;
        // 事前分布に下限を入れる。学習済みの方策は「武器の対象」をほぼ100%相手に
        // 向けるため、素のままでは自傷攻撃の枝に二度と入らない。
        const float p = (1.0f - cfg.prior_floor) * tree.prior[e] * inv_prior + floor_share;
        const float score = q + cfg.c_puct * p * sqrt_total / (1.0f + static_cast<float>(ev));
        if (score > best_score) {
            best_score = score;
            best = i;
        }
    }
    return best;
}

// 決着まで（または打ち切りまで）ランダムに進めて、探索側視点の価値を返す。
// ニューラルネットを繋ぐまでの暫定評価です。`state` は破壊されます。
float rollout(InternalState& state, int searching_player, const Config& cfg,
              std::vector<int>& scratch) {
    int steps = 0;
    while (!state.is_done) {
        if (cfg.rollout_max_steps > 0 && steps >= cfg.rollout_max_steps) {
            // 打ち切り。HP差で近似する（-1..1 に収める）
            const float diff =
                static_cast<float>(state.hp[searching_player] - state.hp[1 - searching_player]) /
                99.0f;
            return std::max(-1.0f, std::min(1.0f, diff));
        }
        // 分岐が無いなら合法手の列挙を省く（こちらの方が安い）
        const int single = get_single_legal_action(state);
        if (single >= 0) {
            step_game(state, static_cast<ActionType>(single));
        } else {
            bool mask[ACTION_SPACE_SIZE];
            get_legal_actions(state, mask);
            scratch.clear();
            for (int a = 0; a < ACTION_SPACE_SIZE; ++a) {
                if (mask[a]) scratch.push_back(a);
            }
            if (scratch.empty()) break;
            step_game(state, static_cast<ActionType>(scratch[state.rng() % scratch.size()]));
        }
        ++steps;
        ++g_stats.game_steps;
    }
    return state.is_done ? terminal_value(state, searching_player) : 0.0f;
}

// Gamma(alpha, 1) からのサンプリング。
// alpha < 1 では Marsaglia-Tsang をそのまま使えないので、alpha+1 で引いてから
// U^(1/alpha) で縮める Ahrens-Dieter のブースト法を使います。
float sample_gamma(float alpha, Xoshiro128PP& rng) {
    auto uniform = [&rng]() {
        // (0,1) の開区間。log(0) を踏まないよう 0 を避ける。
        return (static_cast<float>(rng() >> 8) + 0.5f) / 16777216.0f;
    };

    float boost = 1.0f;
    if (alpha < 1.0f) {
        boost = std::pow(uniform(), 1.0f / alpha);
        alpha += 1.0f;
    }

    const float d = alpha - 1.0f / 3.0f;
    const float c = 1.0f / std::sqrt(9.0f * d);
    for (int guard = 0; guard < 128; ++guard) {
        const float u1 = uniform();
        const float u2 = uniform();
        const float x = std::sqrt(-2.0f * std::log(u1)) * std::cos(6.2831853f * u2);
        const float v = 1.0f + c * x;
        if (v <= 0.0f) continue;
        const float v3 = v * v * v;
        const float u = uniform();
        if (u < 1.0f - 0.0331f * x * x * x * x) return boost * d * v3;
        if (std::log(u) < 0.5f * x * x + d * (1.0f - v3 + std::log(v3))) return boost * d * v3;
    }
    return boost * d;  // 128回棄却されるのは事実上起きない
}

void determinize_impl(InternalState& state, int searching_player, Xoshiro128PP& rng,
                      const DreamTable& dreams) {
    const int opp = 1 - searching_player;

    // 相手の手札のうち、こちらから中身が見えていないものを引き直す。
    //
    // 山札は固定の重みからの復元抽出なので、見えていないカードの事後分布は
    // （相手が「使わなかった」という選択の情報を無視すれば）山札の分布そのものです。
    // 枚数は既知の情報なので、空きスロットは空きのまま残します。
    if (!g_draw_table.empty()) {
        const uint32_t deck_size = static_cast<uint32_t>(g_draw_table.size());
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.true_hand[opp][i] == CARD_EMPTY) continue;
            if (state.is_deployed[opp][i] || state.is_known_to_opp[opp][i]) continue;
            const int32_t card = g_draw_table[rng() % deck_size];
            state.true_hand[opp][i] = card;
            state.apparent_hand[opp][i] = card;
        }
    }

    // 夢で未確定な自分の手札を引き直す。
    //
    // 見かけのカードと同じ夢グループのどれかが真の姿です。見かけそのものも候補に
    // 含みます（DREAM_DISGUISE の抽選で「正しく見える」側に転ぶことがあるため）。
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        if (state.true_hand[searching_player][i] == CARD_EMPTY) continue;
        if (state.is_confirmed[searching_player][i]) continue;

        const int apparent = state.apparent_hand[searching_player][i];
        if (apparent < 0) continue;
        const DreamGroup grp = get_dream_group(apparent);
        if (grp == DreamGroup::NONE) continue;

        const std::vector<int32_t>& pool = dreams.pool_for(grp);
        if (pool.empty()) continue;
        state.true_hand[searching_player][i] = pool[rng() % static_cast<uint32_t>(pool.size())];
    }
}

}  // namespace

void determinize(InternalState& state, int searching_player, Xoshiro128PP& rng) {
    DreamTable dreams;
    dreams.build();
    determinize_impl(state, searching_player, rng, dreams);
}

// ---------------------------------------------------------------------------
// 探索
// ---------------------------------------------------------------------------
Result search(const InternalState& root_state, int searching_player,
              const Config& config, Evaluator* evaluator) {
    g_stats = Stats{};

    Result result;
    if (root_state.is_done) return result;

    DreamTable dreams;
    dreams.build();

    Tree tree;
    tree.reserve(config.num_simulations + 2, 12);

    Xoshiro128PP rng;
    rng.seed(static_cast<uint32_t>(config.seed ? config.seed : 0x9E3779B9u));

    std::vector<int> legal;
    std::vector<float> priors;
    std::vector<int> rollout_scratch;
    std::vector<int32_t> candidates;
    std::vector<int32_t> path_edges;
    std::vector<int32_t> path_nodes;
    legal.reserve(ACTION_SPACE_SIZE);
    priors.reserve(ACTION_SPACE_SIZE);
    rollout_scratch.reserve(ACTION_SPACE_SIZE);
    candidates.reserve(ACTION_SPACE_SIZE);
    path_edges.reserve(64);
    path_nodes.reserve(64);

    bool mask[ACTION_SPACE_SIZE];

    const int32_t root = tree.new_node(root_state.current_actor_id);

    // 根は先に展開しておく（合法手の一覧を Result で返すため）。
    // ここでは決定化前の本物の局面を使うので、返る一覧は実際に指せる手そのもの。
    {
        get_legal_actions(root_state, mask);
        legal.clear();
        for (int a = 0; a < ACTION_SPACE_SIZE; ++a) {
            if (mask[a]) legal.push_back(a);
        }
        if (legal.empty()) return result;

        priors.assign(legal.size(), 1.0f / static_cast<float>(legal.size()));
        if (evaluator) {
            evaluator->evaluate(root_state, legal, priors);
            ++g_stats.evaluations;
        }

        // 自己対戦でデータを集めるときだけ根にノイズを混ぜる（既定は 0）。
        // 「最善手を1つ選ぶ」用途ではノイズは純粋に害なので、手を落とさない役目は
        // prior_floor と expand_root_fully に持たせています。
        if (config.root_noise_frac > 0.0f) {
            std::vector<float> noise(legal.size());
            float sum = 0.0f;
            for (size_t i = 0; i < noise.size(); ++i) {
                noise[i] = sample_gamma(config.root_noise_alpha, rng);
                sum += noise[i];
            }
            if (sum > 0.0f) {
                for (size_t i = 0; i < priors.size(); ++i) {
                    priors[i] = (1.0f - config.root_noise_frac) * priors[i] +
                                config.root_noise_frac * (noise[i] / sum);
                }
            }
        }
        tree.expand(root, legal, priors);

        result.actions = legal;
        result.priors.resize(legal.size());
        const float share = config.prior_floor / static_cast<float>(legal.size());
        for (size_t i = 0; i < legal.size(); ++i) {
            result.priors[i] = (1.0f - config.prior_floor) * priors[i] + share;
        }
    }

    for (int sim = 0; sim < config.num_simulations; ++sim) {
        InternalState state = root_state;

        // 隠れ情報はシミュレーションのたびに引き直す。木は共有したままなので、
        // 同じ情報集合では 1 つの手しか選べない（strategy fusion が起きない）。
        determinize_impl(state, searching_player, rng, dreams);

        // 局面のコピーには乱数の内部状態も含まれるため、そのままだと全シミュレーションが
        // 同じ確率イベント列（命中・弾き・ドロー）を再生してしまう。運の分岐を平均するのが
        // 木探索の役目なので、ここで種を配り直す。
        state.rng.seed(rng());

        path_edges.clear();
        path_nodes.clear();
        int32_t node = root;
        int depth = 0;
        bool have_value = false;
        float value = 0.0f;

        while (true) {
            if (state.is_done) {
                value = terminal_value(state, searching_player);
                have_value = true;
                break;
            }

            get_legal_actions(state, mask);
            legal.clear();
            for (int a = 0; a < ACTION_SPACE_SIZE; ++a) {
                if (mask[a]) legal.push_back(a);
            }
            if (legal.empty()) break;  // 行き止まり（起きない想定だが、価値0で扱う）

            // --- 葉なら評価して終わり ---
            if (!tree.expanded(node)) {
                priors.assign(legal.size(), 1.0f / static_cast<float>(legal.size()));
                if (evaluator) {
                    value = evaluator->evaluate(state, legal, priors);
                    ++g_stats.evaluations;
                    tree.expand(node, legal, priors);
                } else {
                    tree.expand(node, legal, priors);
                    // rollout は state を壊すので、木への書き込みを先に済ませる
                    value = rollout(state, searching_player, config, rollout_scratch);
                }
                have_value = true;
                break;
            }

            // --- 選択 ---
            // 今回の決定化で合法な手だけを候補にする。初めて現れた手はここで足す。
            //
            // 「足す」と「位置を引く」を2周に分けるのは、追加でエッジ領域の引っ越しが
            // 起きるとノードのエッジ開始位置が動くため。1周で済ませると、引っ越し前に
            // 求めた添字が古い領域を指したまま残る。
            for (int a : legal) tree.edge_for(node, a);

            candidates.clear();
            {
                const int32_t block = tree.edge_begin[node];
                const uint8_t* slots = &tree.slot[static_cast<size_t>(node) * ACTION_SPACE_SIZE];
                for (int a : legal) candidates.push_back(block + slots[a]);
            }

            path_nodes.push_back(node);

            int pick = -1;
            if (node == root && config.expand_root_fully) {
                // 根では全合法手を 1 回は通す。学習済み方策が事前確率をほぼ 0 に
                // する手（自傷攻撃など）を落とさないため。根は 1 ノードしかないので、
                // 追加コストは |A|/num_simulations（15手・1万回なら 0.15%）。
                for (size_t i = 0; i < candidates.size(); ++i) {
                    if (tree.visits[candidates[i]] == 0) {
                        pick = static_cast<int>(i);
                        break;
                    }
                }
            }
            if (pick < 0) pick = select_edge(tree, node, candidates, config, searching_player);

            const int32_t e = candidates[pick];
            path_edges.push_back(e);

            step_game(state, static_cast<ActionType>(tree.action[e]));
            ++g_stats.game_steps;
            ++depth;

            // 分岐の無い区間は木に載せない（ノードを作る意味がないため）
            while (!state.is_done) {
                const int single = get_single_legal_action(state);
                if (single < 0) break;
                step_game(state, static_cast<ActionType>(single));
                ++g_stats.game_steps;
            }

            if (tree.child[e] < 0 && !state.is_done) {
                tree.child[e] = tree.new_node(state.current_actor_id);
            }
            if (state.is_done) {
                value = terminal_value(state, searching_player);
                have_value = true;
                break;
            }
            node = tree.child[e];
        }

        if (!have_value) value = 0.0f;

        // --- バックアップ ---
        //
        // 価値は探索プレイヤー視点のまま伝播します。ゴッドフィールドは手番が交互とは
        // 限らず（防御・購入・両替などで行き来する）、深さで符号を反転させる素朴な
        // 方法は使えません。視点の切り替えは select_edge が node_actor を見て行います。
        for (size_t i = 0; i < path_edges.size(); ++i) {
            const int32_t e = path_edges[i];
            tree.visits[e] += 1;
            tree.value_sum[e] += value;
            tree.node_visits[path_nodes[i]] += 1;
            tree.node_value_sum[path_nodes[i]] += value;
        }

        ++g_stats.simulations;
        if (depth > g_stats.max_depth) g_stats.max_depth = depth;
    }

    // --- 結果を取り出す ---
    //
    // 根で初めて現れた手（決定化によってのみ合法になる手）は実局面では指せないので、
    // 報告するのは最初に集めた本物の合法手だけにします。
    const uint8_t* slots = &tree.slot[static_cast<size_t>(root) * ACTION_SPACE_SIZE];
    const int32_t begin = tree.edge_begin[root];
    const int n = static_cast<int>(result.actions.size());
    result.simulations = config.num_simulations;
    result.visits.assign(n, 0);
    result.values.assign(n, 0.0f);

    int best = -1;
    for (int i = 0; i < n; ++i) {
        const int32_t e = begin + slots[result.actions[i]];
        result.visits[i] = tree.visits[e];
        result.values[i] = tree.visits[e] > 0
                               ? tree.value_sum[e] / static_cast<float>(tree.visits[e])
                               : 0.0f;
        // 訪問数が同じときは平均価値の高いほうを採る。expand_root_fully が全手に
        // 1 訪問ずつ配るため、予算が小さいと同数で並びやすい。
        const bool better = best < 0 || result.visits[i] > result.visits[best] ||
                            (result.visits[i] == result.visits[best] &&
                             result.values[i] > result.values[best]);
        if (better) best = i;
    }
    if (best >= 0) result.best_action = result.actions[best];
    return result;
}

Stats last_search_stats() { return g_stats; }

}  // namespace ismcts
