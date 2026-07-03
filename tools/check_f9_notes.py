#!/usr/bin/env python3
"""
Check line items for F9 note requirements per carrier guidelines.

This tool identifies line items that require F9 notes (line item notes) and
provides recommended note text for each flagged item.

Usage:
    python check_f9_notes.py <estimate_json> <carrier_rules_json> [--output <output_path>]
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


def check_f9_requirements(line_item, f9_rules, estimate_id):
    """Check if a line item requires an F9 note."""
    f9_flags = []

    description = line_item['description']
    category = line_item.get('category', 'OTHER')

    for rule in f9_rules:
        rule_id = rule['rule_id']
        item_patterns = rule.get('item_pattern', [])
        rule_categories = rule.get('categories', [])
        applies_to = rule.get('applies_to', None)

        # Check if rule applies to this category
        if rule_categories and category not in rule_categories:
            continue

        # Check for pattern matches
        match_found = False
        for pattern in item_patterns:
            # Fuzzy match for flexibility with OCR errors
            similarity = fuzz.partial_ratio(pattern.lower(), description.lower())
            if similarity > 90:  # 80% similarity threshold
                match_found = True
                break

        if match_found:
            f9_flag = {
                'line_item': line_item['line_number'],
                'description': description,
                'category': category,
                'total': line_item['total'],
                'rule_id': rule_id,
                'requirement': rule['description'],
                'reason': rule['reason'],
                'required_info': rule.get('required_info', 'Provide supporting documentation'),
                'recommended_note': rule.get('recommended_note', f'F9 note required. {rule["reason"]}'),
                'guideline_reference': rule.get('guideline_reference', 'N/A')
            }

            f9_flags.append(f9_flag)

    return f9_flags


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python check_f9_notes.py <estimate_json> <carrier_rules_json> [--output <output_path>]")
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

    print(f"Checking F9 note requirements...")
    print(f"Estimate: {estimate_path}")
    print(f"Rules: {rules_path}\n")

    try:
        # Load data
        estimate_json = load_json(estimate_path)
        rules_json = load_json(rules_path)

        estimate_id = estimate_json.get('estimate_id', 'unknown')
        carrier = rules_json.get('carrier', 'Unknown')
        line_items = estimate_json.get('line_items', [])
        f9_rules = rules_json.get('f9_note_requirements', [])

        print(f"Carrier: {carrier}")
        print(f"Line items to check: {len(line_items)}")
        print(f"F9 rules to apply: {len(f9_rules)}\n")

        # Check each line item
        all_f9_flags = []
        for line_item in line_items:
            f9_flags = check_f9_requirements(line_item, f9_rules, estimate_id)
            all_f9_flags.extend(f9_flags)

        # Create output structure
        output_data = {
            'estimate_id': estimate_id,
            'carrier': carrier,
            'check_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'f9_notes_required': len(all_f9_flags),
            'flags': all_f9_flags
        }

        # Determine output path
        if not output_path:
            output_dir = Path('.tmp/issues')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'f9_notes_{estimate_id}.json'

        # Save results
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        # Print summary
        print(f"F9 Note Check Complete!")
        print(f"[OK] F9 notes required: {len(all_f9_flags)}")
        print(f"Output saved to: {output_path}\n")

        if all_f9_flags:
            print("Items requiring F9 notes:")
            for flag in all_f9_flags:
                print(f"  - Line #{flag['line_item']}: {flag['description']}")
                print(f"    Requirement: {flag['requirement']}")
                print()

        return output_path

    except Exception as e:
        print(f"Error checking F9 notes: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
