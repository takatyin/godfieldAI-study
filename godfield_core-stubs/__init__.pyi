"""
GodField core engine and RL environment pool
"""
from __future__ import annotations
import numpy
import numpy.typing
import typing
__all__: list[str] = ['ACTION_CONFIRM', 'ACTION_DEAL_NO', 'ACTION_DEAL_YES', 'ACTION_DISCARD', 'ACTION_NUM_0', 'ACTION_NUM_1', 'ACTION_NUM_10', 'ACTION_NUM_11', 'ACTION_NUM_12', 'ACTION_NUM_13', 'ACTION_NUM_14', 'ACTION_NUM_15', 'ACTION_NUM_16', 'ACTION_NUM_17', 'ACTION_NUM_18', 'ACTION_NUM_19', 'ACTION_NUM_2', 'ACTION_NUM_20', 'ACTION_NUM_21', 'ACTION_NUM_22', 'ACTION_NUM_23', 'ACTION_NUM_24', 'ACTION_NUM_25', 'ACTION_NUM_26', 'ACTION_NUM_27', 'ACTION_NUM_28', 'ACTION_NUM_29', 'ACTION_NUM_3', 'ACTION_NUM_30', 'ACTION_NUM_31', 'ACTION_NUM_32', 'ACTION_NUM_33', 'ACTION_NUM_34', 'ACTION_NUM_35', 'ACTION_NUM_36', 'ACTION_NUM_37', 'ACTION_NUM_38', 'ACTION_NUM_39', 'ACTION_NUM_4', 'ACTION_NUM_40', 'ACTION_NUM_41', 'ACTION_NUM_42', 'ACTION_NUM_43', 'ACTION_NUM_44', 'ACTION_NUM_45', 'ACTION_NUM_46', 'ACTION_NUM_47', 'ACTION_NUM_48', 'ACTION_NUM_49', 'ACTION_NUM_5', 'ACTION_NUM_50', 'ACTION_NUM_51', 'ACTION_NUM_52', 'ACTION_NUM_53', 'ACTION_NUM_54', 'ACTION_NUM_55', 'ACTION_NUM_56', 'ACTION_NUM_57', 'ACTION_NUM_58', 'ACTION_NUM_59', 'ACTION_NUM_6', 'ACTION_NUM_60', 'ACTION_NUM_61', 'ACTION_NUM_62', 'ACTION_NUM_63', 'ACTION_NUM_64', 'ACTION_NUM_65', 'ACTION_NUM_66', 'ACTION_NUM_67', 'ACTION_NUM_68', 'ACTION_NUM_69', 'ACTION_NUM_7', 'ACTION_NUM_70', 'ACTION_NUM_71', 'ACTION_NUM_72', 'ACTION_NUM_73', 'ACTION_NUM_74', 'ACTION_NUM_75', 'ACTION_NUM_76', 'ACTION_NUM_77', 'ACTION_NUM_78', 'ACTION_NUM_79', 'ACTION_NUM_8', 'ACTION_NUM_80', 'ACTION_NUM_81', 'ACTION_NUM_82', 'ACTION_NUM_83', 'ACTION_NUM_84', 'ACTION_NUM_85', 'ACTION_NUM_86', 'ACTION_NUM_87', 'ACTION_NUM_88', 'ACTION_NUM_89', 'ACTION_NUM_9', 'ACTION_NUM_90', 'ACTION_NUM_91', 'ACTION_NUM_92', 'ACTION_NUM_93', 'ACTION_NUM_94', 'ACTION_NUM_95', 'ACTION_NUM_96', 'ACTION_NUM_97', 'ACTION_NUM_98', 'ACTION_NUM_99', 'ACTION_PRAY', 'ACTION_SELECT_HAND_0', 'ACTION_SELECT_HAND_1', 'ACTION_SELECT_HAND_10', 'ACTION_SELECT_HAND_11', 'ACTION_SELECT_HAND_12', 'ACTION_SELECT_HAND_13', 'ACTION_SELECT_HAND_14', 'ACTION_SELECT_HAND_15', 'ACTION_SELECT_HAND_16', 'ACTION_SELECT_HAND_17', 'ACTION_SELECT_HAND_2', 'ACTION_SELECT_HAND_3', 'ACTION_SELECT_HAND_4', 'ACTION_SELECT_HAND_5', 'ACTION_SELECT_HAND_6', 'ACTION_SELECT_HAND_7', 'ACTION_SELECT_HAND_8', 'ACTION_SELECT_HAND_9', 'ACTION_TARGET_OPP', 'ACTION_TARGET_SELF', 'ActionType', 'CARD_EMPTY', 'CURSE_COLD', 'CURSE_DARK_CLOUD', 'CURSE_DREAM', 'CURSE_FEVER', 'CURSE_FLASH', 'CURSE_FOG', 'CURSE_HEAVEN', 'CURSE_HELL', 'CURSE_NONE', 'CurseType', 'ELEM_DARKNESS', 'ELEM_FIRE', 'ELEM_LIGHT', 'ELEM_NONE', 'ELEM_STONE', 'ELEM_WATER', 'ELEM_WOOD', 'Element', 'EnvPool', 'GamePhase', 'HitCurse', 'InternalState', 'PHASE_ATTACK_PLUS', 'PHASE_BUY', 'PHASE_BUY_SELECT_MIRROR', 'PHASE_DEFENSE', 'PHASE_DISCARD', 'PHASE_END', 'PHASE_EXCHANGE_HP', 'PHASE_EXCHANGE_MP', 'PHASE_GROUP_MIRACLE', 'PHASE_GROUP_WEAPON', 'PHASE_GUARDIAN', 'PHASE_MAIN', 'PHASE_MAIN_TARGET_SELECT', 'PHASE_MIRACLE_DEFENSE', 'PHASE_MIRACLE_PLUS', 'PHASE_SELL_SELECT', 'PHASE_SELL_SELECT_MIRROR', 'PHASE_SUNDRY_SELECT_MIRROR', 'REACTION_BLOCK', 'REACTION_BOUNCE', 'REACTION_NONE', 'REACTION_REFLECT', 'ReactionType', 'SICKNESS_COLD', 'SICKNESS_FEVER', 'SICKNESS_HEAVEN', 'SICKNESS_HELL', 'SICKNESS_NONE', 'SicknessType', 'TIMING_ATK_DEFENCE', 'TIMING_ATK_PLUS', 'TIMING_MAIN_ATK', 'TIMING_MAIN_DEAL', 'TIMING_MAIN_MIRACLE', 'TIMING_MAIN_SUNDRY', 'TIMING_MIRACLE_DEFENCE', 'TIMING_MIRACLE_PLUS', 'clear_state', 'get_card_name', 'get_legal_actions', 'get_registry_size', 'init_game_logic', 'step_game']
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
    def get_observations(self) -> numpy.typing.NDArray[numpy.float32]:
        ...
    def get_ready_env_ids(self) -> numpy.typing.NDArray[numpy.int32]:
        ...
    def reset(self, seed: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def step_all(self, actions: typing.Annotated[numpy.typing.ArrayLike, numpy.int32]) -> None:
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
    
      PHASE_GROUP_MIRACLE
    
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
    PHASE_GROUP_MIRACLE: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GROUP_MIRACLE: 6>
    PHASE_GROUP_WEAPON: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GROUP_WEAPON: 4>
    PHASE_GUARDIAN: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_GUARDIAN: 0>
    PHASE_MAIN: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MAIN: 1>
    PHASE_MAIN_TARGET_SELECT: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>
    PHASE_MIRACLE_DEFENSE: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MIRACLE_DEFENSE: 8>
    PHASE_MIRACLE_PLUS: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_MIRACLE_PLUS: 5>
    PHASE_SELL_SELECT: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SELL_SELECT: 9>
    PHASE_SELL_SELECT_MIRROR: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>
    PHASE_SUNDRY_SELECT_MIRROR: typing.ClassVar[GamePhase]  # value = <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>
    __members__: typing.ClassVar[dict[str, GamePhase]]  # value = {'PHASE_GUARDIAN': <GamePhase.PHASE_GUARDIAN: 0>, 'PHASE_MAIN': <GamePhase.PHASE_MAIN: 1>, 'PHASE_MAIN_TARGET_SELECT': <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>, 'PHASE_ATTACK_PLUS': <GamePhase.PHASE_ATTACK_PLUS: 3>, 'PHASE_GROUP_WEAPON': <GamePhase.PHASE_GROUP_WEAPON: 4>, 'PHASE_MIRACLE_PLUS': <GamePhase.PHASE_MIRACLE_PLUS: 5>, 'PHASE_GROUP_MIRACLE': <GamePhase.PHASE_GROUP_MIRACLE: 6>, 'PHASE_DEFENSE': <GamePhase.PHASE_DEFENSE: 7>, 'PHASE_MIRACLE_DEFENSE': <GamePhase.PHASE_MIRACLE_DEFENSE: 8>, 'PHASE_SELL_SELECT': <GamePhase.PHASE_SELL_SELECT: 9>, 'PHASE_SELL_SELECT_MIRROR': <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>, 'PHASE_BUY_SELECT_MIRROR': <GamePhase.PHASE_BUY_SELECT_MIRROR: 12>, 'PHASE_SUNDRY_SELECT_MIRROR': <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>, 'PHASE_BUY': <GamePhase.PHASE_BUY: 11>, 'PHASE_EXCHANGE_HP': <GamePhase.PHASE_EXCHANGE_HP: 14>, 'PHASE_EXCHANGE_MP': <GamePhase.PHASE_EXCHANGE_MP: 15>, 'PHASE_DISCARD': <GamePhase.PHASE_DISCARD: 16>, 'PHASE_END': <GamePhase.PHASE_END: 17>}
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
    current_phase: GamePhase
    is_done: bool
    pending_absorption: bool
    pending_attack_element: Element
    pending_is_group_attack: bool
    def __init__(self) -> None:
        ...
    def get_curses(self, player_id: typing.SupportsInt | typing.SupportsIndex, curse_idx: CurseType) -> bool:
        ...
    def get_guardian(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_hp(self, player_id: typing.SupportsInt | typing.SupportsIndex) -> int:
        ...
    def get_is_deployed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_is_known_to_opp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_is_used(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
        ...
    def get_miracle_used_this_turn(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex) -> bool:
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
    def set_curses(self, player_id: typing.SupportsInt | typing.SupportsIndex, curse_idx: CurseType, val: bool) -> None:
        ...
    def set_guardian(self, player_id: typing.SupportsInt | typing.SupportsIndex, val: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_hp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hp: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    def set_is_deployed(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, val: bool) -> None:
        ...
    def set_is_known_to_opp(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, is_known: bool) -> None:
        ...
    def set_is_used(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, is_used: bool) -> None:
        ...
    def set_miracle_used_this_turn(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, val: bool) -> None:
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
    def set_true_hand(self, player_id: typing.SupportsInt | typing.SupportsIndex, hand_idx: typing.SupportsInt | typing.SupportsIndex, card_id: typing.SupportsInt | typing.SupportsIndex) -> None:
        ...
    @property
    def attacker_id(self) -> int:
        ...
    @attacker_id.setter
    def attacker_id(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
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
    def turn_end_state(self) -> int:
        ...
    @turn_end_state.setter
    def turn_end_state(self, arg0: typing.SupportsInt | typing.SupportsIndex) -> None:
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
def clear_state(arg0: InternalState) -> None:
    """
    Zero out the state memory preserving RNG
    """
def get_card_name(arg0: typing.SupportsInt | typing.SupportsIndex) -> str:
    """
    Get card name by ID
    """
def get_legal_actions(arg0: InternalState) -> list:
    """
    Get a boolean list of legal actions
    """
def get_registry_size() -> int:
    """
    Get number of cards in registry
    """
def init_game_logic(arg0: list) -> None:
    """
    Initialize the global card registry from JSON
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
ACTION_TARGET_OPP: ActionType  # value = <ActionType.ACTION_TARGET_OPP: 18>
ACTION_TARGET_SELF: ActionType  # value = <ActionType.ACTION_TARGET_SELF: 19>
CARD_EMPTY: int = -1
CURSE_COLD: HitCurse  # value = <HitCurse.CURSE_COLD: 5>
CURSE_DARK_CLOUD: CurseType  # value = <CurseType.CURSE_DARK_CLOUD: 2>
CURSE_DREAM: CurseType  # value = <CurseType.CURSE_DREAM: 3>
CURSE_FEVER: HitCurse  # value = <HitCurse.CURSE_FEVER: 6>
CURSE_FLASH: CurseType  # value = <CurseType.CURSE_FLASH: 1>
CURSE_FOG: CurseType  # value = <CurseType.CURSE_FOG: 0>
CURSE_HEAVEN: HitCurse  # value = <HitCurse.CURSE_HEAVEN: 8>
CURSE_HELL: HitCurse  # value = <HitCurse.CURSE_HELL: 7>
CURSE_NONE: HitCurse  # value = <HitCurse.CURSE_NONE: 0>
ELEM_DARKNESS: Element  # value = <Element.ELEM_DARKNESS: 6>
ELEM_FIRE: Element  # value = <Element.ELEM_FIRE: 1>
ELEM_LIGHT: Element  # value = <Element.ELEM_LIGHT: 5>
ELEM_NONE: Element  # value = <Element.ELEM_NONE: 0>
ELEM_STONE: Element  # value = <Element.ELEM_STONE: 4>
ELEM_WATER: Element  # value = <Element.ELEM_WATER: 2>
ELEM_WOOD: Element  # value = <Element.ELEM_WOOD: 3>
PHASE_ATTACK_PLUS: GamePhase  # value = <GamePhase.PHASE_ATTACK_PLUS: 3>
PHASE_BUY: GamePhase  # value = <GamePhase.PHASE_BUY: 11>
PHASE_BUY_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_BUY_SELECT_MIRROR: 12>
PHASE_DEFENSE: GamePhase  # value = <GamePhase.PHASE_DEFENSE: 7>
PHASE_DISCARD: GamePhase  # value = <GamePhase.PHASE_DISCARD: 16>
PHASE_END: GamePhase  # value = <GamePhase.PHASE_END: 17>
PHASE_EXCHANGE_HP: GamePhase  # value = <GamePhase.PHASE_EXCHANGE_HP: 14>
PHASE_EXCHANGE_MP: GamePhase  # value = <GamePhase.PHASE_EXCHANGE_MP: 15>
PHASE_GROUP_MIRACLE: GamePhase  # value = <GamePhase.PHASE_GROUP_MIRACLE: 6>
PHASE_GROUP_WEAPON: GamePhase  # value = <GamePhase.PHASE_GROUP_WEAPON: 4>
PHASE_GUARDIAN: GamePhase  # value = <GamePhase.PHASE_GUARDIAN: 0>
PHASE_MAIN: GamePhase  # value = <GamePhase.PHASE_MAIN: 1>
PHASE_MAIN_TARGET_SELECT: GamePhase  # value = <GamePhase.PHASE_MAIN_TARGET_SELECT: 2>
PHASE_MIRACLE_DEFENSE: GamePhase  # value = <GamePhase.PHASE_MIRACLE_DEFENSE: 8>
PHASE_MIRACLE_PLUS: GamePhase  # value = <GamePhase.PHASE_MIRACLE_PLUS: 5>
PHASE_SELL_SELECT: GamePhase  # value = <GamePhase.PHASE_SELL_SELECT: 9>
PHASE_SELL_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_SELL_SELECT_MIRROR: 10>
PHASE_SUNDRY_SELECT_MIRROR: GamePhase  # value = <GamePhase.PHASE_SUNDRY_SELECT_MIRROR: 13>
REACTION_BLOCK: ReactionType  # value = <ReactionType.REACTION_BLOCK: 3>
REACTION_BOUNCE: ReactionType  # value = <ReactionType.REACTION_BOUNCE: 1>
REACTION_NONE: ReactionType  # value = <ReactionType.REACTION_NONE: 0>
REACTION_REFLECT: ReactionType  # value = <ReactionType.REACTION_REFLECT: 2>
SICKNESS_COLD: SicknessType  # value = <SicknessType.SICKNESS_COLD: 1>
SICKNESS_FEVER: SicknessType  # value = <SicknessType.SICKNESS_FEVER: 2>
SICKNESS_HEAVEN: SicknessType  # value = <SicknessType.SICKNESS_HEAVEN: 4>
SICKNESS_HELL: SicknessType  # value = <SicknessType.SICKNESS_HELL: 3>
SICKNESS_NONE: SicknessType  # value = <SicknessType.SICKNESS_NONE: 0>
TIMING_ATK_DEFENCE: int = 64
TIMING_ATK_PLUS: int = 16
TIMING_MAIN_ATK: int = 1
TIMING_MAIN_DEAL: int = 8
TIMING_MAIN_MIRACLE: int = 2
TIMING_MAIN_SUNDRY: int = 4
TIMING_MIRACLE_DEFENCE: int = 128
TIMING_MIRACLE_PLUS: int = 32
