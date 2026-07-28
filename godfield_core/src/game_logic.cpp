#include "game_logic.h"
#include "game_logic_internal.h"
#include <vector>
#include <algorithm>
#include <cstring>
#include <stdexcept>
#include <string>


/**
 * @brief ゲームのルール適用と状態更新 (Game Logic Core)
 *
 * 与えられた `InternalState` と選択された `action` を元に、
 * ゴッドフィールドのルールに従って状態を1マイクロステップ分だけ進める純粋なロジック関数。
 * 各フェイズごとの処理は `phase_handlers.cpp` 内の `step_phase_X` 関数に委譲されます。
 *
 * @param state 現在のゲーム状態 (参照渡しの破壊的更新)
 * @param action 実行されたアクションID
 */
void step_game(InternalState& state, ActionType action) {
    if (state.is_done) return;

    ActionType current_action = action;
    bool is_first_iteration = true;
    int micro_step_count = 0;

    while (!state.is_done) {
        // 安全のため無限ループを防止
        if (micro_step_count++ > 1000) {
            break;
        }

        int me = state.current_actor_id;
        int opp = 1 - me;

        if (state.mushroom_turns > 0) {
            // 合法手の中からランダムに選択
            bool legal_actions[ACTION_SPACE_SIZE];
            get_legal_actions(state, legal_actions);
            std::vector<int> valids;
            for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
                if (legal_actions[i]) {
                    valids.push_back(i);
                }
            }
            if (valids.empty()) {
                break;
            }
            int idx = roll_range(state, RollKind::MUSHROOM_ACTION, 0,
                                 static_cast<int>(valids.size()) - 1);
            current_action = static_cast<ActionType>(valids[idx]);
        } else {
            // ご乱心が終了し、かつ最初のステップでない場合は操作を待つためループを抜ける
            if (!is_first_iteration) {
                break;
            }
        }
        is_first_iteration = false;

        // 行動の合法性チェック
        bool legal_actions[ACTION_SPACE_SIZE];
        get_legal_actions(state, legal_actions);
        if (current_action < 0 || current_action >= ACTION_SPACE_SIZE || !legal_actions[current_action]) {
            break; 
        }

        // 【夢状態の確定（Reveal）および合法性再検証（セーフガード）処理】
        // プレイヤーがターゲットの決定（ACTION_TARGET_SELF/OPP）や、行動の確定（ACTION_CONFIRM）などの
        // 「行動を確定させるアクション」を入力した時点で、仮置きしているカードの真の姿を公開します。
        if ((current_action == ACTION_TARGET_SELF || 
             current_action == ACTION_TARGET_OPP || 
             current_action == ACTION_CONFIRM) && 
            state.num_staged_cards[me] > 0) {
            
            // 1. 仮置きされているすべての手札の真偽状態を確定させる（Reveal）
            //    これにより is_confirmed[me][slot] = true となり、apparent_hand が true_hand の値に同期されます。
            confirm_all_staged_cards(state, me);
            
            // 2. 公開された「真の手札情報」に基づいて、現在のアクションの合法性を再判定します。
            //    ※通常ルールでは、夢の偽装グループは使用タイミング（timing等）が一致する神器同士で厳密に
            //      分類されているため、見た目で合法なら真の姿でも必ず合法になります（非合法化は起きません）。
            //      この再判定は、将来的なYamlカード定義の不整合、カスタムルールの追加、またはテスト時の
            //      不整合状態の混入を防ぐための防衛的プログラミング（セーフガード）として機能します。
            bool true_legal_actions[ACTION_SPACE_SIZE];
            get_legal_actions(state, true_legal_actions);
            
            // 3. 万が一、公開された真の手札情報に基づいて現在のアクションが「非合法」と判定された場合：
            //    (※正常に分類された夢グループの下では絶対に到達しない想定 / NEVER_REACH)
            if (!true_legal_actions[current_action]) {
                // 【ロールバック処理の実行】
                // 仮置きしていたカードをすべてプレイヤーの手札に戻します（使用フラグ is_used を false にクリア）。
                // ただし、真の姿が公開（確定）された事実自体は維持されます。
                for (int i = 0; i < state.num_staged_cards[me]; ++i) {
                    int slot = staged_hand_slot(state, me, i);
                    if (slot != NO_HAND_SLOT) state.is_used[me][slot] = false;
                }
                state.num_staged_cards[me] = 0;
                
                // カード選択を開始する前の状態（メインフェイズ）に進行状況を安全に巻き戻します。
                if (state.current_phase == GamePhase::PHASE_MAIN_TARGET_SELECT ||
                    state.current_phase == GamePhase::PHASE_ATTACK_PLUS ||
                    state.current_phase == GamePhase::PHASE_GROUP_WEAPON ||
                    state.current_phase == GamePhase::PHASE_GROUP_MIRACLE_PLUS ||
                    state.current_phase == GamePhase::PHASE_MIRACLE_PLUS) {
                    state.current_phase = GamePhase::PHASE_MAIN;
                }
                
                // このステップでの進行を中断し、プレイヤーの新たな選択入力を待つためループを抜けます。
                break;
            }
        }

        // 現在のフェイズに応じた個別ハンドラの呼び出し
        switch (state.current_phase) {
            case GamePhase::PHASE_MAIN:
                step_phase_main(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_MAIN_TARGET_SELECT:
                step_phase_main_target_select(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_ATTACK_PLUS:
                step_phase_attack_plus(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_GROUP_WEAPON:
                step_phase_group_weapon(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_DEFENSE:
                step_phase_defense(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_MIRACLE_PLUS:
                step_phase_miracle_plus(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_GROUP_MIRACLE_PLUS:
                step_phase_group_miracle(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_MIRACLE_DEFENSE:
                step_phase_miracle_defense(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_SELL_SELECT:
                step_phase_sell_select(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_SELL_SELECT_MIRROR:
                step_phase_sell_select_mirror(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_BUY_SELECT_MIRROR:
                step_phase_buy_select_mirror(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_SUNDRY_SELECT_MIRROR:
                step_phase_sundry_select_mirror(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_BUY:
                step_phase_buy(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_EXCHANGE_HP:
            case GamePhase::PHASE_EXCHANGE_MP:
                step_phase_exchange(state, current_action, me, opp);
                break;
            case GamePhase::PHASE_DISCARD:
                step_phase_discard(state, current_action, me, opp);
                break;
            default:
                break;
        }

        // ターン終了処理 (PHASE_END) の自動解決ループ
        while (!state.is_done) {
            if (state.current_phase == GamePhase::PHASE_END) {
                bool paused = resolve_turn_end_steps(state);
                if (paused) {
                    break;
                }
            } else {
                break;
            }
        }

        // ご乱心が解除されたら通常の操作受付に戻る
        if (state.mushroom_turns == 0) {
            break;
        }
    }
}

/**
 * @brief 現在のゲーム状態において、どのアクションが合法手かを判定してマスクを返します。
 *        各フェイズごとのチェックは `legal_actions.cpp` 内の `legal_phase_X` 関数に委譲されます。
 *
 * @param state 現在のゲーム状態
 * @param legal_actions 長さACTION_SPACE_SIZEのbool配列。結果が格納されます。
 */
void get_legal_actions(const InternalState &state, bool legal_actions[ACTION_SPACE_SIZE]) {
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) legal_actions[i] = false;
    if (state.is_done) return;

    int me = state.current_actor_id;
    int opp = 1 - me;

    if (state.hp[me] <= 0) {
        if (state.current_phase == GamePhase::PHASE_DEFENSE || 
            state.current_phase == GamePhase::PHASE_MIRACLE_DEFENSE ||
            state.current_phase == GamePhase::PHASE_SUNDRY_SELECT_MIRROR ||
            state.current_phase == GamePhase::PHASE_SELL_SELECT_MIRROR ||
            state.current_phase == GamePhase::PHASE_BUY_SELECT_MIRROR) {
            legal_actions[ACTION_CONFIRM] = true;
            return;
        }
    }

    switch (state.current_phase) {
        case GamePhase::PHASE_MAIN:
            legal_phase_main(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MAIN_TARGET_SELECT:
            legal_phase_main_target_select(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_ATTACK_PLUS:
            legal_phase_attack_plus(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_GROUP_WEAPON:
            legal_phase_group_weapon(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_DEFENSE:
            legal_phase_defense(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_PLUS:
            legal_phase_miracle_plus(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_GROUP_MIRACLE_PLUS:
            legal_phase_group_miracle(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_MIRACLE_DEFENSE:
            legal_phase_miracle_defense(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT:
            legal_phase_sell_select(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SELL_SELECT_MIRROR:
            legal_phase_sell_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_BUY:
            legal_phase_buy(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_BUY_SELECT_MIRROR:
            legal_phase_buy_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_SUNDRY_SELECT_MIRROR:
            legal_phase_sundry_select_mirror(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_EXCHANGE_HP:
        case GamePhase::PHASE_EXCHANGE_MP:
            legal_phase_exchange(state, legal_actions, me, opp);
            break;
        case GamePhase::PHASE_DISCARD:
            legal_phase_discard(state, legal_actions, me, opp);
            break;
        default:
            break;
    }
}

/**
 * @brief 現在のゲーム状態において、合法手が1つしかない場合はそのアクションIDを返します。
 *        （自動進行用の判定で使用されます）
 *
 * @param state 現在のゲーム状態
 * @return 合法アクションが唯一存在する場合はそのアクションID。それ以外（0個、または2個以上）の場合は -1。
 */
int get_single_legal_action(const InternalState& state) {
    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    
    int valid_count = 0;
    int last_valid = -1;
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
        if (legal_actions[i]) {
            valid_count++;
            last_valid = i;
            if (valid_count > 1) return -1;
        }
    }
    if (valid_count == 1) {
        int actor = state.current_actor_id;
        GamePhase phase = state.current_phase;
        bool is_defense_phase = (phase == GamePhase::PHASE_DEFENSE || phase == GamePhase::PHASE_MIRACLE_DEFENSE);
        bool is_mirror_reaction_phase = (phase == GamePhase::PHASE_SUNDRY_SELECT_MIRROR || 
                                         phase == GamePhase::PHASE_SELL_SELECT_MIRROR || 
                                         phase == GamePhase::PHASE_BUY_SELECT_MIRROR);

        if (is_defense_phase || is_mirror_reaction_phase) {
            // 防具・鏡を1枚も積んでいない(最初から有効な防具・反射カードがない)場合は ACTION_CONFIRM を自動返却して進行
            if (state.num_staged_cards[actor] == 0 && last_valid == ACTION_CONFIRM) {
                return ACTION_CONFIRM;
            }
            // カードを積んだ後は ACTION_CONFIRM しか残っていなくても自動進行せず待機
            if (last_valid == ACTION_CONFIRM) {
                return -1;
            }
        }

        // その他の確定操作 (ACTION_TARGET_OPP, ACTION_TARGET_SELF) は自動実行せずプレイヤーの入力を待つ
        if (last_valid == ACTION_TARGET_OPP || last_valid == ACTION_TARGET_SELF) {
            return -1;
        }
        return last_valid;
    }
    return -1;
}

/**
 * @brief 「解決中の攻撃・取引」に関するフィールドを未設定の状態に戻します。
 *
 * これらは 0 が有効な値（プレイヤーID 0、カードID 0）になってしまうため、
 * 番兵は -1 / CARD_EMPTY でなければなりません。ゼロ埋めしただけの状態を
 * 「まっさらな盤面」として扱うと、pending_initiator が「プレイヤー0が仕掛けた」
 * という意味を持ってしまい、記録漏れを検出できなくなります
 * （実際にテスト側の clear_state がそうなっており、守護神の罰金・わいろで
 * 実ゲームだけが例外で落ちる不具合を隠していました）。
 */
void reset_pending_resolution(InternalState &state) {
    state.attacker_id = -1;
    state.defender_id = -1;
    state.pending_initiator = -1;
    state.pending_attack_power = 0;
    state.pending_attack_element = ELEM_NONE;
    state.pending_absorption = false;
    state.pending_deal_same_damage = false;
    state.num_pending_counters = 0;
    state.pending_attack_curse = CURSE_NONE;
    state.pending_take_cp = false;
    state.pending_attack_source_id = CARD_EMPTY;
}

/**
 * @brief 新しいゲームの初期状態を組み立てます（強制手の消化は行いません）。
 */
static void setup_new_game_state(InternalState &state, int seed) {
    // 以前はここで乱数エンジンを3回初期化していた（一時オブジェクトの既定構築、
    // seed()、InternalState() の既定構築）。エンジンの状態をそのまま上書きするので、
    // 素の代入と seed() の1回だけで足りる。
    state = InternalState();
    state.rng.seed(static_cast<uint32_t>(seed));

    state.current_actor_id = 0;
    state.current_turn = 0;
    state.current_phase = GamePhase::PHASE_MAIN;
    state.turn_end_state = TurnEndSubstep::DEATH_CHECK_START;

    for (int p = 0; p < 2; ++p) {
        state.hp[p] = INITIAL_HP;
        state.mp[p] = INITIAL_MP;
        state.money[p] = INITIAL_MONEY;
        state.num_staged_cards[p] = 0;
        state.sickness[p] = SICKNESS_NONE;
        state.guardian[p] = GUARDIAN_NONE;
        state.pending_ascension_bows[p] = 0;
        state.heaven_seizure_occurred[p] = false;
    }
    std::memset(state.curses, 0, sizeof(state.curses));

    reset_pending_resolution(state);

    state.history_head = 0;
    state.history_count = 0;
    std::memset(state.history, 0, sizeof(state.history));

    // 初期手札を配る
    for (int p = 0; p < 2; ++p) {
        for (int h = 0; h < MAX_HAND_SIZE; ++h) {
            state.true_hand[p][h] = (h < INITIAL_HAND_SIZE) ? draw_card(state) : CARD_EMPTY;
            state.apparent_hand[p][h] = state.true_hand[p][h];
            state.is_confirmed[p][h] = true;
            state.is_known_to_opp[p][h] = false;
            state.is_used[p][h] = false;
            state.is_deployed[p][h] = false;
        }
    }

    state.is_done = false;
    state.p0_reward = 0.0f;
    state.p1_reward = 0.0f;
}

void init_new_game(InternalState &state, int seed) {
    // 初期局面に強制手（合法手が1つしかない状況）が続くことがあるため、
    // プレイヤーの入力が必要になるところまで進めてから返す。
    //
    // その過程でゲームが決着してしまうと、「開始局面」として決着済みの状態を
    // 返すことになる。学習側は reset 直後を done=false として扱うので、
    // 壊れた遷移を集めることになる。現在のカードデータでは開始直後に
    // ダメージ源が無いため起きないが、カードや初期条件を変えたときに
    // 静かに壊れないよう、シードを変えて配り直す。
    for (int attempt = 0; attempt < MAX_NEW_GAME_ATTEMPTS; ++attempt) {
        // 環境ごとのシード列と衝突しにくいよう、素数を掛けてずらす
        setup_new_game_state(state, seed + attempt * 7919);

        int auto_action;
        while (!state.is_done && (auto_action = get_single_legal_action(state)) != -1) {
            step_game(state, static_cast<ActionType>(auto_action));
        }
        if (!state.is_done) {
            return;
        }
    }
    throw std::runtime_error(
        "初期局面が強制手だけで決着してしまい、" + std::to_string(MAX_NEW_GAME_ATTEMPTS) +
        "回配り直しても開始できませんでした。カードデータか初期条件を確認してください。");
}

void make_observation(const InternalState& state, int player_id, Observation& obs) {
    std::memset(&obs, 0, sizeof(Observation));
    
    int me = player_id;
    int opp = 1 - me;
    
    bool is_me_fog = state.curses[me][CURSE_TYPE_FOG];
    
    // Normalizing logic
    obs.hp_me = state.hp[me] / 100.0f;
    obs.mp_me = state.mp[me] / 100.0f;
    obs.money_me = state.money[me] / 100.0f;

    if (is_me_fog) {
        obs.hp_opp = 0.0f;
        obs.mp_opp = 0.0f;
        obs.money_opp = 0.0f;
    } else {
        obs.hp_opp = state.hp[opp] / 100.0f;
        obs.mp_opp = state.mp[opp] / 100.0f;
        obs.money_opp = state.money[opp] / 100.0f;
    }
    
    obs.sickness_me[state.sickness[me]] = 1.0f;
    if (!is_me_fog) {
        obs.sickness_opp[state.sickness[opp]] = 1.0f;
    }
    
    obs.guardian_me[state.guardian[me]] = 1.0f;
    if (!is_me_fog) {
        obs.guardian_opp[state.guardian[opp]] = 1.0f;
    }

    for (int i = 0; i < 4; ++i) {
        obs.curses_me[i] = state.curses[me][i] ? 1.0f : 0.0f;
        if (is_me_fog) {
            obs.curses_opp[i] = 0.0f;
        } else {
            obs.curses_opp[i] = state.curses[opp][i] ? 1.0f : 0.0f;
        }
    }
    
    // Support and Special states
    obs.incoming_damage = (state.defender_id == me && state.pending_attack_power > 0) ? (static_cast<float>(state.pending_attack_power) / 100.0f) : 0.0f;

    int total_def = 0;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = staged_card_id(state, me, i);
        if (card_id >= 0 && card_id < static_cast<int>(g_card_registry.size())) {
            total_def += g_card_registry[card_id].defense_power;
        }
    }
    obs.current_staged_defense = static_cast<float>(total_def) / 100.0f;

    obs.is_apocalypse = (state.current_turn >= APOCALYPSE_TURN) ? 1.0f : 0.0f;
    // ターン数の打ち切りは行わないため current_turn は基準値を超えうる。
    // 観測は 0.0〜1.0 に収める契約なので上限で飽和させる。
    obs.turn_progress = std::min(1.0f, static_cast<float>(state.current_turn) / static_cast<float>(TURN_PROGRESS_SCALE_TURNS));
    obs.turns_to_apocalypse = static_cast<float>(std::max(0, APOCALYPSE_TURN - state.current_turn)) / static_cast<float>(APOCALYPSE_TURN);

    // Phase one-hot (18 dimensional)
    int phase_idx = static_cast<int>(state.current_phase);
    if (phase_idx >= 0 && phase_idx < NUM_PHASES) {
        obs.phase_one_hot[phase_idx] = 1.0f;
    }

    // Hand cards
    for (int i = 0; i < MAX_HAND_SIZE; ++i) {
        obs.hand_cards[i] = static_cast<float>(state.apparent_hand[me][i]);
    }

    // Staged cards
    // カードを解決できないエントリは飛ばし、opponent_hand_cards と同じく左詰めで格納する。
    std::fill(std::begin(obs.staged_cards), std::end(obs.staged_cards), static_cast<float>(CARD_EMPTY));
    int staged_count = 0;
    for (int i = 0; i < state.num_staged_cards[me]; ++i) {
        int card_id = staged_card_id(state, me, i);
        if (card_id == CARD_EMPTY) continue;
        obs.staged_cards[staged_count++] = static_cast<float>(card_id);
    }

    // Opponent hand cards (相手の公開手札のスロット位置リークを防ぐため、左詰めで格納する)
    int known_count = 0;
    std::fill(std::begin(obs.opponent_hand_cards), std::end(obs.opponent_hand_cards), 0.0f);
    if (!is_me_fog) {
        for (int i = 0; i < MAX_HAND_SIZE; ++i) {
            if (state.is_known_to_opp[opp][i] || state.is_deployed[opp][i]) {
                obs.opponent_hand_cards[known_count++] = static_cast<float>(state.true_hand[opp][i]);
            }
        }
    }

    // Opponent staged cards
    std::fill(std::begin(obs.opponent_staged_cards), std::end(obs.opponent_staged_cards), static_cast<float>(CARD_EMPTY));
    if (state.num_staged_cards[opp] > 0) {
        int opp_staged_count = 0;
        for (int i = 0; i < state.num_staged_cards[opp]; ++i) {
            int card_id = staged_card_id(state, opp, i);
            if (card_id == CARD_EMPTY) continue;
            obs.opponent_staged_cards[opp_staged_count++] = static_cast<float>(card_id);
        }
    } else if (state.pending_attack_source_id != CARD_EMPTY) {
        obs.opponent_staged_cards[0] = static_cast<float>(state.pending_attack_source_id);
    }

    // Legal actions mask
    bool legal_actions[ACTION_SPACE_SIZE];
    get_legal_actions(state, legal_actions);
    for (int i = 0; i < ACTION_SPACE_SIZE; ++i) {
        obs.action_mask[i] = legal_actions[i] ? 1.0f : 0.0f;
    }

    // Populate history metadata
    obs.history_head = static_cast<float>(state.history_head);

    // リングバッファを時系列順に展開 (2回のmemcpy)
    int head = state.history_head;
    int tail_count = HISTORY_LENGTH - head;
    std::memcpy(&obs.history[0], &state.history[head], tail_count * sizeof(GameEvent));
    std::memcpy(&obs.history[tail_count], &state.history[0], head * sizeof(GameEvent));

    // actor/target_id の視点正規化
    for (int i = 0; i < HISTORY_LENGTH; ++i) {
        GameEvent& ev = obs.history[i];
        if (ev.event_type == static_cast<float>(EventType::NONE)) {
            continue;
        }

        // Normalize actor and target_id (0 = observer/me, 1 = opponent)
        ev.actor = (static_cast<int>(ev.actor) == player_id) ? 0.0f : 1.0f;
        if (ev.target_id != -1.0f) {
            ev.target_id = (static_cast<int>(ev.target_id) == player_id) ? 0.0f : 1.0f;
        }
    }
}

Observation get_observation(const InternalState& state, int player_id) {
    Observation obs;
    make_observation(state, player_id, obs);
    return obs;
}

