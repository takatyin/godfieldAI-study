#pragma once
#include "rng.h"
#include "types.h"
#include <vector>
#include <random>
#include <string>

// ============================================================================
// グローバル変数 / Global Variables
// ============================================================================

/**
 * @brief ゲームに登録されているすべてのカードの特徴（CardFeatures）リスト。
 */
extern std::vector<CardFeatures> g_card_registry;

/**
 * @brief カード名リスト。インデックスがカードIDに対応。
 */
extern std::vector<std::string> g_card_names;

/**
 * @brief カードドローの抽選テーブル。
 *
 * drop_rate の重みの分だけカードIDを並べたフラットな配列。抽選は一様乱数1回と
 * 配列アクセス1回で済む。初期化後は読み取り専用なので全スレッドで共有できる。
 */
extern std::vector<int32_t> g_draw_table;

/**
 * @brief drop_rate の重みから抽選テーブルを構築します（init_game_logic からのみ呼ぶ）。
 */
void build_draw_table(const std::vector<int> &weights);


// ============================================================================
// イベント履歴出力ヘルパー / Event Log Helper
// ============================================================================

/**
 * @brief ゲームイベントを InternalState のリングバッファに追記します。
 */
inline void push_event(InternalState &state, int actor, EventType event_type, int card_id = -1, int target_id = -1, float value = 0.0f) {
    GameEvent ev;
    ev.actor = static_cast<float>(actor);
    ev.event_type = static_cast<float>(event_type);
    ev.card_id = static_cast<float>(card_id);
    ev.target_id = static_cast<float>(target_id);
    ev.value = value;

    state.history[state.history_head] = ev;
    state.history_head = (state.history_head + 1) % HISTORY_LENGTH;
    state.history_count++;
}

// ============================================================================
// ヘルパー関数 / Helper Functions
// ============================================================================

/**
 * @brief 指定されたカードが「捨てる」ことが可能なカードであるかを判定します。
 * @param card_id 判定対象のカードID。
 * @return 捨てられるカードであれば true、そうでなければ false。
 */
bool is_discardable_card(int card_id);
void update_staged_pending_info(InternalState &state, int player_id);

/**
 * @brief 指定されたカードが「奇跡の消費MPを0にする」精霊の神器であるかを判定します。
 * @param card_id 判定対象のカードID。
 * @return 精霊の神器であれば true、そうでなければ false。
 */
bool is_spiritual_zero_mp_card(int card_id);

/**
 * @brief 同じカードの組み合わせが複数箇所で列挙されていたものを述語にしたもの。
 *
 * 片方だけ直す事故を防ぐため、2箇所以上で同じ列挙が現れるものはここに集約する。
 */
bool is_non_damage_ring_counter(int card_id);   // 反撃がHPダメージを伴わない指輪5枚
bool is_element_overriding_wand(int card_id);   // 属性を無条件で上書きするワンド
bool is_opponent_discarding_sundry(int card_id); // 相手の手札・奇跡を破棄する雑貨

struct StagedAttackInfo {
    int mp_cost;
    int attack_power;
    Element element;
    bool absorption;
    bool deal_same_damage;
};

/**
 * @brief 仮置きされたカード群から消費MP・攻撃力・属性・吸収などを計算します。
 *
 * 乱数を消費しません（命中判定は roll_staged_attack_hits が担当します）。
 * 観測の更新など、実際に攻撃を解決しない場面から安全に呼べます。
 */
StagedAttackInfo evaluate_staged_attack(InternalState &state, int player_id);

/**
 * @brief 仮置きされたカード群の命中判定を行います（乱数を消費するので解決時のみ呼ぶこと）。
 */
bool roll_staged_attack_hits(InternalState &state, int player_id);
void setup_multiple_attacks(InternalState &state, int me, int opp, const StagedAttackInfo &info);

/**
 * @brief 「あぶないキネ」の使用処理を実行します（ウス所持チェック、99ダメージ解決、ランダムターゲット選定）。
 * @return プレイヤーの入力を要するフェイズ（防御フェイズ）を開いた場合のみ true。
 */
