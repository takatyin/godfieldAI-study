import json
import os

import godfield_core

_NAME_TO_ID_CACHE = None
_JAPANESE_NAME_TO_ID_CACHE = None
_ALL_CARDS_CACHE = None


def _load_cards_if_needed():
    global _NAME_TO_ID_CACHE, _JAPANESE_NAME_TO_ID_CACHE, _ALL_CARDS_CACHE
    if _NAME_TO_ID_CACHE is None:
        _NAME_TO_ID_CACHE = {}
        _JAPANESE_NAME_TO_ID_CACHE = {}
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        json_path = os.path.join(project_root, "assets", "godfield_cards.json")
        with open(json_path, encoding="utf-8") as f:
            _ALL_CARDS_CACHE = json.load(f)
            for c in _ALL_CARDS_CACHE:
                if "id_str" in c and c["id_str"]:
                    _NAME_TO_ID_CACHE[c["id_str"]] = c["id"]
                if "name" in c and c["name"]:
                    _JAPANESE_NAME_TO_ID_CACHE[c["name"]] = c["id"]


def get_all_cards() -> list[dict]:
    """Gets the list of all card data dictionaries loaded from json."""
    _load_cards_if_needed()
    return _ALL_CARDS_CACHE


def find_card_by_type(type=None, element=None) -> int:
    """Finds the first card ID that matches the given type and element."""
    data = get_all_cards()
    for c in data:
        if type and c.get("type") != type:
            continue
        if element is not None:
            card_elem = c.get("element", "")
            if card_elem != element:
                continue
        return c["id"]
    return -1


def find_card_by_name(name: str) -> int:
    """Gets the integer card ID by its Japanese name or id_str."""
    _load_cards_if_needed()
    if name in _NAME_TO_ID_CACHE:
        return _NAME_TO_ID_CACHE[name]
    if name in _JAPANESE_NAME_TO_ID_CACHE:
        return _JAPANESE_NAME_TO_ID_CACHE[name]
    raise ValueError(f"Card name '{name}' not found in godfield_cards.json")


class SimulationRunner:
    """
    A utility class to construct and manipulate a single InternalState
    for unit testing the GodField core game logic.
    """

    def __init__(self):
        # Create a clean default internal state
        self.state: godfield_core.InternalState = godfield_core.InternalState()

        _load_cards_if_needed()
        self._name_to_id = _NAME_TO_ID_CACHE

        self.reset_state()

    def reset_state(self):
        """Resets the state to a clean configuration (e.g., clears hands and unknown flags)."""
        godfield_core.clear_state(self.state)
        self.state.current_phase = godfield_core.GamePhase.PHASE_MAIN
        self.state.current_actor_id = 0
        self.state.is_done = False
        self.state.attacker_id = -1
        self.state.defender_id = -1
        self.state.pending_attack_power = 0
        self.state.pending_attack_element = godfield_core.Element.ELEM_NONE

        for p in range(2):
            self.set_status(p, hp=40, mp=0, money=0)
            for i in range(18):
                self.state.set_true_hand(p, i, -1)
                self.state.set_is_known_to_opp(p, i, False)
                self.state.set_is_used(p, i, False)

    def set_hand(self, player: int, cards: list[str]):
        """Set the hand for a player using string IDs or integers."""
        for i in range(18):
            if i < len(cards):
                card = cards[i]
                card_id = self._name_to_id.get(card) if isinstance(card, str) else card
                self.state.set_true_hand(player, i, card_id)
                self.state.set_apparent_hand(player, i, card_id)
            else:
                self.state.set_true_hand(player, i, -1)  # empty
                self.state.set_apparent_hand(player, i, -1)
            self.state.set_is_known_to_opp(player, i, False)
            self.state.set_is_used(player, i, False)

    def set_status(self, player: int, hp: int = 40, mp: int = 0, money: int = 0):
        self.state.set_hp(player, hp)
        self.state.set_mp(player, mp)
        self.state.set_money(player, money)

    def step(self, action: godfield_core.ActionType):
        """Advances the game state by one action."""
        godfield_core.step_game(self.state, action)
