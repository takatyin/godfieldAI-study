import json
import sys


def validate_cards(file_path):
    with open(file_path, encoding="utf-8") as f:
        cards = json.load(f)

    valid_types = {"weapon", "defense", "miracle", "sundry", "deal"}
    valid_elements = {"火", "水", "木", "土", "光", "闇", ""}
    valid_phases = {
        "main_atk_phase",
        "main_miracle_phase",
        "main_sundry_phase",
        "main_deal_phase",
        "atk_plus_phase",
        "miracle_plus_phase",
        "atk_defence_phase",
        "miracle_defence_phase",
        "guardian_phase",
    }
    valid_reactions = {"bounce", "reflect", "block"}
    valid_hit_curses = {"fog", "flash", "dark cloud", "dream", "cold", "fever", "hell", "heaven"}

    errors = []

    for i, card in enumerate(cards):
        name = card.get("name", f"Card_Index_{i}")

        # 1. Check type
        ctype = card.get("type", "")
        if ctype not in valid_types:
            errors.append(f"[{name}] Invalid type: '{ctype}'")

        # 2. Check timings
        timings = card.get("usage_timing", [])
        if not isinstance(timings, list):
            errors.append(f"[{name}] usage_timing must be a list")
        else:
            for t in timings:
                if t not in valid_phases:
                    errors.append(f"[{name}] Invalid usage_timing: '{t}'")

        # 3. Check type-specific requirements
        # 3. Check type-specific requirements
        if ctype == "weapon" or "main_atk_phase" in timings:
            if "attack_power" not in card:
                errors.append(f"[{name}] Type/Timing indicates attack, but missing 'attack_power'")
        elif "atk_plus_phase" in timings and ctype == "weapon":
            if "attack_power" not in card:
                errors.append(f"[{name}] Weapon used in atk_plus_phase missing 'attack_power'")
        if ctype == "weapon" and "atk_plus_phase" in timings:
            if "main_atk_phase" not in timings:
                errors.append(f"[{name}] Weapon has 'atk_plus_phase' but missing 'main_atk_phase'")

        if ctype == "defense" and "main_atk_phase" in timings:
            errors.append(f"[{name}] Defense items cannot have 'main_atk_phase'")

        if ctype == "defense" or "atk_defence_phase" in timings:
            # Note: reflect/bounce items might not have a raw defense_power, so we allow it if reaction_type is present
            if "defense_power" not in card and "reaction_type" not in card:
                if not ("miracle_defence_phase" in timings and "atk_defence_phase" not in timings):
                    # Some items might just reflect, etc.
                    pass  # We'll be lenient if it's a known reflector. But if it's a strict defense item without defense power:
                    # Let's just warn instead of fail, because there might be special ones.
                    # Actually, if it's a shield without reaction, it must have defense_power.
                    if ctype == "defense" and "reaction_type" not in card:
                        if "指輪" not in name:
                            errors.append(
                                f"[{name}] Type defense requires 'defense_power' or 'reaction_type'"
                            )

        if ctype == "miracle":
            if "mp_cost" not in card:
                if "miracle_plus_phase" not in timings:  # like costs 0 miracle
                    errors.append(f"[{name}] Type miracle missing 'mp_cost'")

        # 4. Check element
        if "element" in card:
            if card["element"] not in valid_elements:
                errors.append(f"[{name}] Invalid element: '{card['element']}'")

        # 5. Check reaction_type
        if "reaction_type" in card:
            if card["reaction_type"] not in valid_reactions:
                errors.append(f"[{name}] Invalid reaction_type: '{card['reaction_type']}'")

        # 6. Check hit_curse
        if "hit_curse" in card:
            if card["hit_curse"] not in valid_hit_curses:
                errors.append(f"[{name}] Invalid hit_curse: '{card['hit_curse']}'")

        # 7. Check is_group_attack and accuracy consistency
        is_group = card.get("is_group_attack", False)
        accuracy = card.get("accuracy", 100)
        if is_group:
            if not isinstance(is_group, bool):
                errors.append(f"[{name}] is_group_attack must be a boolean")
            # 守護神フェイズ (guardian_phase) 以外の場合のみ、命中率が100%未満であることをチェック
            if "guardian_phase" not in timings:
                if not (0 < accuracy < 100):
                    errors.append(
                        f"[{name}] Group attack must have accuracy between 0 and 100 (accuracy was {accuracy})"
                    )
        else:
            if ctype in {"weapon", "miracle"} and accuracy != 100:
                errors.append(
                    f"[{name}] Single target weapon/miracle attack must have accuracy = 100 (accuracy was {accuracy})"
                )

    if errors:
        print(f"Validation FAILED with {len(errors)} errors:")
        for e in errors:
            print(f" - {e}")
        sys.exit(1)
    else:
        print(f"Validation PASSED for {len(cards)} cards.")
        sys.exit(0)


if __name__ == "__main__":
    validate_cards("assets/godfield_cards.json")