bool execute_dangerous_pestle(InternalState &state, int attacker, int defender, bool is_guardian = false);

/**
 * @brief 仮置きされた武器カード群の評価・攻撃実行パイプラインを一元処理します。
 * @return プレイヤーの入力を要するフェイズ（防御フェイズ）を開いた場合のみ true。
 *
 * 守護神の行動から呼ばれた場合、この戻り値はターン終了処理を中断するかどうかの
 * 判断に使われます。効果を適用しただけで PHASE_END に留まる経路で true を返すと、
 * 合法手が1つも無い状態のまま呼び出し側へ制御が戻ってしまいます
 * （実際に、地球神があぶないキネを引いた場合に進行不能になっていました）。
 */
bool execute_attack_from_staged_cards(InternalState &state, int attacker, int target, bool is_guardian = false);

/**
 * @brief 仮置き場（staged_cards）に最後に置かれたカードが「奇跡」であるかを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 最後のカードが奇跡であれば true、そうでなければ false。
 */
bool is_last_staged_card_miracle(const InternalState &state, int player_id);


/**
 * @brief 奇跡を展開し、6つの上限制限（FIFO）を処理します。
 */
void deploy_miracle(InternalState &state, int player_id, int slot_idx);

/**
 * @brief 奇跡の展開を解除し、展開順序バッファから削除します。
 */
void undeploy_miracle(InternalState &state, int player_id, int slot_idx);

void clear_hand_slot(InternalState &state, int player_id, int slot_idx);
void apply_defense_gear_effects(InternalState &state, int player_id);
void confirm_card(InternalState &state, int player_id, int slot_idx);
void add_card_to_hand_slot(InternalState &state, int player_id, int slot_idx, int card_id, bool is_drawn);
std::pair<int, int> get_exchange_hp_range(int sum);
std::pair<int, int> get_exchange_mp_range(int sum, int hp);
DreamGroup get_dream_group(int card_id);
std::vector<int> get_dream_candidates(int true_card_id);
DreamGroup calculate_dream_group(int card_id);

/**
 * @brief 仮置き場（staged_cards）に積まれているカードの合計消費MPを計算します（精霊補正あり）。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 合計消費MP。
 */
int calculate_staged_mp_cost(const InternalState &state, int player_id);

/**
 * @brief マジカルステッキを除いた消費MPを計算します（精霊系による0化を適用）。
 *
 * マジカルステッキの威力は「残りMP×2」なので、威力計算にはステッキ以外の消費MPが
 * 必要になります。この規則を calculate_staged_mp_cost() と別々に書いていたため、
 * 精霊系の扱いが2箇所に複製されていました（片方だけ変えると攻撃力とMP消費が
 * 食い違います）。
 *
 * @param has_magical_stick 非 nullptr なら、仮置きにステッキが含まれるかを書き込みます。
 */
int calculate_mp_cost_excluding_magical_stick(const InternalState &state, int player_id,
                                              bool *has_magical_stick);

/**
 * @brief 指定した手札スロットのカードを仮置き場に追加した場合に、消費MPを支払えるかを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @param next_hand_idx 追加しようとしている手札のインデックス。
 * @return 支払えるなら true、そうでなければ false。
 */
bool can_afford_staged_plus_card(const InternalState &state, int player_id, int next_hand_idx);

/**
 * @brief メインフェイズにおいて「祈る」アクションが可能かを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 祈れるなら true、そうでなければ false。
 */
bool can_pray(const InternalState &state, int player_id);

/**
 * @brief メインフェイズにおいて「捨てる」アクションが可能（手札に捨てられるカードがある）かを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 捨てられるなら true、そうでなければ false。
 */
bool can_discard(const InternalState &state, int player_id);

/**
 * @brief 「売る」カード自体を除いて、売却可能なカードが手札に1枚以上あるかを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @param sell_card_index 使用する「売る」カード自体の手札インデックス。
 * @return 売却可能なカードがあれば true、そうでなければ false。
 */
