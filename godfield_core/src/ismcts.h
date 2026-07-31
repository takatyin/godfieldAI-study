#pragma once

#include <cstdint>
#include <vector>

#include "constants.h"
#include "types.h"

// ============================================================================
// ISMCTS（Information Set Monte Carlo Tree Search）
//
// 学習だけでは拾えない細い筋を探索で見つけるための木探索です。
//
//   - 非常に不利な局面で、勝率の低い勝ち筋を選ぶ
//   - 非常に有利な局面で、確率の低い負け筋を潰す
//   - 夢状態で「本当の手札はこうかもしれない」を数える
//
// ## 決定化ごとに木を分けない
//
// 隠れ情報をサンプリングして完全情報の探索をする素朴な方法（PIMC）は、
// **strategy fusion** を起こします。区別できないはずの2つの状態で別々の手を
// 選べる前提になり、細い勝ち筋を過大評価します。不利な局面ほど誤差が効くため、
// この用途では致命的です。
//
// そこで木は**情報集合ごとに1本**にします。決定化はシミュレーションのたびに
// やり直しますが、木のノードは共有するので、同じ情報集合では必ず1つの手しか
// 選べません（Cowling らの ISMCTS 本来の形）。
//
// 情報集合は探索プレイヤー側だけで区切ります（SO-ISMCTS）。木の中の相手ノードは
// その決定化での完全情報を見て指すので、相手を実際より少しだけ強く見積もります。
// 「有利な局面で負け筋を潰す」用途では安全側に振れるので、この近似で困りません。
//
// ## 価値の視点
//
// 価値は常に**探索プレイヤーから見た値**（勝ち +1 / 負け -1）で持ちます。
// ゴッドフィールドは手番が交互とは限らない（防御・購入・両替で行き来する）ため、
// 深さで符号を反転させる素朴な方法が使えないからです。代わりに各ノードが
// 行動権を持つプレイヤーを覚えていて、選択のときだけ符号を反転します。
// これを省くと「相手がこちらに都合よく指してくれる」前提の探索になります。
//
// ## 速さのための構造
//
// ノードとエッジを SoA（配列の構造体）で持ちます。PUCT の選択はノードの
// エッジ列を連続に舐めるだけになり、ポインタ追跡もキャッシュミスも起きません。
// 探索中の動的確保はゼロで、プールから切り出します。
//
// 局面は木に持ちません（InternalState は 2,240 バイトあり、100万ノードで
// 2.2GB になる）。毎回ルートから `step_game` で再現します。エンジンは
// 毎秒510万ステップ出るので、深さ10でも 2μs 程度で済みます。
// ============================================================================

namespace ismcts {

// 探索の設定。既定値は「爆速で回しつつ、細い筋を落とさない」ことを狙った値。
struct Config {
    int num_simulations = 10000;   // 1手あたりのシミュレーション回数
    float c_puct = 1.4f;           // 探索項の強さ

    // 事前分布の下限。P' = (1-floor)*P + floor/|A|
    //
    // 学習済みの方策は「武器の対象」を100%相手に向けるため、自傷攻撃の事前確率が
    // ほぼ0になります。素の PUCT では二度と訪問されないので、下限を入れて
    // 「方策が切り捨てた手」にも道を残します。
    float prior_floor = 0.05f;

    // 未訪問の子に与える仮の価値（First Play Urgency）。親の価値からこの分だけ
    // 引いた値を使います。0 にすると未訪問を楽観視しすぎ、大きすぎると探索が
    // 既知の手に固まります。
    float fpu_reduction = 0.2f;

    // 根では全合法手を1回ずつ評価する。根は1ノードしかないので、探索全体に対する
    // 追加コストは |A|/num_simulations（合法手15手・1万回なら 0.15%）でしかない。
    // 「自分に武器を撃つ」が効くのはたいてい根なので、ここだけ手厚くする。
    bool expand_root_fully = true;

    // 根の事前分布に混ぜる Dirichlet ノイズ。自己対戦で学習データを集めるときに
    // 局面の多様性を作るためのもので、「最善手を1つ選ぶ」用途では純粋に害になるため
    // 既定は 0 です。手を落とさない役目は prior_floor と expand_root_fully が担います。
    float root_noise_frac = 0.0f;
    float root_noise_alpha = 0.3f;

    // ロールアウトの打ち切り。ニューラルネットを繋ぐまでの暫定評価で使います。
    // 0 なら決着まで回します。
    int rollout_max_steps = 200;

    uint64_t seed = 0;
};

// 探索結果。各合法手の訪問回数と平均価値を返します。
struct Result {
    int best_action = -1;
    int simulations = 0;
    std::vector<int> actions;      // 根の合法手
    std::vector<int> visits;       // それぞれの訪問回数
    std::vector<float> values;     // それぞれの平均価値（手番側から見た値）
    std::vector<float> priors;     // 使った事前分布（ノイズと下限の適用後）
};

// 価値と事前分布の供給元。ニューラルネットを繋ぐときはこれを実装します。
// 既定（nullptr）ではロールアウトと一様分布を使います。
class Evaluator {
public:
    virtual ~Evaluator() = default;

    // 局面を評価して、手番プレイヤーから見た価値 [-1, 1] を返します。
    // priors には合法手それぞれの事前確率を書きます（合計1に正規化済み）。
    virtual float evaluate(const InternalState& state,
                           const std::vector<int>& legal_actions,
                           std::vector<float>& priors) = 0;
};

// 探索本体。
//
// `root` は探索を行うプレイヤーから見た情報集合の代表局面です。隠れ情報
// （相手の手札、夢で未確定の自分の手札）はシミュレーションごとにサンプリングし
// 直すので、`root` に入っている値は使いません。
Result search(const InternalState& root, int searching_player,
              const Config& config, Evaluator* evaluator = nullptr);

// --- 以下はテストと診断のために公開しているもの -----------------------------

// 情報集合と矛盾しないように隠れ情報をサンプリングします。
//
//   - 相手の手札のうち、展開済みでも公開済みでもないもの → 山札の分布から引き直す
//   - 自分の手札のうち夢で未確定のもの → 同じ夢グループから引き直す
//
// `searching_player` から見て見えているものは一切変更しません。
void determinize(InternalState& state, int searching_player, Xoshiro128PP& rng);

// 木の統計。速度の診断に使います。
struct Stats {
    int64_t nodes = 0;
    int64_t edges = 0;
    int64_t simulations = 0;
    int64_t game_steps = 0;      // step_game を呼んだ回数
    int64_t evaluations = 0;
    int64_t max_depth = 0;
    // 決定化によって新しい手が現れ、ノードのエッジ領域を確保し直した回数。
    // 常態的に大きいなら expand() の余裕を増やすべきという合図。
    int64_t edge_relocations = 0;
};

Stats last_search_stats();

}  // namespace ismcts
