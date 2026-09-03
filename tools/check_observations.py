#!/usr/bin/env python3
"""
Check line items for observations worth noting (non-violations).

This tool identifies line items that don't violate guidelines but may be worth
reviewing or noting for the estimator's attention.

Usage:
    python check_observations.py <estimate_json> <carrier_rules_json> [--output <output_path>]
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from fuzzywuzzy import fuzz


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_room_index(line_items):
    """Group line item descriptions (lowercased) by the room they belong to."""
    room_index = {}
    for item in line_items:
        room = item.get('room', 'Unknown')
        room_index.setdefault(room, []).append(item)
    return room_index


def has_suppression_context(line_item, room_index, suppression_rule):
    """Check if another item in the same room justifies skipping this observation.

    E.g. a "paint undamaged trim" observation shouldn't fire if the same room
    also has a door/frame/window R&R or replacement line item - that's the
    context that makes painting the trim expected, not questionable.
    """
    room = line_item.get('room', 'Unknown')
    if room == 'Unknown':
        return False

    component_keywords = suppression_rule.get('component_keywords', [])
    action_keywords = suppression_rule.get('action_keywords', [])

    for other in room_index.get(room, []):
        if other is line_item:
            continue
        other_desc = other['description'].lower()
        if any(c in other_desc for c in component_keywords) and \
           any(a in other_desc for a in action_keywords):
            return True

    return False


def has_required_context(line_item, room_index, requirement_rule):
    """Check if another item in the same room justifies this item's presence.

    E.g. CLN FINALR (extra construction cleanup) is only appropriate where the
    room actually has dust-generating work (drywall, demo, texture) - if no
    other item in the room matches, the room lacks the context that would
    justify it. Room 'Unknown' returns True (don't flag) since absence can't
    be confirmed without knowing the room.
    """
    room = line_item.get('room', 'Unknown')
    if room == 'Unknown':
        return True

    component_keywords = requirement_rule.get('component_keywords', [])

    for other in room_index.get(room, []):
        if other is line_item:
            continue
        other_desc = other['description'].lower()
        if any(c in other_desc for c in component_keywords):
            return True

    return False


def has_duplicate_context(line_item, room_index, duplicate_rule):
    """Check if another item in the same room's own description already
    covers this item's scope - e.g. a separate taping charge (DRY PATCHJ)
    when the room's base drywall item already says "hung, taped, ready for
    texture" in its own description.
    """
    room = line_item.get('room', 'Unknown')
    if room == 'Unknown':
        return False

    substrings = duplicate_rule.get('other_item_description_contains', [])

    for other in room_index.get(room, []):
        if other is line_item:
            continue
        other_desc = other['description'].lower()
        if any(s in other_desc for s in substrings):
            return True

    return False


# Carrier-agnostic structural checks - these apply to every estimate
# regardless of carrier (current or future), so they're built in here rather
# than sourced from a carrier's rules JSON, and aren't tied to a specific
# guideline page. They inspect a whole room (its name and/or its full set of
# line items) rather than a single item's description, unlike the
# pattern-matched rules above.
#
# 'match_on' picks how a rule decides whether a room needs flagging:
#   'always'    - flag every room unconditionally. Used for checks the tool
#                 can't actually verify from extracted data (e.g. whether a
#                 door/window or a sketch block was actually drawn) - it's a
#                 standing reminder, not a real check.
#   'room_name' - flag the room whenever its name contains any of
#                 `room_name_keywords`, regardless of its line items. Same
#                 "can't verify, so remind" reasoning as 'always', just
#                 scoped to certain room types.
# 'exclude_room_name_keywords' (optional, any match_on) - skip the room if
# its name contains any of these, checked before match_on.
STRUCTURAL_ROOM_RULES = [
    {
        'rule_id': 'GEN_ROOM_DOORWINDOW',
        'match_on': 'always',
        'exclude_room_name_keywords': ['kitchen'],
        'description': 'Verify this room has a doorway/window in the sketch',
        'reason': "The tool can't verify door/window presence from the sketch - a line-item check isn't a "
                  "reliable stand-in, since a room can have a real door/window with no replacement line item.",
        'recommendation': "Make sure this room has a doorway in the sketch if it has one, and/or a window.",
        'guideline_reference': 'Paul Davis QA Standard',
    },
    {
        'rule_id': 'GEN_ROOM_SKETCH_BLOCKS',
        'match_on': 'room_name',
        'room_name_keywords': ['kitchen', 'bath'],
        'description': 'Kitchen/bathroom rooms need blocks in the sketch for accurate square footage',
        'reason': 'Kitchens and bathrooms typically have cabinets, islands, tubs, or showers that should be '
                   'blocked out in the sketch so they get deducted from the room\'s square footage.',
        'recommendation': 'Verify blocks were used in the sketch for this room to correctly deduct square footage.',
        'guideline_reference': 'Paul Davis QA Standard',
    },
    {
        'rule_id': 'GEN_ROOM_NO_LITERAL_GENERAL',
        'match_on': 'room_name',
        'room_name_keywords': ['general'],
        'room_name_exact_match': True,
        'description': "A literal 'General' room shouldn't exist on the sketch",
        'reason': "General-category line items (Emergency Service Call, equipment setup/monitoring, content "
                  "manipulation, PPE, HEPA filters, debris haul, etc.) that apply to the whole job belong in a "
                  "'General' category grouping, but should not be placed in an actual room drawn on the sketch.",
        'recommendation': "Verify 'General' isn't an actual room on the sketch - general-category items should "
                          "be grouped without a corresponding sketched room.",
        'guideline_reference': 'Paul Davis QA Standard',
    },
]


def check_structural_room_observations(room_index):
    """Room-level checks that don't hinge on any single line item's pattern -
    standing reminders about the sketch (door/window presence, kitchen/
    bathroom blocks) that the tool can't verify from extracted line items."""
    observations = []

    for room, items in room_index.items():
        if room == 'Unknown' or not items:
            continue

        room_lower = room.lower().strip()

        for rule in STRUCTURAL_ROOM_RULES:
            exclude_keywords = rule.get('exclude_room_name_keywords', [])
            if any(kw in room_lower for kw in exclude_keywords):
                continue

            if rule['match_on'] == 'room_name':
                if rule.get('room_name_exact_match'):
                    if room_lower not in rule['room_name_keywords']:
                        continue
                elif not any(kw in room_lower for kw in rule['room_name_keywords']):
                    continue
            elif rule['match_on'] != 'always':
                continue

            anchor_item = items[0]
            observations.append({
                'line_item': anchor_item['line_number'],
                'description': f"Room: {room}",
                'category': anchor_item.get('category', 'OTHER'),
                'total': 0,
                'rule_id': rule['rule_id'],
                'observation_type': rule['description'],
                'severity': 'info',
                'reason': rule['reason'],
                'recommendation': rule['recommendation'],
                'guideline_reference': rule['guideline_reference'],
                'matched_pattern': None,
            })

    return observations


def check_estimate_level_observations(line_items, observation_rules):
    """Checks that need to see every line item in the estimate at once,
    not just one room - e.g. flagging more than one 'minimum charge' item
    for the same trade/category anywhere in the estimate. This is a
    genuinely different shape than the room-scoped duplicate_if_room_contains
    mechanism, which only ever compares items within a single room."""
    observations = []

    for rule in observation_rules:
        if not rule.get('duplicate_across_estimate_by_category'):
            continue

        item_patterns = rule.get('item_pattern', [])
        matches_by_category = {}

        for item in line_items:
            description = item['description'].lower()
            is_match = any(
                fuzz.partial_ratio(pattern.lower(), description) > 75
                for pattern in item_patterns
            )
            if is_match:
                category = item.get('category') or 'OTHER'
                matches_by_category.setdefault(category, []).append(item)

        for category, matched_items in matches_by_category.items():
            if len(matched_items) <= 1:
                continue

            # First occurrence is the legitimate one; flag every duplicate
            # after it for that same trade/category.
            for duplicate_item in matched_items[1:]:
                observations.append({
                    'line_item': duplicate_item['line_number'],
                    'description': duplicate_item['description'],
                    'category': duplicate_item.get('category', 'OTHER'),
                    'total': duplicate_item.get('total', 0),
                    'rule_id': rule['rule_id'],
                    'observation_type': rule['description'],
                    'severity': rule.get('severity', 'info'),
                    'reason': rule['reason'],
                    'recommendation': rule['recommendation'],
                    'guideline_reference': rule.get('guideline_reference', 'N/A'),
                    'matched_pattern': None,
                })

    return observations


def check_observations(line_item, observation_rules, estimate_id, room_index=None):
    """Check if a line item has observations worth noting."""
    observations = []

    description = line_item['description']
    category = line_item.get('category', 'OTHER')

    for rule in observation_rules:
        rule_id = rule['rule_id']
        item_patterns = rule.get('item_pattern', [])
        rule_category = rule.get('category', None)
        severity = rule.get('severity', 'info')

        # Estimate-wide duplicate rules are only evaluated by
        # check_estimate_level_observations(), which sees every line item
        # at once - evaluating them here too would double-flag matches.
        if rule.get('duplicate_across_estimate_by_category'):
            continue

        # Check if rule applies to this category
        if rule_category and category != rule_category:
            continue

        # Check for pattern matches
        match_found = False
        matched_pattern = None
        for pattern in item_patterns:
            if rule.get('exact_match'):
                # Fuzzy matching is unsafe when a pattern differs from its
                # opposite meaning by nearly nothing textually - e.g. "paint
                # (1 coat)" vs "paint (2 coats)" score ~86% similar under
                # fuzz.partial_ratio despite being opposite scope amounts.
                # Rules like that need a literal substring match instead.
                if pattern.lower() in description.lower():
                    match_found = True
                    matched_pattern = pattern
                    break
            else:
                # Fuzzy match for flexibility with OCR errors
                similarity = fuzz.partial_ratio(pattern.lower(), description.lower())
                if similarity > 75:  # 75% similarity threshold for observations
                    match_found = True
                    matched_pattern = pattern
                    break

        suppression_rule = rule.get('suppress_if_room_contains')
        if match_found and suppression_rule and room_index is not None:
            if has_suppression_context(line_item, room_index, suppression_rule):
                match_found = False

        requirement_rule = rule.get('flag_if_room_lacks')
        if match_found and requirement_rule and room_index is not None:
            if has_required_context(line_item, room_index, requirement_rule):
                match_found = False

        # Inverse of flag_if_room_lacks: the trigger item is only a problem
        # when the room ALSO has some other context - e.g. an under-scoped
        # single-coat paint item is only wrong if the room has new/damaged
        # drywall work requiring the full sealer + two coats.
        only_if_present_rule = rule.get('flag_only_if_room_has')
        if match_found and only_if_present_rule and room_index is not None:
            if not has_required_context(line_item, room_index, only_if_present_rule):
                match_found = False

        duplicate_rule = rule.get('duplicate_if_room_contains')
        if match_found and duplicate_rule and room_index is not None:
            if not has_duplicate_context(line_item, room_index, duplicate_rule):
                match_found = False

        # Only fires when the item's own extracted quantity meets a minimum
        # and/or stays under a maximum - e.g. "ITEL required on flooring
        # replacements of 144 SF or more" (min) or "damage of 100 SF or less
        # should be referred to Nativo" (max). Assumes the rule's
        # item_pattern already scopes this to items where quantity is a
        # meaningful SF/unit measure (e.g. flooring materials).
        quantity_threshold = rule.get('quantity_threshold')
        if match_found and quantity_threshold:
            item_quantity = line_item.get('quantity', 0)
            if item_quantity < quantity_threshold.get('min', 0):
                match_found = False
            if match_found and 'max' in quantity_threshold and item_quantity > quantity_threshold['max']:
                match_found = False

        # Same idea as quantity_threshold, but gated on the item's dollar
        # total instead - e.g. "tree removal subcontractor bids over $7,500
        # need adjuster pre-approval".
        dollar_threshold = rule.get('dollar_threshold')
        if match_found and dollar_threshold:
            item_total = line_item.get('total', 0)
            if item_total < dollar_threshold.get('min', 0):
                match_found = False
            if match_found and 'max' in dollar_threshold and item_total > dollar_threshold['max']:
                match_found = False

        if match_found:
            observation = {
                'line_item': line_item['line_number'],
                'description': description,
                'category': category,
                'total': line_item['total'],
                'rule_id': rule_id,
                'observation_type': rule['description'],
                'severity': severity,
                'reason': rule['reason'],
                'recommendation': rule['recommendation'],
                'guideline_reference': rule.get('guideline_reference', 'N/A'),
                'matched_pattern': matched_pattern
            }

            observations.append(observation)

    return observations


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python check_observations.py <estimate_json> <carrier_rules_json> [--output <output_path>]")
        sys.exit(1)

    estimate_path = sys.argv[1]
    rules_path = sys.argv[2]

    # Check if output path is specified
    output_path = None
    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output')
        if output_idx + 1 < len(sys.argv):
            output_path = sys.argv[output_idx + 1]

    # Validate input files
    if not os.path.exists(estimate_path):
        print(f"Error: Estimate file not found: {estimate_path}")
        sys.exit(1)

    if not os.path.exists(rules_path):
        print(f"Error: Rules file not found: {rules_path}")
        sys.exit(1)

    print(f"Checking for observations...")
    print(f"Estimate: {estimate_path}")
    print(f"Rules: {rules_path}\n")

    try:
        # Load data
        estimate_json = load_json(estimate_path)
        rules_json = load_json(rules_path)

        estimate_id = estimate_json.get('estimate_id', 'unknown')
        carrier = rules_json.get('carrier', 'Unknown')
        line_items = estimate_json.get('line_items', [])
        observation_rules = rules_json.get('observations', [])

        print(f"Carrier: {carrier}")
        print(f"Line items to check: {len(line_items)}")
        print(f"Observation rules to apply: {len(observation_rules)}\n")

        # Check each line item
        room_index = build_room_index(line_items)
        all_observations = []
        for line_item in line_items:
            observations = check_observations(line_item, observation_rules, estimate_id, room_index)
            all_observations.extend(observations)

        # Carrier-agnostic room-level checks (door/window presence, etc.) -
        # always run, independent of which carrier's rules were loaded.
        all_observations.extend(check_structural_room_observations(room_index))

        # Estimate-wide checks (e.g. duplicate minimum charges per trade)
        # that need to see all line items at once, not just one room.
        all_observations.extend(check_estimate_level_observations(line_items, observation_rules))

        # Create output structure
        output_data = {
            'estimate_id': estimate_id,
            'carrier': carrier,
            'check_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'observations_found': len(all_observations),
            'observations': all_observations
        }

        # Determine output path
        if not output_path:
            output_dir = Path('.tmp/issues')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'observations_{estimate_id}.json'

        # Save results
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        # Print summary
        print(f"Observations Check Complete!")
        print(f"[OK] Observations found: {len(all_observations)}")
        print(f"Output saved to: {output_path}\n")

        if all_observations:
            print("Items with observations:")
            for obs in all_observations:
                print(f"  - Line #{obs['line_item']}: {obs['description']}")
                print(f"    Note: {obs['observation_type']}")
                print()

        return output_path

    except Exception as e:
        print(f"Error checking observations: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
