import random

import godfield_core

# 手札スロットの選択は ACTION_SELECT_HAND_0..17 の 18 種
FIRST_HAND_ACTION = int(godfield_core.ActionType.ACTION_SELECT_HAND_0)
NUM_HAND_ACTIONS = 18
# 「相手を対象 / 買う / 承諾」と「自分を対象 / 買わない / 確定」。フェイズによって意味が変わる
ACTION_TARGET_OPP = int(godfield_core.ActionType.ACTION_TARGET_OPP)
ACTION_TARGET_SELF = int(godfield_core.ActionType.ACTION_TARGET_SELF)


def get_ai_action(state):
    """現在の手番プレイヤーの行動を、単純なヒューリスティックで選びます。"""
    legal = godfield_core.get_legal_actions(state)
    valid_actions = [idx for idx, val in enumerate(legal) if val]
    if not valid_actions:
        return None

    # 1. 決定系の行動が可能ならそれを優先し、仮置きや防御を確定させる
    if ACTION_TARGET_OPP in valid_actions:
        return ACTION_TARGET_OPP
    if ACTION_TARGET_SELF in valid_actions:
        return ACTION_TARGET_SELF

    # 2. 祈る・捨てるより、手札のカードを使うことを優先する
    actor = state.current_actor_id
    hand_actions = [a for a in valid_actions if FIRST_HAND_ACTION <= a < FIRST_HAND_ACTION + NUM_HAND_ACTIONS]
    non_empty_hand_actions = [
        a for a in hand_actions if state.get_apparent_hand(actor, a - FIRST_HAND_ACTION) != godfield_core.CARD_EMPTY
    ]
    if non_empty_hand_actions:
        return random.choice(non_empty_hand_actions)

    # 3. どれも該当しなければ合法手からランダムに選ぶ
    return random.choice(valid_actions)