bool is_sellable_card(const InternalState &state, int player_id, int slot_idx);
bool can_sell_card(const InternalState &state, int player_id, int sell_card_index);

/**
 * @brief 手札からランダムに1枚カードを破棄します（手札が一杯の時の祈る等で使用）。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 */
void discard_one_card_randomly(InternalState &state, int player_id);

/**
 * @brief 山札からカードを1枚引き、空いている手札スロットに加えます。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 */
void draw_card_to_hand(InternalState &state, int player_id);

/**
 * @brief 終末の時を考慮してカードをドローします。25%の確率で悪魔カードが発生し、即時効果を適用した後に再ドローします。
 */
int draw_card_with_apocalypse(InternalState &state, int player_id);
void apply_devil_little(InternalState &state, int player_id);
void apply_devil_medium(InternalState &state, int player_id);
void apply_devil_large(InternalState &state, int player_id);
void apply_devil_prankster(InternalState &state, int player_id);
void apply_devil_fairy(InternalState &state, int player_id);

/**
 * @brief ターン終了時のクリーンアップ処理（使用済みカードの再ドロー、奇跡の展開、一時変数のリセット）。
 * @param state ゲーム状態。
 */
void cleanup_phase_end(InternalState &state);
bool resolve_turn_end_steps(InternalState &state);

/**
 * @brief カードが現在のフェイズおよび攻撃属性に対してアクティブなリアクション（反射/弾く/阻止）カードであるかを判定します。
 */
bool is_active_reaction_card(const InternalState &state, int card_id, GamePhase phase, Element attack_element);

/**
 * @brief 対象プレイヤーの仮置き場（staged_cards）に積まれているカードのID一覧を取得します。
 * @param state ゲーム状態。
 * @param player 対象プレイヤーID。
 * @return カードIDのリスト。
 */
StagedCardIds get_staged_card_ids(const InternalState &state, int player);

/**
 * @brief 仮置き場の i 番目が指すカードIDを返します。仮置き場を読む唯一の入口です。
 *
 * 手札由来なら手札から解決し（夢で見た目が変わるためIDはキャッシュしない）、
 * 守護神由来の仮想カードならそのIDを返します。範囲外なら CARD_EMPTY。
 *
 * 直接 staged_cards[p][i] を手札の添字に使わないこと。守護神が仕掛けた取引では
 * 手札スロットではないエントリが入るため、範囲外を読んで静かに壊れます。
 */
int staged_card_id(const InternalState &state, int player, int i);

/**
 * @brief 仮置き場の i 番目が指す手札スロットを返します。手札由来でなければ -1。
 *
 * 「そのカードを消費する」「使用済みにする」など、手札そのものを触る場合に使います。
 */
int staged_hand_slot(const InternalState &state, int player, int i);

/**
 * @brief 手札スロットのカードIDを返します（未確定なら見た目、無ければ真の手札）。
 *
 * 「apparent を見て、負なら true を見る」という同じ2行が11箇所に散っており、
 * 一部だけ範囲検査があるという不統一になっていました。ここに集約します。
 */
inline int card_id_in_hand(const InternalState &state, int player, int slot) {
    if (slot < 0 || slot >= MAX_HAND_SIZE) return CARD_EMPTY;
    int card_id = state.apparent_hand[player][slot];
    if (card_id < 0) card_id = state.true_hand[player][slot];
    return card_id;
}


// ============================================================================
// 取引・戦闘解決 / Combat & Trade Resolutions (combat_resolution.cpp)
// ============================================================================

/**
 * @brief 使用されたカードの効果（HP/MP回復、状態異常付与、その他雑貨効果）をターゲットプレイヤーに適用します。
 * @param state ゲーム状態。
 * @param target_id 効果を適用されるプレイヤーID。
 * @param used_card_ids 使用されたカードのIDリスト。
 */
void apply_card_effects_to_target(InternalState &state, int target_id, const StagedCardIds& used_card_ids);

