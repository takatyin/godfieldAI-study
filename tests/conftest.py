import json
import os

import pytest

import godfield_core


@pytest.fixture(scope="session", autouse=True)
def setup_card_registry():
    # Construct absolute path to assets/godfield_cards.json based on project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(project_root, "assets", "godfield_cards.json")

    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    godfield_core.init_game_logic(cards)
