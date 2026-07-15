import godfield_core
import json
import os

_NAME_TO_ID_CACHE = None

class SimulationRunner:
    """
    A utility class to construct and manipulate a single InternalState
    for unit testing the GodField core game logic.
    """
    def __init__(self):
        # Create a clean default internal state
        self.state = godfield_core.InternalState()
        
        global _NAME_TO_ID_CACHE
        if _NAME_TO_ID_CACHE is None:
            _NAME_TO_ID_CACHE = {}
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            json_path = os.path.join(project_root, 'assets', 'godfield_cards.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                cards = json.load(f)
                for c in cards:
                    if 'id_str' in c and c['id_str']:
                        _NAME_TO_ID_CACHE[c['id_str']] = c['id']
        
        self._name_to_id = _NAME_TO_ID_CACHE

    def reset_state(self):
        """Resets the state to a clean configuration (e.g., clears hands and unknown flags)."""
        for p in range(2):
            self.set_status(p, hp=40, mp=0, money=0, ailments=0)
            for i in range(9):
                self.state.set_true_hand(p, i, -1)
                self.state.set_is_known_to_opp(p, i, False)

    def set_hand(self, player: int, cards: list[str]):
        """Set the hand for a player using string IDs or integers."""
        for i in range(9):
            if i < len(cards):
                card = cards[i]
                card_id = self._name_to_id.get(card) if isinstance(card, str) else card
                self.state.set_true_hand(player, i, card_id)
            else:
                self.state.set_true_hand(player, i, -1) # empty
            self.state.set_is_known_to_opp(player, i, False)

    def set_status(self, player: int, hp: int = 40, mp: int = 0, money: int = 0, ailments: int = 0):
        self.state.set_hp(player, hp)
        self.state.set_mp(player, mp)
        self.state.set_money(player, money)
        self.state.set_status_ailments(player, ailments)

    def step(self, action: int):
        """Advances the game state by one action."""
        godfield_core.step_game(self.state, action)
