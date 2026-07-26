"""Observation feature layout configuration.

Defines the mapping between observation vector indices and feature types
for the GodField RL environment. Must stay in sync with types.h Observation struct.

C++ 側が公開している定数（手札枚数・履歴長・行動空間）はそこから取得する。
値をコピーするとC++側の変更に追従できず、観測のオフセットが黙ってズレるため。
"""

import godfield_core

NUM_SICKNESS_TYPES = 5
NUM_CURSE_TYPES = 4
NUM_GUARDIAN_TYPES = 11
NUM_PHASES = 18
EVENT_SIZE = 5

MAX_HAND_SIZE = godfield_core.MAX_HAND_SIZE
HISTORY_LENGTH = godfield_core.HISTORY_LENGTH
ACTION_SPACE_SIZE = godfield_core.ACTION_SPACE_SIZE

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

# History Events (mixed, card IDs are at index 2 of each 5-float event)
HISTORY_START = offset
offset += HISTORY_LENGTH * EVENT_SIZE

# History Head (continuous)
HISTORY_HEAD_START = offset
offset += 1

TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK = offset