/**
 * @brief カード1枚の効果を対象プレイヤーへ適用します。
 * @param target_id 効果を適用されるプレイヤーID。
 * @param card_id 効果を発生させるカードID。
 */
void apply_card_effect_to_target(InternalState &state, int target_id, int card_id);

/**
 * @brief カードが吸収効果（与えたダメージ分だけ攻撃側のHPが回復）を持つかを判定します。
 *
 * 仮置きから組み立てる攻撃（evaluate_staged_attack）と、仮置きを経由しない守護神の行動
 * （setup_guardian_attack_defense）の双方から参照するため、対象カードをここに一元化しています。
 */
bool is_absorption_source(int card_id);

/**
 * @brief 月神が発動しうる奇跡の一覧（テストが奇跡名から指示値を逆引きするために公開）。
 */
std::vector<int> get_moon_miracles();

/**
 * @brief 指定した守護神の5行動に対応するカードID一覧（テストが行動名から指示値を逆引きするために公開）。
 */
std::vector<int> get_guardian_action_cards(int guardian);

/**
 * @brief 終末の時に出る悪魔カードの一覧（テストが悪魔名から指示値を逆引きするために公開）。
 */
std::vector<int> get_apocalypse_devils();
std::vector<int> get_apocalypse_devil_percents();
std::vector<int> get_guardian_action_percents();

/**
 * @brief HP吸収を持つカードの一覧（テストが全種を網羅するために公開）。
 */
std::vector<int> get_absorption_sources();

void apply_curse_to_player(InternalState &state, int player_id, HitCurse curse);
void apply_curse(InternalState &state, int player_id, CurseType type);
void remove_curse(InternalState &state, int player_id, CurseType type);
void confirm_all_staged_cards(InternalState &state, int player);
void apply_damage(InternalState &state, int player_id, int damage, bool absorption = false, bool deal_same_damage = false);

/**
 * @brief HPをダメージ分減らし、守護神の退散判定だけを行います（お守りでの復活はしない）。
 *
 * 復活を挟まずに続けて別のHP操作を行いたい場合に使います。闇属性即死のように
 * 「ダメージを与えた直後にHPを0にする」処理で apply_damage() を使うと、
 * 途中の復活でお守りが二重に消費されてしまうため、こちらを使ってください。
 * 呼び出し側は適切なタイミングで run_immediate_revive() を呼ぶ責任があります。
 */
void apply_damage_without_revive(InternalState &state, int player_id, int damage);

/**
 * @brief 闇属性攻撃による即死を適用します（防御力を貫通してHPが0になる）。
 *
 * 守護神の退散判定は「攻撃のダメージでHPが減ったこと」に対して行うものであり、
 * このHPを0にする処理自体は退散判定の対象外です。呼び出し側は先に
 * apply_damage_without_revive() でダメージを適用しておいてください。
 */
void apply_darkness_instant_death(InternalState &state, int player_id);

/**
 * @brief 自分自身に闇属性攻撃を撃った場合の死亡処理をまとめて行います。
 *
 * 武器・雑貨経路と奇跡経路の2箇所から呼ばれます。以前は奇跡経路に即死処理が
 * 無く、自分に＜闇＞を撃っても攻撃力分のダメージしか入りませんでした。
 */
void apply_darkness_self_death(InternalState &state, int player_id, int damage);

/**
 * @brief 仮置きカード群の評価結果から、保留中の攻撃パラメータを設定します。
 *
 * 通常攻撃・奇跡攻撃・全体攻撃の3経路がそれぞれ同じ代入を並べており、全体攻撃の
 * 経路だけ pending_attack_curse を設定していませんでした。そのため霧の扇や
 * ＜閃光＞といった全体攻撃カードの状態異常が一切適用されませんでした。
 *
 * pending_is_group_attack はカードを仮置きした時点で確定するのでここでは触りません。
 */
void set_pending_from_staged_attack(InternalState &state, int attacker,
                                    const StagedAttackInfo &info, int target);

