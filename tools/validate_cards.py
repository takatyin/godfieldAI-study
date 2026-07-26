import json
import sys


def validate_cards(file_path):
    with open(file_path, encoding="utf-8") as f:
        cards = json.load(f)

    valid_types = {"weapon", "defense", "miracle", "sundry", "deal", "devil", "phenomena", "guardian"}
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

    # Strict whitelists of allowed keys by type
    allowed_keys_by_type = {
        "weapon": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "element", "attack_power", "defense_power",
            "accuracy", "is_group_attack", "reaction_type", "hit_curse"
        },
        "defense": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "element", "defense_power", "attack_power",
            "accuracy", "reaction_type"
        },
        "miracle": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "element", "attack_power", "accuracy",
            "is_group_attack", "hit_curse", "mp_cost", "reaction_type"
        },
        "sundry": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "attack_power", "hit_curse"
        },
        "deal": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate"
        },
        "devil": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate"
        },
        "phenomena": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "element", "attack_power", "accuracy",
            "is_group_attack"
        },
        "guardian": {
            "id", "name", "id_str", "description", "type", "usage_timing",
            "price", "drop_rate", "element", "attack_power", "accuracy",
            "is_group_attack", "hit_curse"
        }
    }

    errors = []
    seen_ids = set()
    seen_id_strs = set()
    seen_names = set()

    for i, card in enumerate(cards):
        name = card.get("name", f"Card_Index_{i}")

        # 1. Uniqueness check
        cid = card.get("id")
        if cid is None:
            errors.append(f"[{name}] Missing 'id'")
        else:
            if not isinstance(cid, int) or cid < 0:
                errors.append(f"[{name}] 'id' must be a non-negative integer, got {repr(cid)}")
            elif cid in seen_ids:
                errors.append(f"[{name}] Duplicate 'id': {cid}")
            seen_ids.add(cid)

        id_str = card.get("id_str")
        if not id_str or not isinstance(id_str, str):
            errors.append(f"[{name}] 'id_str' must be a non-empty string")
        else:
            if id_str in seen_id_strs:
                errors.append(f"[{name}] Duplicate 'id_str': '{id_str}'")
            seen_id_strs.add(id_str)

        card_name = card.get("name")
        if not card_name or not isinstance(card_name, str):
            errors.append(f"[{name}] 'name' must be a non-empty string")
        else:
            if card_name in seen_names:
                errors.append(f"[{name}] Duplicate 'name': '{card_name}'")
            seen_names.add(card_name)

        # 2. Check type and whitelist
        ctype = card.get("type", "")
        if ctype not in valid_types:
            errors.append(f"[{name}] Invalid type: '{ctype}'")
            continue  # Cannot check type-specific whitelist if type is invalid

        allowed_keys = allowed_keys_by_type[ctype]
        for key in card.keys():
            if key not in allowed_keys:
                errors.append(f"[{name}] Key '{key}' is not allowed for type '{ctype}'")

        # 3. Check timings
        timings = card.get("usage_timing", [])
        if not isinstance(timings, list):
            errors.append(f"[{name}] 'usage_timing' must be a list")
        else:
            for t in timings:
                if t not in valid_phases:
                    errors.append(f"[{name}] Invalid usage_timing phase: '{t}'")

        # 4. Check base type-specific requirements & ranges
        # price
        if "price" in card:
            price = card["price"]
            if not isinstance(price, int) or price < 0:
                errors.append(f"[{name}] 'price' must be a non-negative integer, got {repr(price)}")

        # drop_rate
        if "drop_rate" in card:
            drop_rate = card["drop_rate"]
            if not isinstance(drop_rate, int) or drop_rate < 0:
                errors.append(f"[{name}] 'drop_rate' must be a non-negative integer, got {repr(drop_rate)}")

        # element
        if "element" in card:
            if card["element"] not in valid_elements:
                errors.append(f"[{name}] Invalid element: '{card['element']}'")

        # attack_power
        if "attack_power" in card:
            ap = card["attack_power"]
            if not isinstance(ap, int) or ap < 0:
                errors.append(f"[{name}] 'attack_power' must be a non-negative integer, got {repr(ap)}")

        # defense_power
        if "defense_power" in card:
            dp = card["defense_power"]
            if not isinstance(dp, int) or dp < 0:
                errors.append(f"[{name}] 'defense_power' must be a non-negative integer, got {repr(dp)}")

        # mp_cost
        if "mp_cost" in card:
            mp = card["mp_cost"]
            if not isinstance(mp, int) or mp < 0:
                errors.append(f"[{name}] 'mp_cost' must be a non-negative integer, got {repr(mp)}")
            if ctype != "miracle":
                errors.append(f"[{name}] 'mp_cost' is only allowed for type 'miracle'")

        # accuracy
        if "accuracy" in card:
            acc = card["accuracy"]
            if not isinstance(acc, int) or not (0 <= acc <= 100):
                errors.append(f"[{name}] 'accuracy' must be an integer between 0 and 100, got {repr(acc)}")

        # hit_curse
        if "hit_curse" in card:
            if card["hit_curse"] not in valid_hit_curses:
                errors.append(f"[{name}] Invalid hit_curse: '{card['hit_curse']}'")

        # reaction_type
        if "reaction_type" in card:
            if card["reaction_type"] not in valid_reactions:
                errors.append(f"[{name}] Invalid reaction_type: '{card['reaction_type']}'")
            # Must have defensive timings
            if not any(t in timings for t in ("atk_defence_phase", "miracle_defence_phase")):
                errors.append(
                    f"[{name}] Card has 'reaction_type' but does not allow defensive phases in usage_timing"
                )

        # 5. Type/timing-based conditional checks
        if ctype == "weapon" or "main_atk_phase" in timings:
            if "attack_power" not in card:
                errors.append(f"[{name}] Type/Timing indicates attack, but missing 'attack_power'")

        if ctype == "weapon" and "atk_plus_phase" in timings:
            if "main_atk_phase" not in timings:
                errors.append(f"[{name}] Weapon has 'atk_plus_phase' but missing 'main_atk_phase'")

        if ctype == "defense" and "main_atk_phase" in timings:
            errors.append(f"[{name}] Defense items cannot have 'main_atk_phase'")

        if ctype == "defense" and "reaction_type" not in card:
            # Shields must have defense_power (Rings don't have defense_power)
            if "指輪" not in name and "defense_power" not in card:
                errors.append(f"[{name}] Non-ring defense card requires 'defense_power' or 'reaction_type'")

        if ctype == "miracle":
            if "mp_cost" not in card and "miracle_plus_phase" not in timings:
                errors.append(f"[{name}] Type miracle missing 'mp_cost'")

        # 6. Check group attack and accuracy consistency
        is_group = card.get("is_group_attack", False)
        if not isinstance(is_group, bool):
            errors.append(f"[{name}] 'is_group_attack' must be a boolean")

        accuracy = card.get("accuracy", 100)
        if is_group:
            if "accuracy" not in card:
                errors.append(f"[{name}] Group attack card must specify 'accuracy'")
            # Under guardian_phase, accuracy doesn't have to be < 100
            elif "guardian_phase" not in timings:
                if not (0 < accuracy < 100):
                    errors.append(
                        f"[{name}] Group attack must have accuracy between 0 and 100 (accuracy was {accuracy})"
                    )
        else:
            if ctype in {"weapon", "miracle"} and "accuracy" in card and accuracy != 100:
                errors.append(
                    f"[{name}] Single target weapon/miracle attack must have accuracy = 100 (accuracy was {accuracy})"
                )

    # 7. Check ID sequentiality: IDs should be 0, 1, ..., len(cards)-1
    num_cards = len(cards)
    expected_ids = set(range(num_cards))
    if seen_ids != expected_ids:
        missing_ids = sorted(list(expected_ids - seen_ids))
        extra_ids = sorted(list(seen_ids - expected_ids))
        if missing_ids:
            errors.append(f"Card IDs are not sequential. Missing IDs: {missing_ids}")
        if extra_ids:
            errors.append(f"Card IDs contain out-of-range values: {extra_ids}")

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
