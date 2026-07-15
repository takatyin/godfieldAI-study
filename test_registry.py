import json
import godfield_core

def test():
    with open('assets/godfield_cards.json', 'r', encoding='utf-8') as f:
        cards = json.load(f)
        
    print(f"Loaded {len(cards)} cards from JSON.")
    godfield_core.init_game_logic(cards)
    
    env = godfield_core.EnvPool(1)
    env.reset(42)
    print("EnvPool initialized and reset successfully!")

if __name__ == '__main__':
    test()
