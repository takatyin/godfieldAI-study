"""
Sickness Event Bitmask Constants
"""
from __future__ import annotations
__all__: list[str] = ['FLAG_DAMAGE', 'FLAG_HEAL', 'FLAG_SEIZURE', 'FLAG_WORSENED', 'MASK_TYPE', 'TYPE_COLD', 'TYPE_FEVER', 'TYPE_HEAVEN', 'TYPE_HELL', 'TYPE_NONE']
FLAG_DAMAGE: int = 16
FLAG_HEAL: int = 32
FLAG_SEIZURE: int = 128
FLAG_WORSENED: int = 64
MASK_TYPE: int = 15
TYPE_COLD: int = 1
TYPE_FEVER: int = 2
TYPE_HEAVEN: int = 4
TYPE_HELL: int = 3
TYPE_NONE: int = 0
