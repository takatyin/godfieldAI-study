"""
GodField core engine and RL environment pool
"""
from __future__ import annotations
import collections.abc
import numpy
import numpy.typing
import typing
from . import CurseEvent
from . import SicknessEvent
__all__: list[str] = ['ACTION_CONFIRM', 'ACTION_DEAL_NO', 'ACTION_DEAL_YES', 'ACTION_DISCARD', 'ACTION_NUM_0', 'ACTION_NUM_1', 'ACTION_NUM_10', 'ACTION_NUM_11', 'ACTION_NUM_12', 'ACTION_NUM_13', 'ACTION_NUM_14', 'ACTION_NUM_15', 'ACTION_NUM_16', 'ACTION_NUM_17', 'ACTION_NUM_18', 'ACTION_NUM_19', 'ACTION_NUM_2', 'ACTION_NUM_20', 'ACTION_NUM_21', 'ACTION_NUM_22', 'ACTION_NUM_23', 'ACTION_NUM_24', 'ACTION_NUM_25', 'ACTION_NUM_26', 'ACTION_NUM_27', 'ACTION_NUM_28', 'ACTION_NUM_29', 'ACTION_NUM_3', 'ACTION_NUM_30', 'ACTION_NUM_31', 'ACTION_NUM_32', 'ACTION_NUM_33', 'ACTION_NUM_34', 'ACTION_NUM_35', 'ACTION_NUM_36', 'ACTION_NUM_37', 'ACTION_NUM_38', 'ACTION_NUM_39', 'ACTION_NUM_4', 'ACTION_NUM_40', 'ACTION_NUM_41', 'ACTION_NUM_42', 'ACTION_NUM_43', 'ACTION_NUM_44', 'ACTION_NUM_45', 'ACTION_NUM_46', 'ACTION_NUM_47', 'ACTION_NUM_48', 'ACTION_NUM_49', 'ACTION_NUM_5', 'ACTION_NUM_50', 'ACTION_NUM_51', 'ACTION_NUM_52', 'ACTION_NUM_53', 'ACTION_NUM_54', 'ACTION_NUM_55', 'ACTION_NUM_56', 'ACTION_NUM_57', 'ACTION_NUM_58', 'ACTION_NUM_59', 'ACTION_NUM_6', 'ACTION_NUM_60', 'ACTION_NUM_61', 'ACTION_NUM_62', 'ACTION_NUM_63', 'ACTION_NUM_64', 'ACTION_NUM_65', 'ACTION_NUM_66', 'ACTION_NUM_67', 'ACTION_NUM_68', 'ACTION_NUM_69', 'ACTION_NUM_7', 'ACTION_NUM_70', 'ACTION_NUM_71', 'ACTION_NUM_72', 'ACTION_NUM_73', 'ACTION_NUM_74', 'ACTION_NUM_75', 'ACTION_NUM_76', 'ACTION_NUM_77', 'ACTION_NUM_78', 'ACTION_NUM_79', 'ACTION_NUM_8', 'ACTION_NUM_80', 'ACTION_NUM_81', 'ACTION_NUM_82', 'ACTION_NUM_83', 'ACTION_NUM_84', 'ACTION_NUM_85', 'ACTION_NUM_86', 'ACTION_NUM_87', 'ACTION_NUM_88', 'ACTION_NUM_89', 'ACTION_NUM_9', 'ACTION_NUM_90', 'ACTION_NUM_91', 'ACTION_NUM_92', 'ACTION_NUM_93', 'ACTION_NUM_94', 'ACTION_NUM_95', 'ACTION_NUM_96', 'ACTION_NUM_97', 'ACTION_NUM_98', 'ACTION_NUM_99', 'ACTION_PRAY', 'ACTION_SELECT_HAND_0', 'ACTION_SELECT_HAND_1', 'ACTION_SELECT_HAND_10', 'ACTION_SELECT_HAND_11', 'ACTION_SELECT_HAND_12', 'ACTION_SELECT_HAND_13', 'ACTION_SELECT_HAND_14', 'ACTION_SELECT_HAND_15', 'ACTION_SELECT_HAND_16', 'ACTION_SELECT_HAND_17', 'ACTION_SELECT_HAND_2', 'ACTION_SELECT_HAND_3', 'ACTION_SELECT_HAND_4', 'ACTION_SELECT_HAND_5', 'ACTION_SELECT_HAND_6', 'ACTION_SELECT_HAND_7', 'ACTION_SELECT_HAND_8', 'ACTION_SELECT_HAND_9', 'ACTION_SPACE_SIZE', 'ACTION_TARGET_OPP', 'ACTION_TARGET_SELF', 'APOCALYPSE_DEVIL_THRESHOLDS', 'APOCALYPSE_TURN', 'ASCENSION_BOW_TRIGGERED_POWER', 'ATTACK_HIT', 'ATTACK_MISS', 'ActionType', 'BLACK_HOLE', 'BLOCK_ATTACK', 'BOUNCE_ATTACK', 'BUY_CARD', 'CARD_EMPTY', 'CLEANUP', 'CLEANUP_DEATH_CHECK', 'CONFIRM_ATTACK', 'CONFIRM_DEFENSE', 'CURSE_COLD', 'CURSE_DARK_CLOUD', 'CURSE_DREAM', 'CURSE_FEVER', 'CURSE_FLASH', 'CURSE_FOG', 'CURSE_HEAVEN', 'CURSE_HELL', 'CURSE_NONE', 'CurseEvent', 'CurseType', 'DEATH_CHECK_START', 'DENSE_FOG', 'DISCARD_CARD', 'DRAW_CARD', 'DREAM_DISGUISE_RATE', 'EARTH', 'ECLIPSE', 'EFFECT_CURSE', 'EFFECT_GUARDIAN', 'EFFECT_SICKNESS', 'ELEM_DARKNESS', 'ELEM_FIRE', 'ELEM_LIGHT', 'ELEM_NONE', 'ELEM_STONE', 'ELEM_WATER', 'ELEM_WOOD', 'EXCHANGE', 'Element', 'EnvPool', 'EventType', 'FINAL_DEATH_CHECK', 'GIGANTIC_TUB', 'GOLD_MINE', 'GUARDIAN_ACT', 'GUARDIAN_ACT_CHOICE_THRESHOLDS', 'GUARDIAN_ENTER', 'GUARDIAN_LEAVE', 'GameEvent', 'GamePhase', 'GuardianType', 'HEAL_HP', 'HEAL_MP', 'HISTORY_LENGTH', 'HitCurse', 'InternalState', 'JUPITER', 'MAGNETIC_STORM', 'MARS', 'MAX_HAND_SIZE', 'MERCURY', 'MOON', 'MUSHROOM', 'NEPTUNE', 'NONE', 'OBSERVATION_FEATURE_SIZE', 'OBSERVATION_SIZE', 'Observation', 'PASS_DEFENSE', 'PHASE_ATTACK_PLUS', 'PHASE_BUY', 'PHASE_BUY_SELECT_MIRROR', 'PHASE_DEFENSE', 'PHASE_DISCARD', 'PHASE_END', 'PHASE_EXCHANGE_HP', 'PHASE_EXCHANGE_MP', 'PHASE_GROUP_MIRACLE_PLUS', 'PHASE_GROUP_WEAPON', 'PHASE_GUARDIAN', 'PHASE_MAIN', 'PHASE_MAIN_TARGET_SELECT', 'PHASE_MIRACLE_DEFENSE', 'PHASE_MIRACLE_PLUS', 'PHASE_SELL_SELECT', 'PHASE_SELL_SELECT_MIRROR', 'PHASE_SUNDRY_SELECT_MIRROR', 'PLUTO', 'PhenomenonType', 'REACTION_BLOCK', 'REACTION_BOUNCE', 'REACTION_NONE', 'REACTION_REFLECT', 'REFLECT_DAMAGE', 'REFLECT_MIRROR', 'REFUSE_DEAL', 'RING_EFFECT', 'ROLL_MAX', 'ROLL_MIN', 'ReactionType', 'RollKind', 'SATURN', 'SAW_BOOM_BOOM_ATTACK_COUNT', 'SELL_CARD', 'SICKNESS_COLD', 'SICKNESS_DAMAGE', 'SICKNESS_FEVER', 'SICKNESS_HEAVEN', 'SICKNESS_HELL', 'SICKNESS_NONE', 'SICKNESS_WORSEN', 'STAGE_CARD', 'SUNSET', 'SUN_AMULET_REVIVE_HP', 'SicknessEvent', 'SicknessType', 'TAKE_DAMAGE', 'TIMING_ATK_DEFENCE', 'TIMING_ATK_PLUS', 'TIMING_MAIN_ATK', 'TIMING_MAIN_DEAL', 'TIMING_MAIN_MIRACLE', 'TIMING_MAIN_SUNDRY', 'TIMING_MIRACLE_DEFENCE', 'TIMING_MIRACLE_PLUS', 'TORNADO', 'TRIGGER_PHENOMENON', 'TURN_TRANSITION', 'TurnEndSubstep', 'UNSTAGE_CARD', 'URANUS', 'VENUS', 'WARM_CURRENT', 'clear_state', 'draw_card', 'get_absorption_sources', 'get_apocalypse_devils', 'get_card_name', 'get_draw_table_size', 'get_dream_candidates', 'get_guardian_action_cards', 'get_legal_actions', 'get_moon_miracles', 'get_observation', 'get_opponent_staged_cards_for_obs', 'get_registry_size', 'get_single_legal_action', 'init_game_logic', 'rng_clear_script', 'rng_consumed', 'rng_forbid_unscripted', 'rng_force', 'rng_pick_order', 'rng_script', 'rng_unconsumed_kinds', 'step_game']
class ActionType:
    """
    Members:
    
      ACTION_SELECT_HAND_0
    
      ACTION_SELECT_HAND_1
    
      ACTION_SELECT_HAND_2
    
      ACTION_SELECT_HAND_3
    
      ACTION_SELECT_HAND_4
    
      ACTION_SELECT_HAND_5
    
      ACTION_SELECT_HAND_6
    
      ACTION_SELECT_HAND_7
    
      ACTION_SELECT_HAND_8
    
      ACTION_SELECT_HAND_9
    
      ACTION_SELECT_HAND_10
    
      ACTION_SELECT_HAND_11
    
      ACTION_SELECT_HAND_12
    
      ACTION_SELECT_HAND_13
    
      ACTION_SELECT_HAND_14
    
      ACTION_SELECT_HAND_15
    
      ACTION_SELECT_HAND_16
    
      ACTION_SELECT_HAND_17
    
      ACTION_TARGET_OPP
    
      ACTION_DEAL_YES
    
      ACTION_TARGET_SELF
    
      ACTION_DEAL_NO
    
      ACTION_CONFIRM
    
      ACTION_PRAY
    
      ACTION_DISCARD
    
      ACTION_NUM_0
    
      ACTION_NUM_1
    
      ACTION_NUM_2
    
      ACTION_NUM_3
    
      ACTION_NUM_4
    
      ACTION_NUM_5
    
      ACTION_NUM_6
    
      ACTION_NUM_7
    
      ACTION_NUM_8
    
      ACTION_NUM_9
    
      ACTION_NUM_10
    
      ACTION_NUM_11
    
      ACTION_NUM_12
    
      ACTION_NUM_13
    
      ACTION_NUM_14
    
      ACTION_NUM_15
    
      ACTION_NUM_16
    
      ACTION_NUM_17
    
      ACTION_NUM_18
    
      ACTION_NUM_19
    
      ACTION_NUM_20
    
      ACTION_NUM_21
    
      ACTION_NUM_22
    
      ACTION_NUM_23
    
      ACTION_NUM_24
    
      ACTION_NUM_25
    
      ACTION_NUM_26
    
      ACTION_NUM_27
    
      ACTION_NUM_28
    
      ACTION_NUM_29
    
      ACTION_NUM_30
    
      ACTION_NUM_31
    
      ACTION_NUM_32
    
      ACTION_NUM_33
    
      ACTION_NUM_34
    
      ACTION_NUM_35
    
      ACTION_NUM_36
    
      ACTION_NUM_37
    
      ACTION_NUM_38
    
      ACTION_NUM_39
    
      ACTION_NUM_40
    
      ACTION_NUM_41
    
      ACTION_NUM_42
    
      ACTION_NUM_43
    
      ACTION_NUM_44
    
      ACTION_NUM_45
    
      ACTION_NUM_46
    
      ACTION_NUM_47
    
      ACTION_NUM_48
    
      ACTION_NUM_49
    
      ACTION_NUM_50
    
      ACTION_NUM_51
    
      ACTION_NUM_52
    
      ACTION_NUM_53
    
      ACTION_NUM_54
    
      ACTION_NUM_55
    
      ACTION_NUM_56
    
      ACTION_NUM_57
    
      ACTION_NUM_58
    
      ACTION_NUM_59
    
      ACTION_NUM_60
    
      ACTION_NUM_61
    
      ACTION_NUM_62
    
      ACTION_NUM_63
    
      ACTION_NUM_64
    
      ACTION_NUM_65
    
      ACTION_NUM_66
    
      ACTION_NUM_67
    
      ACTION_NUM_68
    
      ACTION_NUM_69
    
      ACTION_NUM_70
    
      ACTION_NUM_71
    
      ACTION_NUM_72
    
      ACTION_NUM_73
    
      ACTION_NUM_74
    
      ACTION_NUM_75
    
      ACTION_NUM_76
    
      ACTION_NUM_77
    
      ACTION_NUM_78
    
      ACTION_NUM_79
    
      ACTION_NUM_80
    
      ACTION_NUM_81
    
      ACTION_NUM_82
    
      ACTION_NUM_83
    
      ACTION_NUM_84
    
      ACTION_NUM_85
    
      ACTION_NUM_86
    
      ACTION_NUM_87
    
      ACTION_NUM_88
    
      ACTION_NUM_89
    
      ACTION_NUM_90
    
      ACTION_NUM_91
    
      ACTION_NUM_92
    
      ACTION_NUM_93
    
      ACTION_NUM_94
    
      ACTION_NUM_95
    
      ACTION_NUM_96
    
      ACTION_NUM_97
    
      ACTION_NUM_98
    
      ACTION_NUM_99
    """
    ACTION_CONFIRM: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_TARGET_SELF: 19>
    ACTION_DEAL_NO: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_TARGET_SELF: 19>
    ACTION_DEAL_YES: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_TARGET_OPP: 18>
    ACTION_DISCARD: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_DISCARD: 21>
    ACTION_NUM_0: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_0: 22>
    ACTION_NUM_1: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_1: 23>
    ACTION_NUM_10: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_10: 32>
    ACTION_NUM_11: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_11: 33>
    ACTION_NUM_12: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_12: 34>
    ACTION_NUM_13: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_13: 35>
    ACTION_NUM_14: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_14: 36>
    ACTION_NUM_15: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_15: 37>
    ACTION_NUM_16: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_16: 38>
    ACTION_NUM_17: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_17: 39>
    ACTION_NUM_18: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_18: 40>
    ACTION_NUM_19: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_19: 41>
    ACTION_NUM_2: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_2: 24>
    ACTION_NUM_20: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_20: 42>
    ACTION_NUM_21: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_21: 43>
    ACTION_NUM_22: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_22: 44>
    ACTION_NUM_23: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_23: 45>
    ACTION_NUM_24: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_24: 46>
    ACTION_NUM_25: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_25: 47>
    ACTION_NUM_26: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_26: 48>
    ACTION_NUM_27: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_27: 49>
    ACTION_NUM_28: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_28: 50>
    ACTION_NUM_29: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_29: 51>
    ACTION_NUM_3: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_3: 25>
    ACTION_NUM_30: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_30: 52>
    ACTION_NUM_31: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_31: 53>
    ACTION_NUM_32: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_32: 54>
    ACTION_NUM_33: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_33: 55>
    ACTION_NUM_34: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_34: 56>
    ACTION_NUM_35: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_35: 57>
    ACTION_NUM_36: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_36: 58>
    ACTION_NUM_37: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_37: 59>
    ACTION_NUM_38: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_38: 60>
    ACTION_NUM_39: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_39: 61>
    ACTION_NUM_4: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_4: 26>
    ACTION_NUM_40: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_40: 62>
    ACTION_NUM_41: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_41: 63>
    ACTION_NUM_42: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_42: 64>
    ACTION_NUM_43: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_43: 65>
    ACTION_NUM_44: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_44: 66>
    ACTION_NUM_45: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_45: 67>
    ACTION_NUM_46: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_46: 68>
    ACTION_NUM_47: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_47: 69>
    ACTION_NUM_48: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_48: 70>
    ACTION_NUM_49: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_49: 71>
    ACTION_NUM_5: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_5: 27>
    ACTION_NUM_50: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_50: 72>
    ACTION_NUM_51: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_51: 73>
    ACTION_NUM_52: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_52: 74>
    ACTION_NUM_53: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_53: 75>
    ACTION_NUM_54: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_54: 76>
    ACTION_NUM_55: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_55: 77>
    ACTION_NUM_56: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_56: 78>
    ACTION_NUM_57: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_57: 79>
    ACTION_NUM_58: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_58: 80>
    ACTION_NUM_59: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_59: 81>
    ACTION_NUM_6: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_6: 28>
    ACTION_NUM_60: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_60: 82>
    ACTION_NUM_61: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_61: 83>
    ACTION_NUM_62: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_62: 84>
    ACTION_NUM_63: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_63: 85>
    ACTION_NUM_64: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_64: 86>
    ACTION_NUM_65: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_65: 87>
    ACTION_NUM_66: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_66: 88>
    ACTION_NUM_67: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_67: 89>
    ACTION_NUM_68: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_68: 90>
    ACTION_NUM_69: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_69: 91>
    ACTION_NUM_7: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_7: 29>
    ACTION_NUM_70: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_70: 92>
    ACTION_NUM_71: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_71: 93>
    ACTION_NUM_72: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_72: 94>
    ACTION_NUM_73: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_73: 95>
    ACTION_NUM_74: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_74: 96>
    ACTION_NUM_75: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_75: 97>
    ACTION_NUM_76: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_76: 98>
    ACTION_NUM_77: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_77: 99>
    ACTION_NUM_78: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_78: 100>
    ACTION_NUM_79: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_79: 101>
    ACTION_NUM_8: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_8: 30>
    ACTION_NUM_80: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_80: 102>
    ACTION_NUM_81: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_81: 103>
    ACTION_NUM_82: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_82: 104>
    ACTION_NUM_83: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_83: 105>
    ACTION_NUM_84: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_84: 106>
    ACTION_NUM_85: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_85: 107>
    ACTION_NUM_86: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_86: 108>
    ACTION_NUM_87: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_87: 109>
    ACTION_NUM_88: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_88: 110>
    ACTION_NUM_89: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_89: 111>
    ACTION_NUM_9: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_9: 31>
    ACTION_NUM_90: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_90: 112>
    ACTION_NUM_91: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_91: 113>
    ACTION_NUM_92: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_92: 114>
    ACTION_NUM_93: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_93: 115>
    ACTION_NUM_94: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_94: 116>
    ACTION_NUM_95: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_95: 117>
    ACTION_NUM_96: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_96: 118>
    ACTION_NUM_97: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_97: 119>
    ACTION_NUM_98: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_98: 120>
    ACTION_NUM_99: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_NUM_99: 121>
    ACTION_PRAY: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_PRAY: 20>
    ACTION_SELECT_HAND_0: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_0: 0>
    ACTION_SELECT_HAND_1: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_1: 1>
    ACTION_SELECT_HAND_10: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_10: 10>
    ACTION_SELECT_HAND_11: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_11: 11>
    ACTION_SELECT_HAND_12: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_12: 12>
    ACTION_SELECT_HAND_13: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_13: 13>
    ACTION_SELECT_HAND_14: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_14: 14>
    ACTION_SELECT_HAND_15: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_15: 15>
    ACTION_SELECT_HAND_16: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_16: 16>
    ACTION_SELECT_HAND_17: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_17: 17>
    ACTION_SELECT_HAND_2: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_2: 2>
    ACTION_SELECT_HAND_3: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_3: 3>
    ACTION_SELECT_HAND_4: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_4: 4>
    ACTION_SELECT_HAND_5: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_5: 5>
    ACTION_SELECT_HAND_6: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_6: 6>
    ACTION_SELECT_HAND_7: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_7: 7>
    ACTION_SELECT_HAND_8: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_8: 8>
    ACTION_SELECT_HAND_9: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_SELECT_HAND_9: 9>
    ACTION_TARGET_OPP: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_TARGET_OPP: 18>
    ACTION_TARGET_SELF: typing.ClassVar[ActionType]  # value = <ActionType.ACTION_TARGET_SELF: 19>
    __members__: typing.ClassVar[dict[str, ActionType]]  # value = {'ACTION_SELECT_HAND_0': <ActionType.ACTION_SELECT_HAND_0: 0>, 'ACTION_SELECT_HAND_1': <ActionType.ACTION_SELECT_HAND_1: 1>, 'ACTION_SELECT_HAND_2': <ActionType.ACTION_SELECT_HAND_2: 2>, 'ACTION_SELECT_HAND_3': <ActionType.ACTION_SELECT_HAND_3: 3>, 'ACTION_SELECT_HAND_4': <ActionType.ACTION_SELECT_HAND_4: 4>, 'ACTION_SELECT_HAND_5': <ActionType.ACTION_SELECT_HAND_5: 5>, 'ACTION_SELECT_HAND_6': <ActionType.ACTION_SELECT_HAND_6: 6>, 'ACTION_SELECT_HAND_7': <ActionType.ACTION_SELECT_HAND_7: 7>, 'ACTION_SELECT_HAND_8': <ActionType.ACTION_SELECT_HAND_8: 8>, 'ACTION_SELECT_HAND_9': <ActionType.ACTION_SELECT_HAND_9: 9>, 'ACTION_SELECT_HAND_10': <ActionType.ACTION_SELECT_HAND_10: 10>, 'ACTION_SELECT_HAND_11': <ActionType.ACTION_SELECT_HAND_11: 11>, 'ACTION_SELECT_HAND_12': <ActionType.ACTION_SELECT_HAND_12: 12>, 'ACTION_SELECT_HAND_13': <ActionType.ACTION_SELECT_HAND_13: 13>, 'ACTION_SELECT_HAND_14': <ActionType.ACTION_SELECT_HAND_14: 14>, 'ACTION_SELECT_HAND_15': <ActionType.ACTION_SELECT_HAND_15: 15>, 'ACTION_SELECT_HAND_16': <ActionType.ACTION_SELECT_HAND_16: 16>, 'ACTION_SELECT_HAND_17': <ActionType.ACTION_SELECT_HAND_17: 17>, 'ACTION_TARGET_OPP': <ActionType.ACTION_TARGET_OPP: 18>, 'ACTION_DEAL_YES': <ActionType.ACTION_TARGET_OPP: 18>, 'ACTION_TARGET_SELF': <ActionType.ACTION_TARGET_SELF: 19>, 'ACTION_DEAL_NO': <ActionType.ACTION_TARGET_SELF: 19>, 'ACTION_CONFIRM': <ActionType.ACTION_TARGET_SELF: 19>, 'ACTION_PRAY': <ActionType.ACTION_PRAY: 20>, 'ACTION_DISCARD': <ActionType.ACTION_DISCARD: 21>, 'ACTION_NUM_0': <ActionType.ACTION_NUM_0: 22>, 'ACTION_NUM_1': <ActionType.ACTION_NUM_1: 23>, 'ACTION_NUM_2': <ActionType.ACTION_NUM_2: 24>, 'ACTION_NUM_3': <ActionType.ACTION_NUM_3: 25>, 'ACTION_NUM_4': <ActionType.ACTION_NUM_4: 26>, 'ACTION_NUM_5': <ActionType.ACTION_NUM_5: 27>, 'ACTION_NUM_6': <ActionType.ACTION_NUM_6: 28>, 'ACTION_NUM_7': <ActionType.ACTION_NUM_7: 29>, 'ACTION_NUM_8': <ActionType.ACTION_NUM_8: 30>, 'ACTION_NUM_9': <ActionType.ACTION_NUM_9: 31>, 'ACTION_NUM_10': <ActionType.ACTION_NUM_10: 32>, 'ACTION_NUM_11': <ActionType.ACTION_NUM_11: 33>, 'ACTION_NUM_12': <ActionType.ACTION_NUM_12: 34>, 'ACTION_NUM_13': <ActionType.ACTION_NUM_13: 35>, 'ACTION_NUM_14': <ActionType.ACTION_NUM_14: 36>, 'ACTION_NUM_15': <ActionType.ACTION_NUM_15: 37>, 'ACTION_NUM_16': <ActionType.ACTION_NUM_16: 38>, 'ACTION_NUM_17': <ActionType.ACTION_NUM_17: 39>, 'ACTION_NUM_18': <ActionType.ACTION_NUM_18: 40>, 'ACTION_NUM_19': <ActionType.ACTION_NUM_19: 41>, 'ACTION_NUM_20': <ActionType.ACTION_NUM_20: 42>, 'ACTION_NUM_21': <ActionType.ACTION_NUM_21: 43>, 'ACTION_NUM_22': <ActionType.ACTION_NUM_22: 44>, 'ACTION_NUM_23': <ActionType.ACTION_NUM_23: 45>, 'ACTION_NUM_24': <ActionType.ACTION_NUM_24: 46>, 'ACTION_NUM_25': <ActionType.ACTION_NUM_25: 47>, 'ACTION_NUM_26': <ActionType.ACTION_NUM_26: 48>, 'ACTION_NUM_27': <ActionType.ACTION_NUM_27: 49>, 'ACTION_NUM_28': <ActionType.ACTION_NUM_28: 50>, 'ACTION_NUM_29': <ActionType.ACTION_NUM_29: 51>, 'ACTION_NUM_30': <ActionType.ACTION_NUM_30: 52>, 'ACTION_NUM_31': <ActionType.ACTION_NUM_31: 53>, 'ACTION_NUM_32': <ActionType.ACTION_NUM_32: 54>, 'ACTION_NUM_33': <ActionType.ACTION_NUM_33: 55>, 'ACTION_NUM_34': <ActionType.ACTION_NUM_34: 56>, 'ACTION_NUM_35': <ActionType.ACTION_NUM_35: 57>, 'ACTION_NUM_36': <ActionType.ACTION_NUM_36: 58>, 'ACTION_NUM_37': <ActionType.ACTION_NUM_37: 59>, 'ACTION_NUM_38': <ActionType.ACTION_NUM_38: 60>, 'ACTION_NUM_39': <ActionType.ACTION_NUM_39: 61>, 'ACTION_NUM_40': <ActionType.ACTION_NUM_40: 62>, 'ACTION_NUM_41': <ActionType.ACTION_NUM_41: 63>, 'ACTION_NUM_42': <ActionType.ACTION_NUM_42: 64>, 'ACTION_NUM_43': <ActionType.ACTION_NUM_43: 65>, 'ACTION_NUM_44': <ActionType.ACTION_NUM_44: 66>, 'ACTION_NUM_45': <ActionType.ACTION_NUM_45: 67>, 'ACTION_NUM_46': <ActionType.ACTION_NUM_46: 68>, 'ACTION_NUM_47': <ActionType.ACTION_NUM_47: 69>, 'ACTION_NUM_48': <ActionType.ACTION_NUM_48: 70>, 'ACTION_NUM_49': <ActionType.ACTION_NUM_49: 71>, 'ACTION_NUM_50': <ActionType.ACTION_NUM_50: 72>, 'ACTION_NUM_51': <ActionType.ACTION_NUM_51: 73>, 'ACTION_NUM_52': <ActionType.ACTION_NUM_52: 74>, 'ACTION_NUM_53': <ActionType.ACTION_NUM_53: 75>, 'ACTION_NUM_54': <ActionType.ACTION_NUM_54: 76>, 'ACTION_NUM_55': <ActionType.ACTION_NUM_55: 77>, 'ACTION_NUM_56': <ActionType.ACTION_NUM_56: 78>, 'ACTION_NUM_57': <ActionType.ACTION_NUM_57: 79>, 'ACTION_NUM_58': <ActionType.ACTION_NUM_58: 80>, 'ACTION_NUM_59': <ActionType.ACTION_NUM_59: 81>, 'ACTION_NUM_60': <ActionType.ACTION_NUM_60: 82>, 'ACTION_NUM_61': <ActionType.ACTION_NUM_61: 83>, 'ACTION_NUM_62': <ActionType.ACTION_NUM_62: 84>, 'ACTION_NUM_63': <ActionType.ACTION_NUM_63: 85>, 'ACTION_NUM_64': <ActionType.ACTION_NUM_64: 86>, 'ACTION_NUM_65': <ActionType.ACTION_NUM_65: 87>, 'ACTION_NUM_66': <ActionType.ACTION_NUM_66: 88>, 'ACTION_NUM_67': <ActionType.ACTION_NUM_67: 89>, 'ACTION_NUM_68': <ActionType.ACTION_NUM_68: 90>, 'ACTION_NUM_69': <ActionType.ACTION_NUM_69: 91>, 'ACTION_NUM_70': <ActionType.ACTION_NUM_70: 92>, 'ACTION_NUM_71': <ActionType.ACTION_NUM_71: 93>, 'ACTION_NUM_72': <ActionType.ACTION_NUM_72: 94>, 'ACTION_NUM_73': <ActionType.ACTION_NUM_73: 95>, 'ACTION_NUM_74': <ActionType.ACTION_NUM_74: 96>, 'ACTION_NUM_75': <ActionType.ACTION_NUM_75: 97>, 'ACTION_NUM_76': <ActionType.ACTION_NUM_76: 98>, 'ACTION_NUM_77': <ActionType.ACTION_NUM_77: 99>, 'ACTION_NUM_78': <ActionType.ACTION_NUM_78: 100>, 'ACTION_NUM_79': <ActionType.ACTION_NUM_79: 101>, 'ACTION_NUM_80': <ActionType.ACTION_NUM_80: 102>, 'ACTION_NUM_81': <ActionType.ACTION_NUM_81: 103>, 'ACTION_NUM_82': <ActionType.ACTION_NUM_82: 104>, 'ACTION_NUM_83': <ActionType.ACTION_NUM_83: 105>, 'ACTION_NUM_84': <ActionType.ACTION_NUM_84: 106>, 'ACTION_NUM_85': <ActionType.ACTION_NUM_85: 107>, 'ACTION_NUM_86': <ActionType.ACTION_NUM_86: 108>, 'ACTION_NUM_87': <ActionType.ACTION_NUM_87: 109>, 'ACTION_NUM_88': <ActionType.ACTION_NUM_88: 110>, 'ACTION_NUM_89': <ActionType.ACTION_NUM_89: 111>, 'ACTION_NUM_90': <ActionType.ACTION_NUM_90: 112>, 'ACTION_NUM_91': <ActionType.ACTION_NUM_91: 113>, 'ACTION_NUM_92': <ActionType.ACTION_NUM_92: 114>, 'ACTION_NUM_93': <ActionType.ACTION_NUM_93: 115>, 'ACTION_NUM_94': <ActionType.ACTION_NUM_94: 116>, 'ACTION_NUM_95': <ActionType.ACTION_NUM_95: 117>, 'ACTION_NUM_96': <ActionType.ACTION_NUM_96: 118>, 'ACTION_NUM_97': <ActionType.ACTION_NUM_97: 119>, 'ACTION_NUM_98': <ActionType.ACTION_NUM_98: 120>, 'ACTION_NUM_99': <ActionType.ACTION_NUM_99: 121>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class CurseType:
    """
    Members:
    
      CURSE_FOG
    
      CURSE_FLASH
    
      CURSE_DARK_CLOUD
    
      CURSE_DREAM
    """
    CURSE_DARK_CLOUD: typing.ClassVar[CurseType]  # value = <CurseType.CURSE_DARK_CLOUD: 2>
    CURSE_DREAM: typing.ClassVar[CurseType]  # value = <CurseType.CURSE_DREAM: 3>
    CURSE_FLASH: typing.ClassVar[CurseType]  # value = <CurseType.CURSE_FLASH: 1>
    CURSE_FOG: typing.ClassVar[CurseType]  # value = <CurseType.CURSE_FOG: 0>
    __members__: typing.ClassVar[dict[str, CurseType]]  # value = {'CURSE_FOG': <CurseType.CURSE_FOG: 0>, 'CURSE_FLASH': <CurseType.CURSE_FLASH: 1>, 'CURSE_DARK_CLOUD': <CurseType.CURSE_DARK_CLOUD: 2>, 'CURSE_DREAM': <CurseType.CURSE_DREAM: 3>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class Element:
    """
    Members:
    
      ELEM_NONE
    
      ELEM_FIRE
    
      ELEM_WATER
    
      ELEM_WOOD
    
      ELEM_STONE
    
      ELEM_LIGHT
    
      ELEM_DARKNESS
    """
    ELEM_DARKNESS: typing.ClassVar[Element]  # value = <Element.ELEM_DARKNESS: 6>
    ELEM_FIRE: typing.ClassVar[Element]  # value = <Element.ELEM_FIRE: 1>
    ELEM_LIGHT: typing.ClassVar[Element]  # value = <Element.ELEM_LIGHT: 5>
    ELEM_NONE: typing.ClassVar[Element]  # value = <Element.ELEM_NONE: 0>
    ELEM_STONE: typing.ClassVar[Element]  # value = <Element.ELEM_STONE: 4>
    ELEM_WATER: typing.ClassVar[Element]  # value = <Element.ELEM_WATER: 2>
    ELEM_WOOD: typing.ClassVar[Element]  # value = <Element.ELEM_WOOD: 3>
    __members__: typing.ClassVar[dict[str, Element]]  # value = {'ELEM_NONE': <Element.ELEM_NONE: 0>, 'ELEM_FIRE': <Element.ELEM_FIRE: 1>, 'ELEM_WATER': <Element.ELEM_WATER: 2>, 'ELEM_WOOD': <Element.ELEM_WOOD: 3>, 'ELEM_STONE': <Element.ELEM_STONE: 4>, 'ELEM_LIGHT': <Element.ELEM_LIGHT: 5>, 'ELEM_DARKNESS': <Element.ELEM_DARKNESS: 6>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class EnvPool:
    def __init__(self, num_envs: typing.SupportsInt | typing.SupportsIndex = 10000) -> None:
        ...
    def get_current_actors(self) -> numpy.typing.NDArray[numpy.int32]:
        ...
    def get_dones(self) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def get_observations(self) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def get_rewards(self) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def get_rewards_for(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def get_state(self, env_id: typing.SupportsInt | typing.SupportsIndex) -> InternalState:
        ...
    def get_terminal_observations_for(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def reset(self, seed: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_state(self, env_id: typing.SupportsInt | typing.SupportsIndex, state: InternalState) -> None:
        ...
    def step_all(self, actions: typing.Annotated[numpy.typing.ArrayLike, numpy.int32]) -> None:
        ...
    def step_subset(self, env_ids: typing.Annotated[numpy.typing.ArrayLike, numpy.int32], actions: typing.Annotated[numpy.typing.ArrayLike, numpy.int32]) -> None:
        ...
class EventType:
    """
    Members:
    
      NONE
    
      STAGE_CARD
    
      UNSTAGE_CARD
    
      CONFIRM_ATTACK
    
      CONFIRM_DEFENSE
    
      PASS_DEFENSE
    
      ATTACK_HIT
    
      ATTACK_MISS
    
      EFFECT_SICKNESS
    
      EFFECT_GUARDIAN
    
      REFLECT_DAMAGE
    
      TAKE_DAMAGE
    
      HEAL_HP
    
      HEAL_MP
    
      BUY_CARD
    
      SELL_CARD
    
      EXCHANGE
    
      DRAW_CARD
    
      DISCARD_CARD
    
      REFUSE_DEAL
    
      BLOCK_ATTACK
    
      BOUNCE_ATTACK
    
      TRIGGER_PHENOMENON
    
      REFLECT_MIRROR
    
      RING_EFFECT
    
      GUARDIAN_ENTER
    
      GUARDIAN_LEAVE
    
      EFFECT_CURSE
    """
    ATTACK_HIT: typing.ClassVar[EventType]  # value = <EventType.ATTACK_HIT: 6>
    ATTACK_MISS: typing.ClassVar[EventType]  # value = <EventType.ATTACK_MISS: 7>
    BLOCK_ATTACK: typing.ClassVar[EventType]  # value = <EventType.BLOCK_ATTACK: 20>
    BOUNCE_ATTACK: typing.ClassVar[EventType]  # value = <EventType.BOUNCE_ATTACK: 21>
    BUY_CARD: typing.ClassVar[EventType]  # value = <EventType.BUY_CARD: 14>
    CONFIRM_ATTACK: typing.ClassVar[EventType]  # value = <EventType.CONFIRM_ATTACK: 3>
    CONFIRM_DEFENSE: typing.ClassVar[EventType]  # value = <EventType.CONFIRM_DEFENSE: 4>
    DISCARD_CARD: typing.ClassVar[EventType]  # value = <EventType.DISCARD_CARD: 18>
    DRAW_CARD: typing.ClassVar[EventType]  # value = <EventType.DRAW_CARD: 17>
    EFFECT_CURSE: typing.ClassVar[EventType]  # value = <EventType.EFFECT_CURSE: 27>
    EFFECT_GUARDIAN: typing.ClassVar[EventType]  # value = <EventType.EFFECT_GUARDIAN: 9>
    EFFECT_SICKNESS: typing.ClassVar[EventType]  # value = <EventType.EFFECT_SICKNESS: 8>
    EXCHANGE: typing.ClassVar[EventType]  # value = <EventType.EXCHANGE: 16>
    GUARDIAN_ENTER: typing.ClassVar[EventType]  # value = <EventType.GUARDIAN_ENTER: 25>
    GUARDIAN_LEAVE: typing.ClassVar[EventType]  # value = <EventType.GUARDIAN_LEAVE: 26>
    HEAL_HP: typing.ClassVar[EventType]  # value = <EventType.HEAL_HP: 12>
    HEAL_MP: typing.ClassVar[EventType]  # value = <EventType.HEAL_MP: 13>
    NONE: typing.ClassVar[EventType]  # value = <EventType.NONE: 0>
    PASS_DEFENSE: typing.ClassVar[EventType]  # value = <EventType.PASS_DEFENSE: 5>
    REFLECT_DAMAGE: typing.ClassVar[EventType]  # value = <EventType.REFLECT_DAMAGE: 10>
    REFLECT_MIRROR: typing.ClassVar[EventType]  # value = <EventType.REFLECT_MIRROR: 23>
    REFUSE_DEAL: typing.ClassVar[EventType]  # value = <EventType.REFUSE_DEAL: 19>
    RING_EFFECT: typing.ClassVar[EventType]  # value = <EventType.RING_EFFECT: 24>
    SELL_CARD: typing.ClassVar[EventType]  # value = <EventType.SELL_CARD: 15>
    STAGE_CARD: typing.ClassVar[EventType]  # value = <EventType.STAGE_CARD: 1>
    TAKE_DAMAGE: typing.ClassVar[EventType]  # value = <EventType.TAKE_DAMAGE: 11>
    TRIGGER_PHENOMENON: typing.ClassVar[EventType]  # value = <EventType.TRIGGER_PHENOMENON: 22>
    UNSTAGE_CARD: typing.ClassVar[EventType]  # value = <EventType.UNSTAGE_CARD: 2>
    __members__: typing.ClassVar[dict[str, EventType]]  # value = {'NONE': <EventType.NONE: 0>, 'STAGE_CARD': <EventType.STAGE_CARD: 1>, 'UNSTAGE_CARD': <EventType.UNSTAGE_CARD: 2>, 'CONFIRM_ATTACK': <EventType.CONFIRM_ATTACK: 3>, 'CONFIRM_DEFENSE': <EventType.CONFIRM_DEFENSE: 4>, 'PASS_DEFENSE': <EventType.PASS_DEFENSE: 5>, 'ATTACK_HIT': <EventType.ATTACK_HIT: 6>, 'ATTACK_MISS': <EventType.ATTACK_MISS: 7>, 'EFFECT_SICKNESS': <EventType.EFFECT_SICKNESS: 8>, 'EFFECT_GUARDIAN': <EventType.EFFECT_GUARDIAN: 9>, 'REFLECT_DAMAGE': <EventType.REFLECT_DAMAGE: 10>, 'TAKE_DAMAGE': <EventType.TAKE_DAMAGE: 11>, 'HEAL_HP': <EventType.HEAL_HP: 12>, 'HEAL_MP': <EventType.HEAL_MP: 13>, 'BUY_CARD': <EventType.BUY_CARD: 14>, 'SELL_CARD': <EventType.SELL_CARD: 15>, 'EXCHANGE': <EventType.EXCHANGE: 16>, 'DRAW_CARD': <EventType.DRAW_CARD: 17>, 'DISCARD_CARD': <EventType.DISCARD_CARD: 18>, 'REFUSE_DEAL': <EventType.REFUSE_DEAL: 19>, 'BLOCK_ATTACK': <EventType.BLOCK_ATTACK: 20>, 'BOUNCE_ATTACK': <EventType.BOUNCE_ATTACK: 21>, 'TRIGGER_PHENOMENON': <EventType.TRIGGER_PHENOMENON: 22>, 'REFLECT_MIRROR': <EventType.REFLECT_MIRROR: 23>, 'RING_EFFECT': <EventType.RING_EFFECT: 24>, 'GUARDIAN_ENTER': <EventType.GUARDIAN_ENTER: 25>, 'GUARDIAN_LEAVE': <EventType.GUARDIAN_LEAVE: 26>, 'EFFECT_CURSE': <EventType.EFFECT_CURSE: 27>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class GameEvent:
    def __init__(self) -> None:
        ...
    @property
    def actor(self) -> float:
        ...
    @actor.setter
    def actor(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def card_id(self) -> float:
        ...
    @card_id.setter
    def card_id(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def event_type(self) -> float:
        ...
    @event_type.setter
    def event_type(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def target_id(self) -> float:
        ...
    @target_id.setter
    def target_id(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def value(self) -> float:
        ...
    @value.setter
    def value(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
class GamePhase:
    """
    Members:
    
      PHASE_GUARDIAN
    
      PHASE_MAIN
    
      PHASE_MAIN_TARGET_SELECT
    
      PHASE_ATTACK_PLUS
    
      PHASE_GROUP_WEAPON
    
      PHASE_MIRACLE_PLUS
    
      PHASE_GROUP_MIRACLE_PLUS
    
      PHASE_DEFENSE
    
      PHASE_MIRACLE_DEFENSE
    
      PHASE_SELL_SELECT
    
      PHASE_SELL_SELECT_MIRROR
    
      PHASE_BUY_SELECT_MIRROR
    
      PHASE_SUNDRY_SELECT_MIRROR
    
      PHASE_BUY
    
      PHASE_EXCHANGE_HP
    
      PHASE_EXCHANGE_MP
    
      PHASE_DISCARD
    
      PHASE_END
    """
    PHASE_ATTACK_PLUS: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_ATTACK_PLUS: 3>
    PHASE_BUY: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_BUY: 11>
    PHASE_BUY_SELECT_MIRROR: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_BUY_SELECT_MIRROR: 12>
    PHASE_DEFENSE: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_DEFENSE: 7>
    PHASE_DISCARD: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_DISCARD: 16>
    PHASE_END: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_END: 17>
    PHASE_EXCHANGE_HP: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_EXCHANGE_HP: 14>
    PHASE_EXCHANGE_MP: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_EXCHANGE_MP: 15>
    PHASE_GROUP_MIRACLE_PLUS: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GROUP_MIRACLE_PLUS: 6>
    PHASE_GROUP_WEAPON: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GROUP_WEAPON: 4>
    PHASE_GUARDIAN: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GUARDIAN: 0>
    PHASE_MAIN: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MAIN: 1>
    PHASE_MAIN_TARGET_SELECT: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>
    PHASE_MIRACLE_DEFENSE: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MIRACLE_DEFENSE: 8>
    PHASE_MIRACLE_PLUS: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MIRACLE_PLUS: 5>
    PHASE_SELL_SELECT: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SELL_SELECT: 9>
    PHASE_SELL_SELECT_MIRROR: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>
    PHASE_SUNDRY_SELECT_MIRROR: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>
    __members__: typing.ClassVar[dict[str, GamePhase]]  # value = {'PHASE_GUARDIAN': <GamePhase.PHASE_GUARDIAN: 0>, 'PHASE_MAIN': <GamePhase.PHASE_MAIN: 1>, 'PHASE_MAIN_TARGET_SELECT': <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>, 'PHASE_ATTACK_PLUS': <GamePhase.PHASE_ATTACK_PLUS: 3>, 'PHASE_GROUP_WEAPON': <GamePhase.PHASE_GROUP_WEAPON: 4>, 'PHASE_MIRACLE_PLUS': <GamePhase.PHASE_MIRACLE_PLUS: 5>, 'PHASE_GROUP_MIRACLE_PLUS': <GamePhase.PHASE_GROUP_MIRACLE_PLUS: 6>, 'PHASE_DEFENSE': <GamePhase.PHASE_DEFENSE: 7>, 'PHASE_MIRACLE_DEFENSE': <GamePhase.PHASE_MIRACLE_DEFENSE: 8>, 'PHASE_SELL_SELECT': <GamePhase.PHASE_SELL_SELECT: 9>, 'PHASE_SELL_SELECT_MIRROR': <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>, 'PHASE_BUY_SELECT_MIRROR': <GamePhase.PHASE_BUY_SELECT_MIRROR: 12>, 'PHASE_SUNDRY_SELECT_MIRROR': <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>, 'PHASE_BUY': <GamePhase.PHASE_BUY: 11>, 'PHASE_EXCHANGE_HP': <GamePhase.PHASE_EXCHANGE_HP: 14>, 'PHASE_EXCHANGE_MP': <GamePhase.PHASE_EXCHANGE_MP: 15>, 'PHASE_DISCARD': <GamePhase.PHASE_DISCARD: 16>, 'PHASE_END': <GamePhase.PHASE_END: 17>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class GuardianType:
    """
    Members:
    
      NONE
    
      MARS
    
      MERCURY
    
      JUPITER
    
      SATURN
    
      URANUS
    
      PLUTO
    
      NEPTUNE
    
      VENUS
    
      EARTH
    
      MOON
    """
    EARTH: typing.ClassVar[GuardianType]  # value = <GuardianType.EARTH: 9>
    JUPITER: typing.ClassVar[GuardianType]  # value = <GuardianType.JUPITER: 3>
    MARS: typing.ClassVar[GuardianType]  # value = <GuardianType.MARS: 1>
    MERCURY: typing.ClassVar[GuardianType]  # value = <GuardianType.MERCURY: 2>
    MOON: typing.ClassVar[GuardianType]  # value = <GuardianType.MOON: 10>
    NEPTUNE: typing.ClassVar[GuardianType]  # value = <GuardianType.NEPTUNE: 7>
    NONE: typing.ClassVar[GuardianType]  # value = <GuardianType.NONE: 0>
    PLUTO: typing.ClassVar[GuardianType]  # value = <GuardianType.PLUTO: 6>
    SATURN: typing.ClassVar[GuardianType]  # value = <GuardianType.SATURN: 4>
    URANUS: typing.ClassVar[GuardianType]  # value = <GuardianType.URANUS: 5>
    VENUS: typing.ClassVar[GuardianType]  # value = <GuardianType.VENUS: 8>
    __members__: typing.ClassVar[dict[str, GuardianType]]  # value = {'NONE': <GuardianType.NONE: 0>, 'MARS': <GuardianType.MARS: 1>, 'MERCURY': <GuardianType.MERCURY: 2>, 'JUPITER': <GuardianType.JUPITER: 3>, 'SATURN': <GuardianType.SATURN: 4>, 'URANUS': <GuardianType.URANUS: 5>, 'PLUTO': <GuardianType.PLUTO: 6>, 'NEPTUNE': <GuardianType.NEPTUNE: 7>, 'VENUS': <GuardianType.VENUS: 8>, 'EARTH': <GuardianType.EARTH: 9>, 'MOON': <GuardianType.MOON: 10>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class HitCurse:
    """
    Members:
    
      CURSE_NONE
    
      CURSE_FOG
    
      CURSE_FLASH
    
      CURSE_DARK_CLOUD
    
      CURSE_DREAM
    
      CURSE_COLD
    
      CURSE_FEVER
    
      CURSE_HELL
    
      CURSE_HEAVEN
    """
    CURSE_COLD: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_COLD: 5>
    CURSE_DARK_CLOUD: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_DARK_CLOUD: 3>
    CURSE_DREAM: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_DREAM: 4>
    CURSE_FEVER: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_FEVER: 6>
    CURSE_FLASH: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_FLASH: 2>
    CURSE_FOG: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_FOG: 1>
    CURSE_HEAVEN: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_HEAVEN: 8>
    CURSE_HELL: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_HELL: 7>
    CURSE_NONE: typing.ClassVar[HitCurse]  # value = <HitCurse.CURSE_NONE: 0>
    __members__: typing.ClassVar[dict[str, HitCurse]]  # value = {'CURSE_NONE': <HitCurse.CURSE_NONE: 0>, 'CURSE_FOG': <HitCurse.CURSE_FOG: 1>, 'CURSE_FLASH': <HitCurse.CURSE_FLASH: 2>, 'CURSE_DARK_CLOUD': <HitCurse.CURSE_DARK_CLOUD: 3>, 'CURSE_DREAM': <HitCurse.CURSE_DREAM: 4>, 'CURSE_COLD': <HitCurse.CURSE_COLD: 5>, 'CURSE_FEVER': <HitCurse.CURSE_FEVER: 6>, 'CURSE_HELL': <HitCurse.CURSE_HELL: 7>, 'CURSE_HEAVEN': <HitCurse.CURSE_HEAVEN: 8>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class InternalState:
    base_absorption: bool
    base_attack_element: Element
    base_deal_same_damage: bool
    current_phase: GamePhase
    is_done: bool
    pending_absorption: bool
    pending_attack_element: Element
    pending_deal_same_damage: bool
    pending_is_group_attack: bool
    turn_end_state: TurnEndSubstep
    def __init__(self) -> None:
        ...
    def add_card_to_hand_slot(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, card_id: typing.SupportsInt | typing.SupportsIndex, is_drawn: bool) -> None:
        ...
    def get_apparent_hand(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_curses(self, player_id: typing.SupportsInt | typing.SupportsIndex, curse_idx: CurseType) -> bool:
        ...
    def get_guardian(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_hp(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_is_confirmed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_is_deployed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_is_known_to_opp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_is_used(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_money(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_mp(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_num_staged_cards(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_pending_ascension_bows(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_sickness(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> SicknessType:
        ...
    def get_staged_card(self, player_id: typing.SupportsInt | typing.SupportsIndex, staged_idx: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_true_hand(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def seed_rng(self, seed: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_apparent_hand(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, card_id: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_curses(self, player_id: typing.SupportsInt | typing.SupportsIndex, curse_idx: CurseType, val: bool) -> None:
        ...
    def set_guardian(self, player_id: typing.SupportsInt | typing.SupportsIndex, val: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_hp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hp: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_is_confirmed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, is_confirmed: bool) -> None:
        ...
    def set_is_deployed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, val: bool) -> None:
        ...
    def set_is_known_to_opp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, is_known: bool) -> None:
        ...
    def set_is_used(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, is_used: bool) -> None:
        ...
    def set_money(self, player_id: typing.SupportsInt | typing.SupportsIndex, money: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_mp(self, player_id: typing.SupportsInt | typing.SupportsIndex, mp: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_num_staged_cards(self, player_id: typing.SupportsInt | typing.SupportsIndex, num: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_pending_ascension_bows(self, player_id: typing.SupportsInt | typing.SupportsIndex, val: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_sickness(self, player_id: typing.SupportsInt | typing.SupportsIndex, val: SicknessType) -> None:
        ...
    def set_staged_card(self, player_id: typing.SupportsInt | typing.SupportsIndex, staged_idx: typing.SupportsInt | typing.SupportsIndex, val: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_true_hand(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, card_id: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def attacker_id(self) -> int:
        ...
    @attacker_id.setter
    def attacker_id(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def base_attack_power(self) -> int:
        ...
    @base_attack_power.setter
    def base_attack_power(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def current_actor_id(self) -> int:
        ...
    @current_actor_id.setter
    def current_actor_id(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def current_turn(self) -> int:
        ...
    @current_turn.setter
    def current_turn(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def defender_id(self) -> int:
        ...
    @defender_id.setter
    def defender_id(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def history_count(self) -> int:
        ...
    @history_count.setter
    def history_count(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def mushroom_turns(self) -> int:
        ...
    @mushroom_turns.setter
    def mushroom_turns(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def p0_reward(self) -> float:
        ...
    @p0_reward.setter
    def p0_reward(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def p1_reward(self) -> float:
        ...
    @p1_reward.setter
    def p1_reward(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def pending_attack_power(self) -> int:
        ...
    @pending_attack_power.setter
    def pending_attack_power(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def pending_attack_source_id(self) -> int:
        ...
    @pending_attack_source_id.setter
    def pending_attack_source_id(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def pending_defense_power(self) -> int:
        ...
    @pending_defense_power.setter
    def pending_defense_power(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def remaining_attacks(self) -> int:
        ...
    @remaining_attacks.setter
    def remaining_attacks(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
class Observation:
    def __copy__(self) -> Observation:
        ...
    def __deepcopy__(self, arg0: dict) -> Observation:
        ...
    def __init__(self) -> None:
        ...
    def get_action_mask(self) -> list:
        ...
    def get_curses_me(self) -> list:
        ...
    def get_curses_opp(self) -> list:
        ...
    def get_guardian_me(self) -> list:
        ...
    def get_guardian_opp(self) -> list:
        ...
    def get_hand_cards(self) -> list:
        ...
    def get_history(self) -> list:
        ...
    def get_opponent_hand_cards(self) -> list:
        ...
    def get_opponent_staged_cards(self) -> list:
        ...
    def get_phase_one_hot(self) -> list:
        ...
    def get_sickness_me(self) -> list:
        ...
    def get_sickness_opp(self) -> list:
        ...
    def get_staged_cards(self) -> list:
        ...
    def to_numpy(self) -> numpy.typing.NDArray[numpy.float32]:
        ...
    @property
    def current_staged_defense(self) -> float:
        ...
    @current_staged_defense.setter
    def current_staged_defense(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def history_head(self) -> float:
        ...
    @history_head.setter
    def history_head(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def hp_me(self) -> float:
        ...
    @hp_me.setter
    def hp_me(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def hp_opp(self) -> float:
        ...
    @hp_opp.setter
    def hp_opp(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def incoming_damage(self) -> float:
        ...
    @incoming_damage.setter
    def incoming_damage(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def is_apocalypse(self) -> float:
        ...
    @is_apocalypse.setter
    def is_apocalypse(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def money_me(self) -> float:
        ...
    @money_me.setter
    def money_me(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def money_opp(self) -> float:
        ...
    @money_opp.setter
    def money_opp(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def mp_me(self) -> float:
        ...
    @mp_me.setter
    def mp_me(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def mp_opp(self) -> float:
        ...
    @mp_opp.setter
    def mp_opp(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def turn_progress(self) -> float:
        ...
    @turn_progress.setter
    def turn_progress(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
    @property
    def turns_to_apocalypse(self) -> float:
        ...
    @turns_to_apocalypse.setter
    def turns_to_apocalypse(self, arg0: typing.SupportsFloat | typing.SupportsIndex) -> None:
        ...
class PhenomenonType:
    """
    Members:
    
      SUNSET
    
      DENSE_FOG
    
      MUSHROOM
    
      TORNADO
    
      GIGANTIC_TUB
    
      BLACK_HOLE
    
      WARM_CURRENT
    
      GOLD_MINE
    
      MAGNETIC_STORM
    
      ECLIPSE
    """
    BLACK_HOLE: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.BLACK_HOLE: 5>
    DENSE_FOG: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.DENSE_FOG: 1>
    ECLIPSE: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.ECLIPSE: 9>
    GIGANTIC_TUB: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.GIGANTIC_TUB: 4>
    GOLD_MINE: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.GOLD_MINE: 7>
    MAGNETIC_STORM: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.MAGNETIC_STORM: 8>
    MUSHROOM: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.MUSHROOM: 2>
    SUNSET: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.SUNSET: 0>
    TORNADO: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.TORNADO: 3>
    WARM_CURRENT: typing.ClassVar[PhenomenonType]  # value = <PhenomenonType.WARM_CURRENT: 6>
    __members__: typing.ClassVar[dict[str, PhenomenonType]]  # value = {'SUNSET': <PhenomenonType.SUNSET: 0>, 'DENSE_FOG': <PhenomenonType.DENSE_FOG: 1>, 'MUSHROOM': <PhenomenonType.MUSHROOM: 2>, 'TORNADO': <PhenomenonType.TORNADO: 3>, 'GIGANTIC_TUB': <PhenomenonType.GIGANTIC_TUB: 4>, 'BLACK_HOLE': <PhenomenonType.BLACK_HOLE: 5>, 'WARM_CURRENT': <PhenomenonType.WARM_CURRENT: 6>, 'GOLD_MINE': <PhenomenonType.GOLD_MINE: 7>, 'MAGNETIC_STORM': <PhenomenonType.MAGNETIC_STORM: 8>, 'ECLIPSE': <PhenomenonType.ECLIPSE: 9>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class ReactionType:
    """
    Members:
    
      REACTION_NONE
    
      REACTION_BOUNCE
    
      REACTION_REFLECT
    
      REACTION_BLOCK
    """
    REACTION_BLOCK: typing.ClassVar[ReactionType]  # value = <ReactionType.REACTION_BLOCK: 3>
    REACTION_BOUNCE: typing.ClassVar[ReactionType]  # value = <ReactionType.REACTION_BOUNCE: 1>
    REACTION_NONE: typing.ClassVar[ReactionType]  # value = <ReactionType.REACTION_NONE: 0>
    REACTION_REFLECT: typing.ClassVar[ReactionType]  # value = <ReactionType.REACTION_REFLECT: 2>
    __members__: typing.ClassVar[dict[str, ReactionType]]  # value = {'REACTION_NONE': <ReactionType.REACTION_NONE: 0>, 'REACTION_BOUNCE': <ReactionType.REACTION_BOUNCE: 1>, 'REACTION_REFLECT': <ReactionType.REACTION_REFLECT: 2>, 'REACTION_BLOCK': <ReactionType.REACTION_BLOCK: 3>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class RollKind:
    """
    乱数消費点のラベル。どの確率判定を指示するかを表す。
    
    Members:
    
      ACCURACY
    
      BOUNCE
    
      MARS_RING
    
      GUARDIAN_LEAVE
    
      ASCENSION_BOW_HIT
    
      SICKNESS_WORSEN
    
      GUARDIAN_ACT
    
      GUARDIAN_ACT_CHOICE
    
      MOON_MIRACLE
    
      PHENOMENON
    
      PHENOMENON_TUB_TARGET
    
      PHENOMENON_GOLD_MINE
    
      PHENOMENON_ECLIPSE_G0
    
      PHENOMENON_ECLIPSE_G1
    
      PHENOMENON_MAGNETIC_STORM
    
      GUARDIAN_POT
    
      THUMP_THUMP_TEAR
    
      DEVIL_FAIRY
    
      DEVIL_PRANKSTER
    
      DECK_DRAW
    
      APOCALYPSE_DRAW
    
      DREAM_DISGUISE
    
      DREAM_FAKE_CARD
    
      MUSHROOM_ACTION
    
      MORTAR_VICTIM
    
      PESTLE_TARGET
    
      DISCARD_RANDOM_ORDER
    
      DISCARD_ONE_SLOT
    
      REVEAL_SLOT
    
      HAND_REPLACE_SLOT
    
      EARTH_DISCARD_SLOT
    
      EARTH_EXCHANGE_HP
    
      EARTH_EXCHANGE_MP
    
      EARTH_SELL_SLOT
    """
    ACCURACY: typing.ClassVar[RollKind]  # value = <RollKind.ACCURACY: 0>
    APOCALYPSE_DRAW: typing.ClassVar[RollKind]  # value = <RollKind.APOCALYPSE_DRAW: 20>
    ASCENSION_BOW_HIT: typing.ClassVar[RollKind]  # value = <RollKind.ASCENSION_BOW_HIT: 4>
    BOUNCE: typing.ClassVar[RollKind]  # value = <RollKind.BOUNCE: 1>
    DECK_DRAW: typing.ClassVar[RollKind]  # value = <RollKind.DECK_DRAW: 19>
    DEVIL_FAIRY: typing.ClassVar[RollKind]  # value = <RollKind.DEVIL_FAIRY: 17>
    DEVIL_PRANKSTER: typing.ClassVar[RollKind]  # value = <RollKind.DEVIL_PRANKSTER: 18>
    DISCARD_ONE_SLOT: typing.ClassVar[RollKind]  # value = <RollKind.DISCARD_ONE_SLOT: 27>
    DISCARD_RANDOM_ORDER: typing.ClassVar[RollKind]  # value = <RollKind.DISCARD_RANDOM_ORDER: 26>
    DREAM_DISGUISE: typing.ClassVar[RollKind]  # value = <RollKind.DREAM_DISGUISE: 21>
    DREAM_FAKE_CARD: typing.ClassVar[RollKind]  # value = <RollKind.DREAM_FAKE_CARD: 22>
    EARTH_DISCARD_SLOT: typing.ClassVar[RollKind]  # value = <RollKind.EARTH_DISCARD_SLOT: 30>
    EARTH_EXCHANGE_HP: typing.ClassVar[RollKind]  # value = <RollKind.EARTH_EXCHANGE_HP: 31>
    EARTH_EXCHANGE_MP: typing.ClassVar[RollKind]  # value = <RollKind.EARTH_EXCHANGE_MP: 32>
    EARTH_SELL_SLOT: typing.ClassVar[RollKind]  # value = <RollKind.EARTH_SELL_SLOT: 33>
    GUARDIAN_ACT: typing.ClassVar[RollKind]  # value = <RollKind.GUARDIAN_ACT: 6>
    GUARDIAN_ACT_CHOICE: typing.ClassVar[RollKind]  # value = <RollKind.GUARDIAN_ACT_CHOICE: 7>
    GUARDIAN_LEAVE: typing.ClassVar[RollKind]  # value = <RollKind.GUARDIAN_LEAVE: 3>
    GUARDIAN_POT: typing.ClassVar[RollKind]  # value = <RollKind.GUARDIAN_POT: 15>
    HAND_REPLACE_SLOT: typing.ClassVar[RollKind]  # value = <RollKind.HAND_REPLACE_SLOT: 29>
    MARS_RING: typing.ClassVar[RollKind]  # value = <RollKind.MARS_RING: 2>
    MOON_MIRACLE: typing.ClassVar[RollKind]  # value = <RollKind.MOON_MIRACLE: 8>
    MORTAR_VICTIM: typing.ClassVar[RollKind]  # value = <RollKind.MORTAR_VICTIM: 24>
    MUSHROOM_ACTION: typing.ClassVar[RollKind]  # value = <RollKind.MUSHROOM_ACTION: 23>
    PESTLE_TARGET: typing.ClassVar[RollKind]  # value = <RollKind.PESTLE_TARGET: 25>
    PHENOMENON: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON: 9>
    PHENOMENON_ECLIPSE_G0: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON_ECLIPSE_G0: 12>
    PHENOMENON_ECLIPSE_G1: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON_ECLIPSE_G1: 13>
    PHENOMENON_GOLD_MINE: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON_GOLD_MINE: 11>
    PHENOMENON_MAGNETIC_STORM: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON_MAGNETIC_STORM: 14>
    PHENOMENON_TUB_TARGET: typing.ClassVar[RollKind]  # value = <RollKind.PHENOMENON_TUB_TARGET: 10>
    REVEAL_SLOT: typing.ClassVar[RollKind]  # value = <RollKind.REVEAL_SLOT: 28>
    SICKNESS_WORSEN: typing.ClassVar[RollKind]  # value = <RollKind.SICKNESS_WORSEN: 5>
    THUMP_THUMP_TEAR: typing.ClassVar[RollKind]  # value = <RollKind.THUMP_THUMP_TEAR: 16>
    __members__: typing.ClassVar[dict[str, RollKind]]  # value = {'ACCURACY': <RollKind.ACCURACY: 0>, 'BOUNCE': <RollKind.BOUNCE: 1>, 'MARS_RING': <RollKind.MARS_RING: 2>, 'GUARDIAN_LEAVE': <RollKind.GUARDIAN_LEAVE: 3>, 'ASCENSION_BOW_HIT': <RollKind.ASCENSION_BOW_HIT: 4>, 'SICKNESS_WORSEN': <RollKind.SICKNESS_WORSEN: 5>, 'GUARDIAN_ACT': <RollKind.GUARDIAN_ACT: 6>, 'GUARDIAN_ACT_CHOICE': <RollKind.GUARDIAN_ACT_CHOICE: 7>, 'MOON_MIRACLE': <RollKind.MOON_MIRACLE: 8>, 'PHENOMENON': <RollKind.PHENOMENON: 9>, 'PHENOMENON_TUB_TARGET': <RollKind.PHENOMENON_TUB_TARGET: 10>, 'PHENOMENON_GOLD_MINE': <RollKind.PHENOMENON_GOLD_MINE: 11>, 'PHENOMENON_ECLIPSE_G0': <RollKind.PHENOMENON_ECLIPSE_G0: 12>, 'PHENOMENON_ECLIPSE_G1': <RollKind.PHENOMENON_ECLIPSE_G1: 13>, 'PHENOMENON_MAGNETIC_STORM': <RollKind.PHENOMENON_MAGNETIC_STORM: 14>, 'GUARDIAN_POT': <RollKind.GUARDIAN_POT: 15>, 'THUMP_THUMP_TEAR': <RollKind.THUMP_THUMP_TEAR: 16>, 'DEVIL_FAIRY': <RollKind.DEVIL_FAIRY: 17>, 'DEVIL_PRANKSTER': <RollKind.DEVIL_PRANKSTER: 18>, 'DECK_DRAW': <RollKind.DECK_DRAW: 19>, 'APOCALYPSE_DRAW': <RollKind.APOCALYPSE_DRAW: 20>, 'DREAM_DISGUISE': <RollKind.DREAM_DISGUISE: 21>, 'DREAM_FAKE_CARD': <RollKind.DREAM_FAKE_CARD: 22>, 'MUSHROOM_ACTION': <RollKind.MUSHROOM_ACTION: 23>, 'MORTAR_VICTIM': <RollKind.MORTAR_VICTIM: 24>, 'PESTLE_TARGET': <RollKind.PESTLE_TARGET: 25>, 'DISCARD_RANDOM_ORDER': <RollKind.DISCARD_RANDOM_ORDER: 26>, 'DISCARD_ONE_SLOT': <RollKind.DISCARD_ONE_SLOT: 27>, 'REVEAL_SLOT': <RollKind.REVEAL_SLOT: 28>, 'HAND_REPLACE_SLOT': <RollKind.HAND_REPLACE_SLOT: 29>, 'EARTH_DISCARD_SLOT': <RollKind.EARTH_DISCARD_SLOT: 30>, 'EARTH_EXCHANGE_HP': <RollKind.EARTH_EXCHANGE_HP: 31>, 'EARTH_EXCHANGE_MP': <RollKind.EARTH_EXCHANGE_MP: 32>, 'EARTH_SELL_SLOT': <RollKind.EARTH_SELL_SLOT: 33>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class SicknessType:
    """
    Members:
    
      SICKNESS_NONE
    
      SICKNESS_COLD
    
      SICKNESS_FEVER
    
      SICKNESS_HELL
    
      SICKNESS_HEAVEN
    """
    SICKNESS_COLD: typing.ClassVar[SicknessType]  # value = <SicknessType.SICKNESS_COLD: 1>
    SICKNESS_FEVER: typing.ClassVar[SicknessType]  # value = <SicknessType.SICKNESS_FEVER: 2>
    SICKNESS_HEAVEN: typing.ClassVar[SicknessType]  # value = <SicknessType.SICKNESS_HEAVEN: 4>
    SICKNESS_HELL: typing.ClassVar[SicknessType]  # value = <SicknessType.SICKNESS_HELL: 3>
    SICKNESS_NONE: typing.ClassVar[SicknessType]  # value = <SicknessType.SICKNESS_NONE: 0>
    __members__: typing.ClassVar[dict[str, SicknessType]]  # value = {'SICKNESS_NONE': <SicknessType.SICKNESS_NONE: 0>, 'SICKNESS_COLD': <SicknessType.SICKNESS_COLD: 1>, 'SICKNESS_FEVER': <SicknessType.SICKNESS_FEVER: 2>, 'SICKNESS_HELL': <SicknessType.SICKNESS_HELL: 3>, 'SICKNESS_HEAVEN': <SicknessType.SICKNESS_HEAVEN: 4>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
class TurnEndSubstep:
    """
    Members:
    
      DEATH_CHECK_START
    
      SICKNESS_WORSEN
    
      SICKNESS_DAMAGE
    
      FINAL_DEATH_CHECK
    
      GUARDIAN_ACT
    
      CLEANUP_DEATH_CHECK
    
      CLEANUP
    
      TURN_TRANSITION
    """
    CLEANUP: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.CLEANUP: 6>
    CLEANUP_DEATH_CHECK: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.CLEANUP_DEATH_CHECK: 5>
    DEATH_CHECK_START: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.DEATH_CHECK_START: 0>
    FINAL_DEATH_CHECK: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.FINAL_DEATH_CHECK: 3>
    GUARDIAN_ACT: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.GUARDIAN_ACT: 4>
    SICKNESS_DAMAGE: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.SICKNESS_DAMAGE: 2>
    SICKNESS_WORSEN: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.SICKNESS_WORSEN: 1>
    TURN_TRANSITION: typing.ClassVar[TurnEndSubstep]  # value = <TurnEndSubstep.TURN_TRANSITION: 7>
    __members__: typing.ClassVar[dict[str, TurnEndSubstep]]  # value = {'DEATH_CHECK_START': <TurnEndSubstep.DEATH_CHECK_START: 0>, 'SICKNESS_WORSEN': <TurnEndSubstep.SICKNESS_WORSEN: 1>, 'SICKNESS_DAMAGE': <TurnEndSubstep.SICKNESS_DAMAGE: 2>, 'FINAL_DEATH_CHECK': <TurnEndSubstep.FINAL_DEATH_CHECK: 3>, 'GUARDIAN_ACT': <TurnEndSubstep.GUARDIAN_ACT: 4>, 'CLEANUP_DEATH_CHECK': <TurnEndSubstep.CLEANUP_DEATH_CHECK: 5>, 'CLEANUP': <TurnEndSubstep.CLEANUP: 6>, 'TURN_TRANSITION': <TurnEndSubstep.TURN_TRANSITION: 7>}
    def __eq__(self, other: typing.Any) -> bool:
        ...
    def __getstate__(self) -> int:
        ...
    def __hash__(self) -> int:
        ...
    def __index__(self) -> int:
        ...
    def __init__(self, value: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __int__(self) -> int:
        ...
    def __ne__(self, other: typing.Any) -> bool:
        ...
    def __repr__(self) -> str:
        ...
    def __setstate__(self, state: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def __str__(self) -> str:
        ...
    @property
    def name(self) -> str:
        ...
    @property
    def value(self) -> int:
        ...
def clear_state(arg0: InternalState) -> None:
    """
    Zero out the state memory preserving RNG
    """
def draw_card(state: InternalState) -> int:
    """
    山札から1枚抽選してカードIDを返します。抽選分布そのものを検証するために公開しています（テストが next_draws() で指示している場合はその値が返ります）。
    """
def get_absorption_sources() -> list[int]:
    """
    HP吸収（与えたダメージ分だけ攻撃側が回復する）を持つカードID一覧。テストが全種を網羅するために公開しています。
    """
def get_apocalypse_devils() -> list[int]:
    """
    終末の時のドローで出る悪魔カードID一覧。APOCALYPSE_DEVIL_THRESHOLDS の各区間に対応する。テストは悪魔名からこの並びのインデックスを逆引きしてRollKind::APOCALYPSE_DRAW に指示します。
    """
def get_card_name(arg0: typing.SupportsInt | typing.SupportsIndex) -> str:
    """
    Get card name by ID
    """
def get_draw_table_size() -> int:
    """
    抽選テーブルの要素数（drop_rate の重みの総和）。
    """
def get_dream_candidates(card_id: typing.SupportsInt | typing.SupportsIndex) -> list[int]:
    """
    夢状態でそのカードが偽装されうる相手のカードID一覧（自分自身は含まない）。テストは偽装先のカード名からこの並びのインデックスを逆引きして RollKind::DREAM_FAKE_CARD に指示します。
    """
def get_guardian_action_cards(guardian: typing.SupportsInt | typing.SupportsIndex) -> list[int]:
    """
    指定した守護神の5行動に対応するカードID一覧（攻撃系6神と海王神のみ。他は空）。テストは行動カード名からこの並びのインデックスを逆引きして RollKind::GUARDIAN_ACT_CHOICE に指示します。
    """
def get_legal_actions(arg0: InternalState) -> list:
    """
    Get a boolean list of legal actions
    """
def get_moon_miracles() -> list[int]:
    """
    月神が発動しうる奇跡のカードID一覧。テストは奇跡名からこの並びのインデックスを逆引きして RollKind::MOON_MIRACLE に指示します。
    """
def get_observation(arg0: InternalState, arg1: typing.SupportsInt | typing.SupportsIndex) -> Observation:
    """
    Get Observation from InternalState for player_id
    """
def get_opponent_staged_cards_for_obs(arg0: InternalState, arg1: typing.SupportsInt | typing.SupportsIndex) -> list:
    """
    Get opponent staged cards for observation integration validation
    """
def get_registry_size() -> int:
    """
    Get number of cards in registry
    """
def get_single_legal_action(arg0: InternalState) -> int:
    """
    Get single legal action ID if only one is available, else -1
    """
def init_game_logic(arg0: list) -> None:
    """
    Initialize the global card registry from JSON
    """
def rng_clear_script() -> None:
    """
    仕込んだ指示をすべて破棄し、本番と同じ挙動に戻します（各テストの終わりに必ず呼ぶ）。
    """
def rng_consumed(kind: RollKind) -> int:
    """
    その判定が実際に何回行われたかを返します。
    """
def rng_forbid_unscripted(forbid: bool = True) -> None:
    """
    指示のない乱数消費が起きた時点で例外にします。そのテストが運に一切依存しないことを機械的に証明できます。
    """
def rng_force(kind: RollKind, value: typing.SupportsInt | typing.SupportsIndex, optional: bool = False) -> None:
    """
    以後その判定が常に value を返すようにします（回数は問わない）。optional=True にすると未消費検査の対象外になります（手札補充のように、起きるかどうかがテストの主題でない背景固定に使う）。
    """
def rng_pick_order(kind: RollKind, preferred: collections.abc.Sequence[typing.SupportsInt | typing.SupportsIndex]) -> None:
    """
    シャッフル系の判定で、指定した値（手札スロット番号など）を先頭から順に並べます。残りは候補の元の順序を保つため、指示済みテストは完全に決定的になります。
    """
def rng_script(kind: RollKind, values: collections.abc.Sequence[typing.SupportsInt | typing.SupportsIndex], repeat_last: bool = False) -> None:
    """
    その判定がちょうどこの順で values 回だけ行われることを指示します。回数を超えて判定されると例外になります。repeat_last=True にすると、使い切った後は最後の値を繰り返します（先頭数回だけ意味を持たせ、残りは無害な値で埋めたい場合に使う）。
    """
def rng_unconsumed_kinds() -> list:
    """
    指示したのに使われなかった判定の名前一覧を返します。空でなければ、テストが意図したコードパスが実行されていません。
    """
def step_game(arg0: InternalState, arg1: ActionType) -> None:
    """
    Step a single InternalState
    """
ACTION_CONFIRM: ActionType  # value = <ActionType.ACTION_TARGET_SELF: 19>
ACTION_DEAL_NO: ActionType  # value = <ActionType.ACTION_TARGET_SELF: 19>
ACTION_DEAL_YES: ActionType  # value = <ActionType.ACTION_TARGET_OPP: 18>
ACTION_DISCARD: ActionType  # value = <ActionType.ACTION_DISCARD: 21>
ACTION_NUM_0: ActionType  # value = <ActionType.ACTION_NUM_0: 22>
ACTION_NUM_1: ActionType  # value = <ActionType.ACTION_NUM_1: 23>
ACTION_NUM_10: ActionType  # value = <ActionType.ACTION_NUM_10: 32>
ACTION_NUM_11: ActionType  # value = <ActionType.ACTION_NUM_11: 33>
ACTION_NUM_12: ActionType  # value = <ActionType.ACTION_NUM_12: 34>
ACTION_NUM_13: ActionType  # value = <ActionType.ACTION_NUM_13: 35>
ACTION_NUM_14: ActionType  # value = <ActionType.ACTION_NUM_14: 36>
ACTION_NUM_15: ActionType  # value = <ActionType.ACTION_NUM_15: 37>
ACTION_NUM_16: ActionType  # value = <ActionType.ACTION_NUM_16: 38>
ACTION_NUM_17: ActionType  # value = <ActionType.ACTION_NUM_17: 39>
ACTION_NUM_18: ActionType  # value = <ActionType.ACTION_NUM_18: 40>
ACTION_NUM_19: ActionType  # value = <ActionType.ACTION_NUM_19: 41>
ACTION_NUM_2: ActionType  # value = <ActionType.ACTION_NUM_2: 24>
ACTION_NUM_20: ActionType  # value = <ActionType.ACTION_NUM_20: 42>
ACTION_NUM_21: ActionType  # value = <ActionType.ACTION_NUM_21: 43>
ACTION_NUM_22: ActionType  # value = <ActionType.ACTION_NUM_22: 44>
ACTION_NUM_23: ActionType  # value = <ActionType.ACTION_NUM_23: 45>
ACTION_NUM_24: ActionType  # value = <ActionType.ACTION_NUM_24: 46>
ACTION_NUM_25: ActionType  # value = <ActionType.ACTION_NUM_25: 47>
ACTION_NUM_26: ActionType  # value = <ActionType.ACTION_NUM_26: 48>
ACTION_NUM_27: ActionType  # value = <ActionType.ACTION_NUM_27: 49>
ACTION_NUM_28: ActionType  # value = <ActionType.ACTION_NUM_28: 50>
ACTION_NUM_29: ActionType  # value = <ActionType.ACTION_NUM_29: 51>
ACTION_NUM_3: ActionType  # value = <ActionType.ACTION_NUM_3: 25>
ACTION_NUM_30: ActionType  # value = <ActionType.ACTION_NUM_30: 52>
ACTION_NUM_31: ActionType  # value = <ActionType.ACTION_NUM_31: 53>
ACTION_NUM_32: ActionType  # value = <ActionType.ACTION_NUM_32: 54>
ACTION_NUM_33: ActionType  # value = <ActionType.ACTION_NUM_33: 55>
ACTION_NUM_34: ActionType  # value = <ActionType.ACTION_NUM_34: 56>
ACTION_NUM_35: ActionType  # value = <ActionType.ACTION_NUM_35: 57>
ACTION_NUM_36: ActionType  # value = <ActionType.ACTION_NUM_36: 58>
ACTION_NUM_37: ActionType  # value = <ActionType.ACTION_NUM_37: 59>
ACTION_NUM_38: ActionType  # value = <ActionType.ACTION_NUM_38: 60>
ACTION_NUM_39: ActionType  # value = <ActionType.ACTION_NUM_39: 61>
ACTION_NUM_4: ActionType  # value = <ActionType.ACTION_NUM_4: 26>
ACTION_NUM_40: ActionType  # value = <ActionType.ACTION_NUM_40: 62>
ACTION_NUM_41: ActionType  # value = <ActionType.ACTION_NUM_41: 63>
ACTION_NUM_42: ActionType  # value = <ActionType.ACTION_NUM_42: 64>
ACTION_NUM_43: ActionType  # value = <ActionType.ACTION_NUM_43: 65>
ACTION_NUM_44: ActionType  # value = <ActionType.ACTION_NUM_44: 66>
ACTION_NUM_45: ActionType  # value = <ActionType.ACTION_NUM_45: 67>
ACTION_NUM_46: ActionType  # value = <ActionType.ACTION_NUM_46: 68>
ACTION_NUM_47: ActionType  # value = <ActionType.ACTION_NUM_47: 69>
ACTION_NUM_48: ActionType  # value = <ActionType.ACTION_NUM_48: 70>
ACTION_NUM_49: ActionType  # value = <ActionType.ACTION_NUM_49: 71>
ACTION_NUM_5: ActionType  # value = <ActionType.ACTION_NUM_5: 27>
ACTION_NUM_50: ActionType  # value = <ActionType.ACTION_NUM_50: 72>
ACTION_NUM_51: ActionType  # value = <ActionType.ACTION_NUM_51: 73>
ACTION_NUM_52: ActionType  # value = <ActionType.ACTION_NUM_52: 74>
ACTION_NUM_53: ActionType  # value = <ActionType.ACTION_NUM_53: 75>
ACTION_NUM_54: ActionType  # value = <ActionType.ACTION_NUM_54: 76>
ACTION_NUM_55: ActionType  # value = <ActionType.ACTION_NUM_55: 77>
ACTION_NUM_56: ActionType  # value = <ActionType.ACTION_NUM_56: 78>
ACTION_NUM_57: ActionType  # value = <ActionType.ACTION_NUM_57: 79>
ACTION_NUM_58: ActionType  # value = <ActionType.ACTION_NUM_58: 80>
ACTION_NUM_59: ActionType  # value = <ActionType.ACTION_NUM_59: 81>
ACTION_NUM_6: ActionType  # value = <ActionType.ACTION_NUM_6: 28>
ACTION_NUM_60: ActionType  # value = <ActionType.ACTION_NUM_60: 82>
ACTION_NUM_61: ActionType  # value = <ActionType.ACTION_NUM_61: 83>
ACTION_NUM_62: ActionType  # value = <ActionType.ACTION_NUM_62: 84>
ACTION_NUM_63: ActionType  # value = <ActionType.ACTION_NUM_63: 85>
ACTION_NUM_64: ActionType  # value = <ActionType.ACTION_NUM_64: 86>
ACTION_NUM_65: ActionType  # value = <ActionType.ACTION_NUM_65: 87>
ACTION_NUM_66: ActionType  # value = <ActionType.ACTION_NUM_66: 88>
ACTION_NUM_67: ActionType  # value = <ActionType.ACTION_NUM_67: 89>
ACTION_NUM_68: ActionType  # value = <ActionType.ACTION_NUM_68: 90>
ACTION_NUM_69: ActionType  # value = <ActionType.ACTION_NUM_69: 91>
ACTION_NUM_7: ActionType  # value = <ActionType.ACTION_NUM_7: 29>
ACTION_NUM_70: ActionType  # value = <ActionType.ACTION_NUM_70: 92>
ACTION_NUM_71: ActionType  # value = <ActionType.ACTION_NUM_71: 93>
ACTION_NUM_72: ActionType  # value = <ActionType.ACTION_NUM_72: 94>
ACTION_NUM_73: ActionType  # value = <ActionType.ACTION_NUM_73: 95>
ACTION_NUM_74: ActionType  # value = <ActionType.ACTION_NUM_74: 96>
ACTION_NUM_75: ActionType  # value = <ActionType.ACTION_NUM_75: 97>
ACTION_NUM_76: ActionType  # value = <ActionType.ACTION_NUM_76: 98>
ACTION_NUM_77: ActionType  # value = <ActionType.ACTION_NUM_77: 99>
ACTION_NUM_78: ActionType  # value = <ActionType.ACTION_NUM_78: 100>
ACTION_NUM_79: ActionType  # value = <ActionType.ACTION_NUM_79: 101>
ACTION_NUM_8: ActionType  # value = <ActionType.ACTION_NUM_8: 30>
ACTION_NUM_80: ActionType  # value = <ActionType.ACTION_NUM_80: 102>
ACTION_NUM_81: ActionType  # value = <ActionType.ACTION_NUM_81: 103>
ACTION_NUM_82: ActionType  # value = <ActionType.ACTION_NUM_82: 104>
ACTION_NUM_83: ActionType  # value = <ActionType.ACTION_NUM_83: 105>
ACTION_NUM_84: ActionType  # value = <ActionType.ACTION_NUM_84: 106>
ACTION_NUM_85: ActionType  # value = <ActionType.ACTION_NUM_85: 107>
ACTION_NUM_86: ActionType  # value = <ActionType.ACTION_NUM_86: 108>
ACTION_NUM_87: ActionType  # value = <ActionType.ACTION_NUM_87: 109>
ACTION_NUM_88: ActionType  # value = <ActionType.ACTION_NUM_88: 110>
ACTION_NUM_89: ActionType  # value = <ActionType.ACTION_NUM_89: 111>
ACTION_NUM_9: ActionType  # value = <ActionType.ACTION_NUM_9: 31>
ACTION_NUM_90: ActionType  # value = <ActionType.ACTION_NUM_90: 112>
ACTION_NUM_91: ActionType  # value = <ActionType.ACTION_NUM_91: 113>
ACTION_NUM_92: ActionType  # value = <ActionType.ACTION_NUM_92: 114>
ACTION_NUM_93: ActionType  # value = <ActionType.ACTION_NUM_93: 115>
ACTION_NUM_94: ActionType  # value = <ActionType.ACTION_NUM_94: 116>
ACTION_NUM_95: ActionType  # value = <ActionType.ACTION_NUM_95: 117>
ACTION_NUM_96: ActionType  # value = <ActionType.ACTION_NUM_96: 118>
ACTION_NUM_97: ActionType  # value = <ActionType.ACTION_NUM_97: 119>
ACTION_NUM_98: ActionType  # value = <ActionType.ACTION_NUM_98: 120>
ACTION_NUM_99: ActionType  # value = <ActionType.ACTION_NUM_99: 121>
ACTION_PRAY: ActionType  # value = <ActionType.ACTION_PRAY: 20>
ACTION_SELECT_HAND_0: ActionType  # value = <ActionType.ACTION_SELECT_HAND_0: 0>
ACTION_SELECT_HAND_1: ActionType  # value = <ActionType.ACTION_SELECT_HAND_1: 1>
ACTION_SELECT_HAND_10: ActionType  # value = <ActionType.ACTION_SELECT_HAND_10: 10>
ACTION_SELECT_HAND_11: ActionType  # value = <ActionType.ACTION_SELECT_HAND_11: 11>
ACTION_SELECT_HAND_12: ActionType  # value = <ActionType.ACTION_SELECT_HAND_12: 12>
ACTION_SELECT_HAND_13: ActionType  # value = <ActionType.ACTION_SELECT_HAND_13: 13>
ACTION_SELECT_HAND_14: ActionType  # value = <ActionType.ACTION_SELECT_HAND_14: 14>
ACTION_SELECT_HAND_15: ActionType  # value = <ActionType.ACTION_SELECT_HAND_15: 15>
ACTION_SELECT_HAND_16: ActionType  # value = <ActionType.ACTION_SELECT_HAND_16: 16>
ACTION_SELECT_HAND_17: ActionType  # value = <ActionType.ACTION_SELECT_HAND_17: 17>
ACTION_SELECT_HAND_2: ActionType  # value = <ActionType.ACTION_SELECT_HAND_2: 2>
ACTION_SELECT_HAND_3: ActionType  # value = <ActionType.ACTION_SELECT_HAND_3: 3>
ACTION_SELECT_HAND_4: ActionType  # value = <ActionType.ACTION_SELECT_HAND_4: 4>
ACTION_SELECT_HAND_5: ActionType  # value = <ActionType.ACTION_SELECT_HAND_5: 5>
ACTION_SELECT_HAND_6: ActionType  # value = <ActionType.ACTION_SELECT_HAND_6: 6>
ACTION_SELECT_HAND_7: ActionType  # value = <ActionType.ACTION_SELECT_HAND_7: 7>
ACTION_SELECT_HAND_8: ActionType  # value = <ActionType.ACTION_SELECT_HAND_8: 8>
ACTION_SELECT_HAND_9: ActionType  # value = <ActionType.ACTION_SELECT_HAND_9: 9>
ACTION_SPACE_SIZE: int = 122
ACTION_TARGET_OPP: ActionType  # value = <ActionType.ACTION_TARGET_OPP: 18>
ACTION_TARGET_SELF: ActionType  # value = <ActionType.ACTION_TARGET_SELF: 19>
APOCALYPSE_DEVIL_THRESHOLDS: list = [7, 12, 15, 20, 25]
APOCALYPSE_TURN: int = 150
ASCENSION_BOW_TRIGGERED_POWER: int = 30
ATTACK_HIT: EventType  # value = <EventType.ATTACK_HIT: 6>
ATTACK_MISS: EventType  # value = <EventType.ATTACK_MISS: 7>
BLACK_HOLE: PhenomenonType  # value = <PhenomenonType.BLACK_HOLE: 5>
BLOCK_ATTACK: EventType  # value = <EventType.BLOCK_ATTACK: 20>
BOUNCE_ATTACK: EventType  # value = <EventType.BOUNCE_ATTACK: 21>
BUY_CARD: EventType  # value = <EventType.BUY_CARD: 14>
CARD_EMPTY: int = -1
CLEANUP: TurnEndSubstep  # value = <TurnEndSubstep.CLEANUP: 6>
CLEANUP_DEATH_CHECK: TurnEndSubstep  # value = <TurnEndSubstep.CLEANUP_DEATH_CHECK: 5>
CONFIRM_ATTACK: EventType  # value = <EventType.CONFIRM_ATTACK: 3>
CONFIRM_DEFENSE: EventType  # value = <EventType.CONFIRM_DEFENSE: 4>
CURSE_COLD: HitCurse  # value = <HitCurse.CURSE_COLD: 5>
CURSE_DARK_CLOUD: CurseType  # value = <CurseType.CURSE_DARK_CLOUD: 2>
CURSE_DREAM: CurseType  # value = <CurseType.CURSE_DREAM: 3>
CURSE_FEVER: HitCurse  # value = <HitCurse.CURSE_FEVER: 6>
CURSE_FLASH: CurseType  # value = <CurseType.CURSE_FLASH: 1>
CURSE_FOG: CurseType  # value = <CurseType.CURSE_FOG: 0>
CURSE_HEAVEN: HitCurse  # value = <HitCurse.CURSE_HEAVEN: 8>
CURSE_HELL: HitCurse  # value = <HitCurse.CURSE_HELL: 7>
CURSE_NONE: HitCurse  # value = <HitCurse.CURSE_NONE: 0>
DEATH_CHECK_START: TurnEndSubstep  # value = <TurnEndSubstep.DEATH_CHECK_START: 0>
DENSE_FOG: PhenomenonType  # value = <PhenomenonType.DENSE_FOG: 1>
DISCARD_CARD: EventType  # value = <EventType.DISCARD_CARD: 18>
DRAW_CARD: EventType  # value = <EventType.DRAW_CARD: 17>
DREAM_DISGUISE_RATE: int = 50
EARTH: GuardianType  # value = <GuardianType.EARTH: 9>
ECLIPSE: PhenomenonType  # value = <PhenomenonType.ECLIPSE: 9>
EFFECT_CURSE: EventType  # value = <EventType.EFFECT_CURSE: 27>
EFFECT_GUARDIAN: EventType  # value = <EventType.EFFECT_GUARDIAN: 9>
EFFECT_SICKNESS: EventType  # value = <EventType.EFFECT_SICKNESS: 8>
ELEM_DARKNESS: Element  # value = <Element.ELEM_DARKNESS: 6>
ELEM_FIRE: Element  # value = <Element.ELEM_FIRE: 1>
ELEM_LIGHT: Element  # value = <Element.ELEM_LIGHT: 5>
ELEM_NONE: Element  # value = <Element.ELEM_NONE: 0>
ELEM_STONE: Element  # value = <Element.ELEM_STONE: 4>
ELEM_WATER: Element  # value = <Element.ELEM_WATER: 2>
ELEM_WOOD: Element  # value = <Element.ELEM_WOOD: 3>
EXCHANGE: EventType  # value = <EventType.EXCHANGE: 16>
FINAL_DEATH_CHECK: TurnEndSubstep  # value = <TurnEndSubstep.FINAL_DEATH_CHECK: 3>
GIGANTIC_TUB: PhenomenonType  # value = <PhenomenonType.GIGANTIC_TUB: 4>
GOLD_MINE: PhenomenonType  # value = <PhenomenonType.GOLD_MINE: 7>
GUARDIAN_ACT: TurnEndSubstep  # value = <TurnEndSubstep.GUARDIAN_ACT: 4>
GUARDIAN_ACT_CHOICE_THRESHOLDS: list = [30, 55, 75, 90, 100]
GUARDIAN_ENTER: EventType  # value = <EventType.GUARDIAN_ENTER: 25>
GUARDIAN_LEAVE: EventType  # value = <EventType.GUARDIAN_LEAVE: 26>
HEAL_HP: EventType  # value = <EventType.HEAL_HP: 12>
HEAL_MP: EventType  # value = <EventType.HEAL_MP: 13>
HISTORY_LENGTH: int = 64
JUPITER: GuardianType  # value = <GuardianType.JUPITER: 3>
MAGNETIC_STORM: PhenomenonType  # value = <PhenomenonType.MAGNETIC_STORM: 8>
MARS: GuardianType  # value = <GuardianType.MARS: 1>
MAX_HAND_SIZE: int = 18
MERCURY: GuardianType  # value = <GuardianType.MERCURY: 2>
MOON: GuardianType  # value = <GuardianType.MOON: 10>
MUSHROOM: PhenomenonType  # value = <PhenomenonType.MUSHROOM: 2>
NEPTUNE: GuardianType  # value = <GuardianType.NEPTUNE: 7>
NONE: EventType  # value = <EventType.NONE: 0>
OBSERVATION_FEATURE_SIZE: int = 584
OBSERVATION_SIZE: int = 592
PASS_DEFENSE: EventType  # value = <EventType.PASS_DEFENSE: 5>
PHASE_ATTACK_PLUS: GamePhase  # value = <GamePhase.PHASE_ATTACK_PLUS: 3>
PHASE_BUY: GamePhase  # value = <GamePhase.PHASE_BUY: 11>
PHASE_BUY_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_BUY_SELECT_MIRROR: 12>
PHASE_DEFENSE: GamePhase  # value = <GamePhase.PHASE_DEFENSE: 7>
PHASE_DISCARD: GamePhase  # value = <GamePhase.PHASE_DISCARD: 16>
PHASE_END: GamePhase  # value = <GamePhase.PHASE_END: 17>
PHASE_EXCHANGE_HP: GamePhase  # value = <GamePhase.PHASE_EXCHANGE_HP: 14>
PHASE_EXCHANGE_MP: GamePhase  # value = <GamePhase.PHASE_EXCHANGE_MP: 15>
PHASE_GROUP_MIRACLE_PLUS: GamePhase  # value = <GamePhase.PHASE_GROUP_MIRACLE_PLUS: 6>
PHASE_GROUP_WEAPON: GamePhase  # value = <GamePhase.PHASE_GROUP_WEAPON: 4>
PHASE_GUARDIAN: GamePhase  # value = <GamePhase.PHASE_GUARDIAN: 0>
PHASE_MAIN: GamePhase  # value = <GamePhase.PHASE_MAIN: 1>
PHASE_MAIN_TARGET_SELECT: GamePhase  # value = <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>
PHASE_MIRACLE_DEFENSE: GamePhase  # value = <GamePhase.PHASE_MIRACLE_DEFENSE: 8>
PHASE_MIRACLE_PLUS: GamePhase  # value = <GamePhase.PHASE_MIRACLE_PLUS: 5>
PHASE_SELL_SELECT: GamePhase  # value = <GamePhase.PHASE_SELL_SELECT: 9>
PHASE_SELL_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>
PHASE_SUNDRY_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>
PLUTO: GuardianType  # value = <GuardianType.PLUTO: 6>
REACTION_BLOCK: ReactionType  # value = <ReactionType.REACTION_BLOCK: 3>
REACTION_BOUNCE: ReactionType  # value = <ReactionType.REACTION_BOUNCE: 1>
REACTION_NONE: ReactionType  # value = <ReactionType.REACTION_NONE: 0>
REACTION_REFLECT: ReactionType  # value = <ReactionType.REACTION_REFLECT: 2>
REFLECT_DAMAGE: EventType  # value = <EventType.REFLECT_DAMAGE: 10>
REFLECT_MIRROR: EventType  # value = <EventType.REFLECT_MIRROR: 23>
REFUSE_DEAL: EventType  # value = <EventType.REFUSE_DEAL: 19>
RING_EFFECT: EventType  # value = <EventType.RING_EFFECT: 24>
ROLL_MAX: int = 2147483647
ROLL_MIN: int = -2147483648
SATURN: GuardianType  # value = <GuardianType.SATURN: 4>
SAW_BOOM_BOOM_ATTACK_COUNT: int = 2
SELL_CARD: EventType  # value = <EventType.SELL_CARD: 15>
SICKNESS_COLD: SicknessType  # value = <SicknessType.SICKNESS_COLD: 1>
SICKNESS_DAMAGE: TurnEndSubstep  # value = <TurnEndSubstep.SICKNESS_DAMAGE: 2>
SICKNESS_FEVER: SicknessType  # value = <SicknessType.SICKNESS_FEVER: 2>
SICKNESS_HEAVEN: SicknessType  # value = <SicknessType.SICKNESS_HEAVEN: 4>
SICKNESS_HELL: SicknessType  # value = <SicknessType.SICKNESS_HELL: 3>
SICKNESS_NONE: SicknessType  # value = <SicknessType.SICKNESS_NONE: 0>
SICKNESS_WORSEN: TurnEndSubstep  # value = <TurnEndSubstep.SICKNESS_WORSEN: 1>
STAGE_CARD: EventType  # value = <EventType.STAGE_CARD: 1>
SUNSET: PhenomenonType  # value = <PhenomenonType.SUNSET: 0>
SUN_AMULET_REVIVE_HP: int = 10
TAKE_DAMAGE: EventType  # value = <EventType.TAKE_DAMAGE: 11>
TIMING_ATK_DEFENCE: int = 64
TIMING_ATK_PLUS: int = 16
TIMING_MAIN_ATK: int = 1
TIMING_MAIN_DEAL: int = 8
TIMING_MAIN_MIRACLE: int = 2
TIMING_MAIN_SUNDRY: int = 4
TIMING_MIRACLE_DEFENCE: int = 128
TIMING_MIRACLE_PLUS: int = 32
TORNADO: PhenomenonType  # value = <PhenomenonType.TORNADO: 3>
TRIGGER_PHENOMENON: EventType  # value = <EventType.TRIGGER_PHENOMENON: 22>
TURN_TRANSITION: TurnEndSubstep  # value = <TurnEndSubstep.TURN_TRANSITION: 7>
UNSTAGE_CARD: EventType  # value = <EventType.UNSTAGE_CARD: 2>
URANUS: GuardianType  # value = <GuardianType.URANUS: 5>
VENUS: GuardianType  # value = <GuardianType.VENUS: 8>
WARM_CURRENT: PhenomenonType  # value = <PhenomenonType.WARM_CURRENT: 6>
