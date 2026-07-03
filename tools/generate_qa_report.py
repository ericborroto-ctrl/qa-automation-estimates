#!/usr/bin/env python3
"""
Generate comprehensive QA report from validation results.

This tool consolidates all validation issues into a readable markdown report
with recommendations and cost impact analysis.

Usage:
    python generate_qa_report.py <estimate_json> <issues_dir> [--output <output_path>]
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_issues(issues_dir, estimate_id):
    """Load all issue JSON files for an estimate."""
    issues_data = {
        'disallowed': None,
        'quantities': None,
        'depreciation': None
    }

    issues_path = Path(issues_dir)
    if not issues_path.exists():
        return issues_data

    # Load disallowed items
    disallowed_file = issues_path / f'disallowed_{estimate_id}.json'
    if disallowed_file.exists():
        issues_data['disallowed'] = load_json(disallowed_file)

    # Load quantity limits
    quantities_file = issues_path / f'quantities_{estimate_id}.json'
    if quantities_file.exists():
        issues_data['quantities'] = load_json(quantities_file)

    # Load depreciation (future)
    depreciation_file = issues_path / f'depreciation_{estimate_id}.json'
    if depreciation_file.exists():
        issues_data['depreciation'] = load_json(depreciation_file)

    return issues_data


def generate_markdown_report(estimate_json, issues_data):
    """Generate markdown report from estimate and issues data."""
    report = []

    # Header
    estimate_id = estimate_json.get('estimate_id', 'Unknown')
    client = estimate_json.get('metadata', {}).get('client', 'Unknown')
    date = estimate_json.get('metadata', {}).get('date', 'Unknown')

    report.append(f"# QA Review Report: {estimate_id}")
    report.append("")
    report.append(f"**Client:** {client}")
    report.append(f"**Estimate Date:** {date}")
    report.append(f"**Review Date:** {datetime.now().strftime('%Y-%m-%d')}")
    report.append("")

    # Get carrier from first issues file
    carrier = "Unknown"
    for issue_type, data in issues_data.items():
        if data and 'carrier' in data:
            carrier = data['carrier']
            break

    report.append(f"**Carrier:** {carrier}")
    report.append("")

    # Summary section
    report.append("## Summary")
    report.append("")

    # Calculate totals
    total_issues = 0
    disallowed_count = 0
    quantities_count = 0
    depreciation_count = 0

    if issues_data['disallowed']:
        disallowed_count = issues_data['disallowed'].get('issues_found', 0)
        total_issues += disallowed_count

    if issues_data['quantities']:
        quantities_count = issues_data['quantities'].get('issues_found', 0)
        total_issues += quantities_count

    if issues_data['depreciation']:
        depreciation_count = issues_data['depreciation'].get('issues_found', 0)
        total_issues += depreciation_count

    # Estimate totals
    summary = estimate_json.get('summary', {})
    line_item_total = summary.get('line_item_total', 0)
    overhead = summary.get('overhead', 0)
    profit = summary.get('profit', 0)
    rcv_total = line_item_total + overhead + profit

    report.append(f"- **Total Issues Found:** {total_issues}")
    report.append(f"- **Disallowed Items:** {disallowed_count}")
    report.append(f"- **Quantity Limit Violations:** {quantities_count}")
    report.append(f"- **Depreciation Errors:** {depreciation_count}")
    report.append("")
    report.append(f"- **Original Estimate Total:** ${rcv_total:,.2f}")
    report.append("")

    # Issues detail sections
    if total_issues == 0:
        report.append("## Results")
        report.append("")
        report.append("[OK] No issues found - estimate appears compliant with carrier guidelines.")
        report.append("")
    else:
        # Disallowed items section
        if disallowed_count > 0:
            report.append("## 1. Disallowed Items")
            report.append("")
            report.append(f"Found {disallowed_count} line item(s) that may violate carrier guidelines:")
            report.append("")

            for idx, issue in enumerate(issues_data['disallowed']['issues'], start=1):
                report.append(f"### Issue #{idx}: {issue['description']}")
                report.append("")
                report.append(f"- **Line Item:** #{issue['line_item']}")
                report.append(f"- **Category:** {issue.get('category', 'N/A')}")
                report.append(f"- **Amount:** ${issue['total']:.2f}")
                report.append(f"- **Confidence:** {issue['confidence']}%")
                report.append(f"- **Reason:** {issue['reason']}")
                report.append(f"- **Recommendation:** {issue['recommendation']}")
                report.append(f"- **Guideline Reference:** {issue['guideline_reference']}")
                report.append("")

        # Quantity limits section
        if quantities_count > 0:
            report.append(f"## 2. Quantity Limit Violations")
            report.append("")
            report.append(f"Found {quantities_count} line item(s) that exceed carrier quantity limits:")
            report.append("")

            for idx, issue in enumerate(issues_data['quantities']['issues'], start=1):
                report.append(f"### Issue #{idx}: {issue['description']}")
                report.append("")
                report.append(f"- **Line Item:** #{issue['line_item']}")
                report.append(f"- **Category:** {issue.get('category', 'N/A')}")
                report.append(f"- **Amount:** ${issue['total']:.2f}")
                report.append(f"- **Max Allowed:** {issue['max_allowed']} {issue.get('unit', 'units')}")
                report.append(f"- **Excess:** {issue['excess']}")
                report.append(f"- **Reason:** {issue['reason']}")
                report.append(f"- **Recommendation:** {issue['recommendation']}")
                report.append(f"- **Guideline Reference:** {issue['guideline_reference']}")
                report.append("")

        # Depreciation section (future)
        if depreciation_count > 0:
            report.append(f"## 3. Depreciation Errors")
            report.append("")
            report.append(f"Found {depreciation_count} depreciation calculation issue(s):")
            report.append("")
            # ... (to be implemented in Phase 2)

    # Recommended actions section
    if total_issues > 0:
        report.append("## Recommended Actions")
        report.append("")

        action_num = 1
        total_adjustment = 0

        # Actions from disallowed items
        if disallowed_count > 0:
            for issue in issues_data['disallowed']['issues']:
                action = issue.get('action', 'review')
                if action == 'remove':
                    report.append(f"{action_num}. **Remove** line item #{issue['line_item']}: {issue['description']}")
                    report.append(f"   - Saves: ${issue['total']:.2f}")
                    total_adjustment += issue['total']
                elif action == 'review':
                    report.append(f"{action_num}. **Review with adjuster** line item #{issue['line_item']}: {issue['description']}")
                    report.append(f"   - Potential adjustment: ${issue['total']:.2f}")
                else:
                    report.append(f"{action_num}. **Flag for manual review** line item #{issue['line_item']}: {issue['description']}")

                report.append("")
                action_num += 1

        # Actions from quantity limits
        if quantities_count > 0:
            for issue in issues_data['quantities']['issues']:
                report.append(f"{action_num}. **Adjust quantity** for line item #{issue['line_item']}: {issue['description']}")
                report.append(f"   - {issue['recommendation']}")
                report.append(f"   - Potential adjustment: ${issue['total']:.2f}")
                report.append("")
                action_num += 1

        # Summary of adjustments
        if total_adjustment > 0:
            revised_total = rcv_total - total_adjustment
            report.append(f"**Total Recommended Adjustment:** -${total_adjustment:.2f}")
            report.append(f"**Revised Estimate Total:** ${revised_total:,.2f}")
            report.append("")

    # Footer
    report.append("---")
    report.append("")
    report.append("*This report was generated automatically by the QA Reconstruction Estimate Automation system.*")
    report.append("*Always verify recommendations with carrier guidelines and adjuster before finalizing changes.*")

    return '\n'.join(report)


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python generate_qa_report.py <estimate_json> <issues_dir> [--output <output_path>]")
        sys.exit(1)

    estimate_path = sys.argv[1]
    issues_dir = sys.argv[2]

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

    if not os.path.exists(issues_dir):
        print(f"Error: Issues directory not found: {issues_dir}")
        sys.exit(1)

    print(f"Loading estimate: {estimate_path}")
    print(f"Loading issues from: {issues_dir}\n")

    try:
        # Load data
        estimate_json = load_json(estimate_path)
        estimate_id = estimate_json.get('estimate_id', 'unknown')
        issues_data = load_all_issues(issues_dir, estimate_id)

        # Generate report
        print("Generating QA report...")
        report_markdown = generate_markdown_report(estimate_json, issues_data)

        # Determine output path
        if not output_path:
            output_dir = Path('.tmp/reports')
            output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime('%Y%m%d')
            output_path = output_dir / f'qa_report_{estimate_id}_{date_str}.md'

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_markdown)

        print(f"\nReport generated successfully!")
        print(f"Output saved to: {output_path}")

        # Print summary
        total_issues = sum([
            issues_data['disallowed'].get('issues_found', 0) if issues_data['disallowed'] else 0,
            issues_data['quantities'].get('issues_found', 0) if issues_data['quantities'] else 0,
            issues_data['depreciation'].get('issues_found', 0) if issues_data['depreciation'] else 0
        ])

        print(f"\nTotal issues in report: {total_issues}")

        return output_path

    except Exception as e:
        print(f"Error generating report: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
