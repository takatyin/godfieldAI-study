"""Observation feature layout configuration.

Defines the mapping between observation vector indices and feature types
for the GodField RL environment. Must stay in sync with types.h Observation struct.

ブロックの長さはすべてC++側が公開している定数から取得する。値をコピーすると
C++側の変更に追従できず、観測のオフセットが黙ってズレる（例外は出ないので、
学習の精度が落ちるだけで気付けない）。

このオフセット表とC++の Observation 構造体が整合していることは
tests/test_observation_layout.py が検証している。torch を必要としないので、
学習まわりの依存を入れない CI でも実行される。
"""

import godfield_core

NUM_SICKNESS_TYPES = godfield_core.NUM_SICKNESS_TYPES
NUM_CURSE_TYPES = godfield_core.NUM_CURSE_TYPES
NUM_GUARDIAN_TYPES = godfield_core.NUM_GUARDIAN_TYPES
NUM_PHASES = godfield_core.NUM_PHASES
EVENT_SIZE = godfield_core.EVENT_SIZE

MAX_HAND_SIZE = godfield_core.MAX_HAND_SIZE
HISTORY_LENGTH = godfield_core.HISTORY_LENGTH
ACTION_SPACE_SIZE = godfield_core.ACTION_SPACE_SIZE

# カード埋め込みテーブルの語彙数。
#
# ここだけは C++ から取得できない。feature_config は init_game_logic より先に
# import されるため（train.py が godfield_rl を import した時点ではカードマスタが
# まだ読み込まれておらず、get_registry_size() は 0 を返す）。
# 実際の枚数を賄えているかは tests/test_observation_layout.py が検証する。
NUM_CARD_TYPES = 294  # Max ID is 293, so 294 cards

# Offset calculations
offset = 0

# 6 continuous floats
STAT_START = offset
STAT_LEN = 6
offset += STAT_LEN

# Sickness (One-hot, 5 + 5)
SICKNESS_START = offset
SICKNESS_LEN = NUM_SICKNESS_TYPES * 2
offset += SICKNESS_LEN

# Curses (Multi-hot, 4 + 4)
CURSES_START = offset
CURSES_LEN = NUM_CURSE_TYPES * 2
offset += CURSES_LEN

# Guardian (One-hot, 11 + 11)
GUARDIAN_START = offset
GUARDIAN_LEN = NUM_GUARDIAN_TYPES * 2
offset += GUARDIAN_LEN

# Other continuous
MISC_START = offset
MISC_LEN = 5  # incoming_damage, current_staged_defense, is_apocalypse, turn_progress, turns_to_apocalypse
offset += MISC_LEN

# 手札の枚数（自分, 相手）。MAX_HAND_SIZE で正規化済み。
# カードID配列からは枚数を読み取れないため独立した次元にしている
# （相手は非公開手札と空きスロットが同じ値、自分は key_padding_mask で
# 空きスロットが注意から外れるため）。
HAND_COUNT_START = offset
HAND_COUNT_LEN = 2
offset += HAND_COUNT_LEN

# Phases (One-hot, 18)
PHASE_START = offset
PHASE_LEN = NUM_PHASES
offset += PHASE_LEN

# Total continuous features size before categorical cards
CONTINUOUS_FEATURES_SIZE = offset

# Categorical: Card IDs
HAND_CARDS_START = offset
offset += MAX_HAND_SIZE
STAGED_CARDS_START = offset
offset += MAX_HAND_SIZE
OPP_HAND_CARDS_START = offset
offset += MAX_HAND_SIZE
OPP_STAGED_CARDS_START = offset
offset += MAX_HAND_SIZE

# カードごとの属性。上のカードID配列と同じ並びで対応する。
# HAND_KNOWN_TO_OPP は HAND_CARDS と、OPP_DEPLOYED は OPP_HAND_CARDS と対応する。
HAND_KNOWN_TO_OPP_START = offset
offset += MAX_HAND_SIZE
OPP_DEPLOYED_START = offset
offset += MAX_HAND_SIZE

# History Events (mixed, card IDs are at index 2 of each 5-float event)
HISTORY_START = offset
offset += HISTORY_LENGTH * EVENT_SIZE

# History Head (continuous)
HISTORY_HEAD_START = offset
offset += 1

TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK = offset
