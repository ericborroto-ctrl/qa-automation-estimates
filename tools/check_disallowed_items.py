#!/usr/bin/env python3
"""
Check estimate line items against carrier's disallowed materials list.

This tool matches line item descriptions against disallowed item patterns
using fuzzy matching and flags violations with recommendations.

Usage:
    python check_disallowed_items.py <estimate_json> <guidelines_json> [--output <output_path>]
"""

import sys
import json
import os
from pathlib import Path
from fuzzywuzzy import fuzz


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_item_against_rules(line_item, disallowed_rules, confidence_threshold=95):
    """
    Check if a line item matches any disallowed item rules.

    Returns: (is_allowed, matched_rule, confidence_score)
    """
    description = line_item['description'].lower()
    category = line_item.get('category', '').upper() if line_item.get('category') else None

    best_match = None
    best_confidence = 0

    for rule in disallowed_rules:
        # Category exact match increases confidence
        category_match = False
        if rule.get('category') and category:
            if rule['category'].upper() == category:
                category_match = True

        # Check each pattern in the rule
        for pattern in rule['item_pattern']:
            pattern_lower = pattern.lower()

            # Exact substring match (high confidence)
            if pattern_lower in description:
                confidence = 95 if category_match else 85
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = rule

            # Fuzzy match (medium confidence)
            else:
                similarity = fuzz.partial_ratio(pattern_lower, description)
                if similarity > confidence_threshold:
                    confidence = similarity * 0.9  # Scale down slightly
                    if category_match:
                        confidence = min(confidence + 10, 100)  # Boost for category match

                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = rule

    if best_match:
        return (False, best_match, best_confidence)
    else:
        return (True, None, 100)


def check_disallowed_items(estimate_json, guidelines_json, confidence_threshold=95):
    """
    Check all line items against disallowed items rules.

    Returns list of issues found.
    """
    issues = []

    line_items = estimate_json.get('line_items', [])
    disallowed_rules = guidelines_json.get('disallowed_items', [])
    carrier = guidelines_json.get('carrier', 'Unknown Carrier')

    print(f"Checking {len(line_items)} line items against {len(disallowed_rules)} disallowed item rules...")
    print(f"Carrier: {carrier}")
    print(f"Confidence threshold: {confidence_threshold}%\n")

    for item in line_items:
        is_allowed, matched_rule, confidence = check_item_against_rules(
            item, disallowed_rules, confidence_threshold
        )

        if not is_allowed:
            # Determine recommendation based on confidence
            if confidence >= 90:
                recommendation = "Remove line item - clear policy violation"
                action = "remove"
            elif confidence >= 75:
                recommendation = "Review with adjuster - likely not covered"
                action = "review"
            else:
                recommendation = "Flag for manual review - possible policy issue"
                action = "flag"

            issue = {
                "issue_type": "disallowed_item",
                "line_item": item.get('line_number', item.get('item_number', 0)),
                "description": item['description'],
                "category": item.get('category'),
                "quantity": item['quantity'],
                "unit": item.get('unit'),
                "total": item['total'],
                "confidence": round(confidence, 1),
                "matched_rule": matched_rule['rule_id'],
                "reason": matched_rule['reason'],
                "recommendation": recommendation,
                "action": action,
                "guideline_reference": matched_rule.get('guideline_reference', 'Not specified')
            }

            issues.append(issue)

            print(f"[X] Issue found: Line {item.get('line_number', item.get('item_number', 0))}")
            print(f"  Description: {item['description']}")
            print(f"  Confidence: {confidence:.1f}%")
            print(f"  Reason: {matched_rule['reason']}")
            print(f"  Action: {action}\n")

    if not issues:
        print("[OK] No disallowed items found - all line items appear compliant\n")

    return issues


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python check_disallowed_items.py <estimate_json> <guidelines_json> [--output <output_path>]")
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
        issues = check_disallowed_items(estimate_json, guidelines_json)

        # Determine output path
        if not output_path:
            estimate_id = estimate_json.get('estimate_id', 'unknown')
            output_dir = Path('.tmp/issues')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'disallowed_{estimate_id}.json'

        # Write output
        output_data = {
            "estimate_id": estimate_json.get('estimate_id'),
            "carrier": guidelines_json.get('carrier'),
            "check_type": "disallowed_items",
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

            actions = {}
            for issue in issues:
                action = issue['action']
                actions[action] = actions.get(action, 0) + 1

            print("\nActions breakdown:")
            for action, count in actions.items():
                print(f"  {action}: {count}")

        return output_data

    except Exception as e:
        print(f"Error during validation: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