/**
 * @brief 自分自身を対象にした攻撃（武器・奇跡の共通処理）を解決します。
 *
 * ダメージ適用（闇属性なら即死）・カード効果・状態異常付与を `times` 回行い、
 * 最後に太陽のお守りによる復活を判定します。
 *
 * 武器経路と奇跡経路で別々に書かれていたため、闇属性の即死が奇跡側にしか無く、
 * 闇属性の「武器」を自分に撃っても攻撃力分のダメージしか入らない不具合がありました。
 *
 * @param times 連撃回数（蜃気楼など）。奇跡は連撃を持たないので常に1。
 */
void resolve_self_targeted_attack(InternalState &state, int attacker,
                                  const StagedAttackInfo &info,
                                  const StagedCardIds &used_cards, int times);

/**
 * @brief 天国病の発作による死亡を適用します。
 *
 * 闇属性即死と違い、発作は病気による死なので守護神の退散判定を行い、
 * 太陽のお守りによる復活も発生します。
 */
void apply_heaven_seizure_death(InternalState &state, int player_id);

/**
 * @brief ダメージによってHPが減少した際、一定確率で守護神を離脱させます。
 * @param hp_decreased このダメージ適用でHPが実際に減少したか。
 */
void try_guardian_leave(InternalState &state, int player_id, bool hp_decreased);

/**
 * @brief プレイヤーに病気を適用・悪化させます。
 */
void apply_sickness(InternalState &state, int player_id, SicknessType new_sick);

/**
 * @brief 病気を無条件で上書きします（悪化の規則を適用しない）。
 * 「必ずこの病気にする」効果に使います。SICKNESS_NONE を渡した場合は
 * cure_sickness() に委譲されます。
 */
void set_sickness(InternalState &state, int player_id, SicknessType sick);

/**
 * @brief 病気を治します。病気でなければ何もしません。
 *
 * 直接 state.sickness に SICKNESS_NONE を代入すると EFFECT_SICKNESS イベントが
 * 出ず、イベント履歴（観測に入る）から「治った」ことが読み取れなくなります。
 * 呪いの remove_curse() と対になるヘルパーです。
 */
void cure_sickness(InternalState &state, int player_id);


/**
 * @brief 死亡判定および昇天弓の発射、お守りでの復活を処理します。
 * @return 昇天弓の発射などにより防御フェイズが起動され、ゲームループを一時停止する場合は true。
 */
bool run_death_check(InternalState &state);
bool run_immediate_revive(InternalState &state);
void execute_money_deduction(InternalState &state, int player, int amount);

/**
 * @brief 「売る」アクションにおける商品の引き渡しおよび決済の解決を行います。
 * @param state ゲーム状態。
 * @param seller 売り手プレイヤーID。
 * @param buyer 買い手プレイヤーID。
 */
void execute_sell_resolution(InternalState &state, int seller, int buyer);

/**
 * @brief 相手のアクションに対して「スーパーミラー」での反射を試み、成功した場合はロールをスワップします。
 * @param state ゲーム状態。
 * @param action 実行されたアクション。
 * @param me アクターID。
 * @param opp 対戦相手ID。
 * @return 反射に成功した（スーパーミラーを使用した）場合は true、そうでなければ false。
 */
bool try_execute_super_mirror_reflection(InternalState &state, ActionType action, int me, int opp);


// ============================================================================
// 各フェイズのステップハンドラ / Phase Step Handlers (phase_handlers.cpp)
// ============================================================================

/**
 * @brief メインフェイズ（PHASE_MAIN）でのアクション解決（祈る/捨てる/カード発動など）を行います。
 */
