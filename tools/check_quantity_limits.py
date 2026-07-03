#!/usr/bin/env python3
"""
Check estimate line item quantities against carrier-approved maximums.

This tool validates quantities don't exceed carrier limits and flags violations.

Usage:
    python check_quantity_limits.py <estimate_json> <guidelines_json> [--output <output_path>]
"""

import sys
import json
import os
import re
from pathlib import Path


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_coat_count(description):
    """Extract number of coats from description text."""
    desc_lower = description.lower()

    # Look for patterns like "one coat", "1 coat", "two coats", "2 coats"
    patterns = [
        r'(\d+)\s*coats?',
        r'(one|two|three|four)\s*coats?'
    ]

    word_to_num = {'one': 1, 'two': 2, 'three': 3, 'four': 4}

    for pattern in patterns:
        match = re.search(pattern, desc_lower)
        if match:
            count_str = match.group(1)
            if count_str.isdigit():
                return int(count_str)
            elif count_str in word_to_num:
                return word_to_num[count_str]

    return None


def check_item_against_quantity_rules(line_item, quantity_rules):
    """
    Check if a line item exceeds quantity limits.

    Returns: (within_limits, matched_rule, excess_amount)
    """
    description = line_item['description'].lower()
    quantity = line_item.get('quantity', 0)
    unit = line_item.get('unit', '').lower()

    for rule in quantity_rules:
        # Check if description matches rule pattern
        pattern_match = False
        for pattern in rule['item_pattern']:
            if pattern.lower() in description:
                pattern_match = True
                break

        if not pattern_match:
            continue

        # For paint/coating rules, check coat count in description
        if 'coat' in rule.get('unit', '').lower():
            coat_count = extract_coat_count(description)
            if coat_count and coat_count > rule.get('max_quantity', float('inf')):
                excess = coat_count - rule['max_quantity']
                return (False, rule, excess)

        # For quantity-based rules
        elif 'max_quantity' in rule:
            if quantity > rule['max_quantity']:
                excess = quantity - rule['max_quantity']
                return (False, rule, excess)

        # For height-based rules (drywall)
        elif 'max_height' in rule:
            # Extract height from description (e.g., "up to 4' tall")
            height_match = re.search(r"up to (\d+)'", description)
            if height_match:
                height = int(height_match.group(1))
                if height > rule['max_height']:
                    excess = height - rule['max_height']
                    return (False, rule, excess)

    return (True, None, 0)


def check_quantity_limits(estimate_json, guidelines_json):
    """
    Check all line items against quantity limit rules.

    Returns list of issues found.
    """
    issues = []

    line_items = estimate_json.get('line_items', [])
    quantity_rules = guidelines_json.get('quantity_limits', [])
    carrier = guidelines_json.get('carrier', 'Unknown Carrier')

    print(f"Checking {len(line_items)} line items against {len(quantity_rules)} quantity limit rules...")
    print(f"Carrier: {carrier}\n")

    for item in line_items:
        within_limits, matched_rule, excess = check_item_against_quantity_rules(
            item, quantity_rules
        )

        if not within_limits:
            # Determine recommendation
            if 'coat' in matched_rule.get('unit', '').lower():
                recommendation = f"Reduce to {matched_rule['max_quantity']} coat(s) maximum"
            else:
                recommendation = f"Reduce quantity to {matched_rule['max_quantity']} {matched_rule.get('unit', 'units')}"

            if matched_rule.get('exceptions'):
                recommendation += f" or justify with: {matched_rule['exceptions']}"

            issue = {
                "issue_type": "quantity_limit_exceeded",
                "line_item": item.get('line_number', item.get('item_number', 0)),
                "description": item['description'],
                "category": item.get('category'),
                "quantity": item['quantity'],
                "unit": item.get('unit'),
                "total": item['total'],
                "matched_rule": matched_rule['rule_id'],
                "max_allowed": matched_rule.get('max_quantity') or matched_rule.get('max_height'),
                "excess": excess,
                "reason": matched_rule['description'],
                "recommendation": recommendation,
                "guideline_reference": matched_rule.get('guideline_reference', 'Not specified')
            }

            issues.append(issue)

            print(f"[X] Issue found: Line {item.get('line_number', item.get('item_number', 0))}")
            print(f"  Description: {item['description']}")
            print(f"  Excess: {excess} {matched_rule.get('unit', 'units')}")
            print(f"  Reason: {matched_rule['description']}")
            print(f"  Recommendation: {recommendation}\n")

    if not issues:
        print("[OK] No quantity limit violations found - all quantities within limits\n")

    return issues


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python check_quantity_limits.py <estimate_json> <guidelines_json> [--output <output_path>]")
        sys.exit(1)

    estimate_path = sys.argv[1]
    guidelines_path = sys.argv[2]

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

    if not os.path.exists(guidelines_path):
        print(f"Error: Guidelines file not found: {guidelines_path}")
        sys.exit(1)

    print(f"Loading estimate: {estimate_path}")
    print(f"Loading guidelines: {guidelines_path}\n")

    try:
        # Load JSON files
        estimate_json = load_json(estimate_path)
        guidelines_json = load_json(guidelines_path)

        # Run validation
        issues = check_quantity_limits(estimate_json, guidelines_json)

        # Determine output path
        if not output_path:
            estimate_id = estimate_json.get('estimate_id', 'unknown')
            output_dir = Path('.tmp/issues')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'quantities_{estimate_id}.json'

        # Write output
        output_data = {
            "estimate_id": estimate_json.get('estimate_id'),
            "carrier": guidelines_json.get('carrier'),
            "check_type": "quantity_limits",
            "issues_found": len(issues),
            "issues": issues
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"Validation complete!")
        print(f"Issues found: {len(issues)}")
        print(f"Output saved to: {output_path}")

        # Print summary
        if issues:
            total_amount = sum(issue['total'] for issue in issues)
            print(f"\nTotal amount flagged: ${total_amount:.2f}")

        return output_data

    except Exception as e:
        print(f"Error during validation: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
