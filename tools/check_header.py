#!/usr/bin/env python3
"""
Check that the estimate has the Paul Davis company header.

Every estimate must show the Paul Davis letterhead/header (company name,
address, license info) - this is a Paul Davis QA requirement, not tied to
any specific carrier's guidelines, so it applies regardless of carrier.

Usage:
    python check_header.py <estimate_json> <guidelines_json> [--output <output_path>]
"""

import sys
import json
import os
from pathlib import Path


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_header(estimate_json):
    """Check whether the estimate has the Paul Davis header. Returns list of issues (0 or 1)."""
    has_header = estimate_json.get('metadata', {}).get('has_paul_davis_header', False)

    if has_header:
        print("[OK] Paul Davis header found\n")
        return []

    issue = {
        "issue_type": "missing_header",
        "line_item": None,
        "description": "Missing Paul Davis company header",
        "category": "Document",
        "total": 0,
        "confidence": 100,
        "matched_rule": "GEN_DOC_HEADER",
        "reason": "Every Paul Davis estimate must show the Paul Davis company header/letterhead.",
        "recommendation": "Add the Paul Davis company header to this estimate before submitting.",
        "action": "add",
        "guideline_reference": "Paul Davis QA Standard"
    }

    print("[X] Issue found: Paul Davis header not found on this estimate\n")

    return [issue]


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python check_header.py <estimate_json> <guidelines_json> [--output <output_path>]")
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
        estimate_json = load_json(estimate_path)
        guidelines_json = load_json(guidelines_path)

        issues = check_header(estimate_json)

        # Determine output path
        if not output_path:
            estimate_id = estimate_json.get('estimate_id', 'unknown')
            output_dir = Path('.tmp/issues')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'header_{estimate_id}.json'

        output_data = {
            "estimate_id": estimate_json.get('estimate_id'),
            "carrier": guidelines_json.get('carrier'),
            "check_type": "header",
            "issues_found": len(issues),
            "issues": issues
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"Validation complete!")
        print(f"Issues found: {len(issues)}")
        print(f"Output saved to: {output_path}")

        return output_path

    except Exception as e:
        print(f"Error checking header: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