void step_phase_main(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief メイン対象選択フェイズ（PHASE_MAIN_TARGET_SELECT）で対象決定時の処理を行います。
 */
void step_phase_main_target_select(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 物理攻撃の追加・決定フェイズ（PHASE_ATTACK_PLUS）での処理を行います。
 */
void step_phase_attack_plus(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 物理防御フェイズ（PHASE_DEFENSE）での処理を行います。
 */
void step_phase_defense(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 奇跡攻撃の追加・決定フェイズ（PHASE_MIRACLE_PLUS）での処理を行います。
 */
void step_phase_miracle_plus(InternalState &state, ActionType action, int me, int opp);
void step_phase_group_weapon(InternalState &state, ActionType action, int me, int opp);
void step_phase_group_miracle(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）での処理を行います。
 */
void step_phase_miracle_defense(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 売るカードの選択フェイズ（PHASE_SELL_SELECT）での処理を行います。
 */
void step_phase_sell_select(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 売却のスーパーミラー反射・受諾選択フェイズ（PHASE_SELL_SELECT_MIRROR）での処理を行います。
 */
void step_phase_sell_select_mirror(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 購入のスーパーミラー反射・受諾選択フェイズ（PHASE_BUY_SELECT_MIRROR）での処理を行います。
 */
void step_phase_buy_select_mirror(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 雑貨のスーパーミラー反射・受諾選択フェイズ（PHASE_SUNDRY_SELECT_MIRROR）での処理を行います。
 */
void step_phase_sundry_select_mirror(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 購入意思決定フェイズ（PHASE_BUY）での処理を行います。
 */
void step_phase_buy(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 両替フェイズ（PHASE_EXCHANGE_HP / PHASE_EXCHANGE_MP）での処理を行います。
 */
void step_phase_exchange(InternalState &state, ActionType action, int me, int opp);

/**
 * @brief 捨てるカード選択フェイズ（PHASE_DISCARD）での処理を行います。
 */
void step_phase_discard(InternalState &state, ActionType action, int me, int opp);


// ============================================================================
// 合法手チェック関数 / Phase Legal Checking Handlers (legal_actions.cpp)
// ============================================================================

/**
 * @brief メインフェイズ（PHASE_MAIN）における合法アクションを判定します。
 */
void legal_phase_main(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 対象選択フェイズ（PHASE_MAIN_TARGET_SELECT）における合法アクションを判定します。
 */
void legal_phase_main_target_select(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 物理攻撃追加フェイズ（PHASE_ATTACK_PLUS）における合法アクションを判定します。
 */
void legal_phase_attack_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 物理防御フェイズ（PHASE_DEFENSE）における合法アクションを判定します。
 */
void legal_phase_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);
void legal_phase_group_weapon(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);
void legal_phase_group_miracle(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 奇跡攻撃追加フェイズ（PHASE_MIRACLE_PLUS）における合法アクションを判定します。
 */
void legal_phase_miracle_plus(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 奇跡防御フェイズ（PHASE_MIRACLE_DEFENSE）における合法アクションを判定します。
 */
void legal_phase_miracle_defense(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 相手の売る/買う/雑貨等のアクションを反射するスーパーミラーの選択可否を判定します。
 */
void legal_mirror_selection(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me);

/**
 * @brief 購入反射選択フェイズ（PHASE_BUY_SELECT_MIRROR）における合法アクションを判定します。
 */
void legal_phase_buy_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 雑貨反射選択フェイズ（PHASE_SUNDRY_SELECT_MIRROR）における合法アクションを判定します。
 */
void legal_phase_sundry_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 売るカード選択フェイズ（PHASE_SELL_SELECT）における合法アクションを判定します。
 */
void legal_phase_sell_select(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 売却反射選択フェイズ（PHASE_SELL_SELECT_MIRROR）における合法アクションを判定します。
 */
void legal_phase_sell_select_mirror(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 購入フェイズ（PHASE_BUY）における合法アクションを判定します。
 */
void legal_phase_buy(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 両替数値選択フェイズ（PHASE_EXCHANGE_HP / PHASE_EXCHANGE_MP）における合法アクションを判定します。
 */
void legal_phase_exchange(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);

/**
 * @brief 捨てるカード選択フェイズ（PHASE_DISCARD）における合法アクションを判定します。
 */
void legal_phase_discard(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE], int me, int opp);
