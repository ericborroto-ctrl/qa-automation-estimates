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

        # Check if rule applies to this category
        if rule_category and category != rule_category:
            continue

        # Check for pattern matches
        match_found = False
        matched_pattern = None
        for pattern in item_patterns:
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
