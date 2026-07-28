#pragma once
#include <cstdint>

/**
 * @brief xoshiro128++ 1.0（32bit出力・内部状態16バイト）
 *
 * 【なぜ std::mt19937 をやめたのか】
 * mt19937 は内部状態が 5000 バイトあり、InternalState 全体 7232 バイトの 69% を
 * 占めていました。この構造体は環境の数だけ並ぶ（1024環境で 7.4MB）ため、
 * キャッシュに乗る量が乱数エンジンだけで決まってしまう状態でした。
 * さらに初期化コストが大きく（624要素の漸化式を回す）、リセットのたびに走ります。
 *
 * ゲームシミュレータが必要とするのは「偏りのない乱数を大量に速く」であって、
 * mt19937 の長周期（2^19937-1）ではありません。xoshiro128++ は周期 2^128-1、
 * 内部状態16バイトで、統計的品質は BigCrush を通ります。
 *
 * 【互換性】
 * UniformRandomBitGenerator の要件（result_type / min / max / operator()）を
 * 満たすので、std::uniform_int_distribution や std::shuffle にそのまま渡せます。
 *
 * 【注意】
 * 乱数列は mt19937 と当然変わります。同じシードでも以前と同じ試合にはなりません。
 * テストが特定のシードの結果に依存していないこと（RollKind による値注入への
 * 移行で解消済み）が前提です。
 *
 * 出典: David Blackman and Sebastiano Vigna, xoshiro128++ (public domain)
 */
class Xoshiro128PP {
public:
    using result_type = uint32_t;

    static constexpr result_type min() { return 0; }
    static constexpr result_type max() { return UINT32_MAX; }

    Xoshiro128PP() { seed(5489u); }  // mt19937 の既定シードに合わせておく
    explicit Xoshiro128PP(uint32_t s) { seed(s); }

    /**
     * @brief SplitMix32 で内部状態を埋めます。
     *
     * シード値をそのまま状態に置くと、0 や 1 のような近いシード同士で
     * 初期状態が似てしまい、系列の出だしに相関が出ます。環境ごとに
     * seed + env_id を配る使い方をしているため、ここは必ず撹拌します。
     */
    void seed(uint32_t s) {
        for (int i = 0; i < 4; ++i) {
            s += 0x9E3779B9u;
            uint32_t z = s;
            z ^= z >> 16;
            z *= 0x21F0AAADu;
            z ^= z >> 15;
            z *= 0x735A2D97u;
            z ^= z >> 15;
            state_[i] = z;
        }
        // 全ビット0は不動点になるため、万一そうなったら既知の非零値へ退避する
        if ((state_[0] | state_[1] | state_[2] | state_[3]) == 0) {
            state_[0] = 0x9E3779B9u;
        }
    }

    result_type operator()() {
        const uint32_t result = rotl(state_[0] + state_[3], 7) + state_[0];
        const uint32_t t = state_[1] << 9;

        state_[2] ^= state_[0];
        state_[3] ^= state_[1];
        state_[1] ^= state_[2];
        state_[0] ^= state_[3];
        state_[2] ^= t;
        state_[3] = rotl(state_[3], 11);

        return result;
    }

    bool operator==(const Xoshiro128PP &other) const {
        return state_[0] == other.state_[0] && state_[1] == other.state_[1] &&
               state_[2] == other.state_[2] && state_[3] == other.state_[3];
    }
    bool operator!=(const Xoshiro128PP &other) const { return !(*this == other); }

private:
    static uint32_t rotl(uint32_t x, int k) { return (x << k) | (x >> (32 - k)); }

    uint32_t state_[4];
};
