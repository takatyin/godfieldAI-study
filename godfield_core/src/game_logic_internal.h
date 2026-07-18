#pragma once
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
 * @brief カードドロー時の確率分布。
 */
extern std::discrete_distribution<int> g_drop_distribution;


// ============================================================================
// ヘルパー関数 / Helper Functions
// ============================================================================

/**
 * @brief 指定されたカードが「捨てる」ことが可能なカードであるかを判定します。
 * @param card_id 判定対象のカードID。
 * @return 捨てられるカードであれば true、そうでなければ false。
 */
bool is_discardable_card(int card_id);

/**
 * @brief 指定されたカードが「奇跡の消費MPを0にする」精霊の神器であるかを判定します。
 * @param card_id 判定対象のカードID。
 * @return 精霊の神器であれば true、そうでなければ false。
 */
bool is_spiritual_zero_mp_card(int card_id);

/**
 * @brief 仮置き場（staged_cards）に最後に置かれたカードが「奇跡」であるかを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 最後のカードが奇跡であれば true、そうでなければ false。
 */
bool is_last_staged_card_miracle(const InternalState &state, int player_id);

/**
 * @brief 現在の仮置き場（staged_cards）の内容から、今回の攻撃が「武器攻撃」であるかを判定します。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 武器攻撃（物理）であれば true、奇跡攻撃（属性）であれば false。
 */
bool is_weapon_attack(const InternalState &state, int player_id);

/**
 * @brief 奇跡を展開し、6つの上限制限（FIFO）を処理します。
 */
void deploy_miracle(InternalState &state, int player_id, int slot_idx);

/**
 * @brief 奇跡の展開を解除し、展開順序バッファから削除します。
 */
void undeploy_miracle(InternalState &state, int player_id, int slot_idx);

void clear_hand_slot(InternalState &state, int player_id, int slot_idx);
void confirm_card(InternalState &state, int player_id, int slot_idx);
void add_card_to_hand_slot(InternalState &state, int player_id, int slot_idx, int card_id, bool is_drawn);
DreamGroup get_dream_group(int card_id);
DreamGroup calculate_dream_group(int card_id);

/**
 * @brief 仮置き場（staged_cards）に積まれているカードの合計消費MPを計算します（精霊補正あり）。
 * @param state ゲーム状態。
 * @param player_id 対象プレイヤーID。
 * @return 合計消費MP。
 */
int calculate_staged_mp_cost(const InternalState &state, int player_id);

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
bool is_active_reaction_card(int card_id, GamePhase phase, Element attack_element);

/**
 * @brief 対象プレイヤーの仮置き場（staged_cards）に積まれているカードのID一覧を取得します。
 * @param state ゲーム状態。
 * @param player 対象プレイヤーID。
 * @return カードIDのリスト。
 */
std::vector<int> get_staged_card_ids(const InternalState &state, int player);


// ============================================================================
// 取引・戦闘解決 / Combat & Trade Resolutions (combat_resolution.cpp)
// ============================================================================

/**
 * @brief 使用されたカードの効果（HP/MP回復、状態異常付与、その他雑貨効果）をターゲットプレイヤーに適用します。
 * @param state ゲーム状態。
 * @param target_id 効果を適用されるプレイヤーID。
 * @param used_card_ids 使用されたカードのIDリスト。
 */
void apply_card_effects_to_target(InternalState &state, int target_id, const std::vector<int>& used_card_ids);

void apply_curse_to_player(InternalState &state, int player_id, HitCurse curse);

/**
 * @brief プレイヤーに病気を適用・悪化させます。
 */
void apply_sickness(InternalState &state, int player_id, SicknessType new_sick);


/**
 * @brief 死亡判定および昇天弓の発射、お守りでの復活を処理します。
 * @return 昇天弓の発射などにより防御フェイズが起動され、ゲームループを一時停止する場合は true。
 */
bool run_death_check(InternalState &state);

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
