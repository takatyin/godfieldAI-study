#pragma once

#include "types.h"
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

/**
 * @brief 並列化管理とバッチ処理のインターフェース
 * 
 * 大量のゲーム状態を並列に保持・進行し、AI推論（判断）が必要になったタイミングでゲームをストップし、
 * 状態をキューに溜めて一気にGPU（Python側）へ投げる。
 * 推論結果のアクションを受け取って再びゲームを進める、というCPU-GPU間のバッチ化管理に特化する。
 * ゲーム固有のルールやカード情報の知識は持たない。
 */
class EnvPool {
public:
    EnvPool(int num_envs = NUM_ENVS);
    ~EnvPool();

    void reset(int seed);
    void step_all(pybind11::array_t<int> actions);

    /**
     * @brief 指定した環境のみを1手進めます（相手の手番だけを消化する用途）。
     * @param env_ids 進める環境ID。
     * @param actions env_ids と同じ長さの行動列。
     */
    void step_subset(pybind11::array_t<int> env_ids, pybind11::array_t<int> actions);

    pybind11::array_t<float> get_observations();
    pybind11::array_t<float> get_dones();

    /** @brief 各環境で現在行動権を持つプレイヤーID。 */
    pybind11::array_t<int> get_current_actors();

    /** @brief 直前のステップで行動したプレイヤー視点の報酬（従来互換）。 */
    pybind11::array_t<float> get_rewards();

    /**
     * @brief 終局時の報酬を指定プレイヤー視点で返します。
     *        相手の手番で決着した場合、行動者視点の報酬は学習者の報酬と符号が逆になるため、
     *        単一エージェントとして学習する側はこちらを使います。
     */
    pybind11::array_t<float> get_rewards_for(int player_id);

    /**
     * @brief 終局時の観測を指定プレイヤー視点で返します（自動リセット前にキャッシュしたもの）。
     */
    pybind11::array_t<float> get_terminal_observations_for(int player_id);

    /**
     * @brief 全環境の HP / MP / お金を真の値で返します。形は (環境数, 6)。
     *        並びは [p0_hp, p0_mp, p0_money, p1_hp, p1_mp, p1_money]。
     *
     * 報酬シェーピング用です。観測（get_observations）は霧がかかると相手の
     * HP/MP/お金が 0 に潰れるため、そこからポテンシャルを作ると霧の付与・解除で
     * 巨大な偽の報酬が出ます。学習者が見るのはあくまで観測で、報酬の計算にだけ
     * 真の状態を使う、という切り分けです。
     */
    pybind11::array_t<int> get_player_stats();

    pybind11::array_t<int> get_opponent_true_hands(int player_id);

    InternalState get_state(int env_id) const { return states_[env_id]; }
    void set_state(int env_id, const InternalState &state) {
        states_[env_id] = state;
        generate_observation(env_id);
    }

private:
    int num_envs_;
    int seed_;
    std::vector<int> reset_counts_;
    std::vector<InternalState> states_;
    std::vector<Observation> obs_buffers_;
    // 終局時の観測をプレイヤーごとにキャッシュする。自動リセットで真の終端が失われるため、
    // かつ相手の手番で決着した場合は学習者視点の終端が必要になるため、両者分を持つ。
    std::vector<Observation> terminal_obs_buffers_[2];
    std::vector<float> rewards_;
    std::vector<float> rewards_per_player_[2];
    std::vector<float> dones_;
    std::vector<int> current_actors_;
    // get_player_stats() が返す配列の実体。呼び出しごとに詰め直す。
    std::vector<int> player_stats_;
    std::vector<int> opponent_true_hands_;

    // Internal helper functions for game logic
    void reset_env(int env_id, int seed);
    void step_env(int env_id, int action);
    void generate_observation(int env_id);
};
