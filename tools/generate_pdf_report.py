#!/usr/bin/env python3
"""
Generate PDF report from QA validation results.

Usage:
    python generate_pdf_report.py <estimate_json> <issues_dir> [--output <output_path>]
"""

import sys
import json
import os
import math
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Circle, Polygon, String


# Alert taxonomy mirrors Xactimate's own QA scrub conventions, so results
# read consistently with what estimators already know:
#   Violation - things the carrier will not allow; must be resolved.
#   Warning   - resolvable, or explained with a line-item note.
#   Caution   - worth noting, but no action is required.
# Violations = disallowed items + quantity limit violations.
# Warnings = F9 note requirements. Cautions = observations.
ALERT_STYLES = {
    'violation': {
        'color': '#dc3545', 'bg': '#f8d7da', 'label': 'Violation',
        'description': 'Must be resolved inside the estimate.'
    },
    'warning': {
        'color': '#e67e22', 'bg': '#fdebd0', 'label': 'Warning',
        'description': 'Can be resolved, or explained with a line-item note.'
    },
    'caution': {
        'color': '#f0ad4e', 'bg': '#fff3cd', 'label': 'Caution',
        'description': 'Worth noting, but no action is required.'
    },
}


def _regular_polygon_points(cx, cy, radius, sides, rotation_deg=0):
    """Vertex list for a regular polygon, flattened for reportlab's Polygon."""
    points = []
    for i in range(sides):
        angle = math.radians(rotation_deg + i * (360 / sides))
        points.append(cx + radius * math.sin(angle))
        points.append(cy + radius * math.cos(angle))
    return points


def make_alert_icon(kind, size=16):
    """Small badge icon: circle (violation), octagon (warning), triangle (caution)."""
    style = ALERT_STYLES[kind]
    cx = cy = size / 2
    color = colors.HexColor(style['color'])
    d = Drawing(size, size)

    if kind == 'violation':
        d.add(Circle(cx, cy, size * 0.44, fillColor=color, strokeColor=None))
    elif kind == 'warning':
        pts = _regular_polygon_points(cx, cy, size * 0.48, 8, rotation_deg=22.5)
        d.add(Polygon(pts, fillColor=color, strokeColor=None))
    else:
        pts = _regular_polygon_points(cx, cy, size * 0.54, 3, rotation_deg=0)
        d.add(Polygon(pts, fillColor=color, strokeColor=None))

    d.add(String(cx, cy - size * 0.22, '!', fillColor=colors.white,
                  fontName='Helvetica-Bold', fontSize=size * 0.55, textAnchor='middle'))
    return d


def alert_heading(kind, text, heading_style):
    """Section heading with its alert badge icon inline to the left."""
    icon = make_alert_icon(kind, size=18)
    label = Paragraph(f"<b>{text}</b>", heading_style)
    t = Table([[icon, label]], colWidths=[0.3 * inch, 5.9 * inch])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def load_json(file_path):
    """Load and parse JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_issues(issues_dir, estimate_id):
    """Load all issue JSON files for an estimate."""
    issues_data = {
        'disallowed': None,
        'quantities': None,
        'depreciation': None,
        'f9_notes': None,
        'observations': None
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

    # Load F9 notes
    f9_notes_file = issues_path / f'f9_notes_{estimate_id}.json'
    if f9_notes_file.exists():
        issues_data['f9_notes'] = load_json(f9_notes_file)

    # Load observations
    observations_file = issues_path / f'observations_{estimate_id}.json'
    if observations_file.exists():
        issues_data['observations'] = load_json(observations_file)

    return issues_data


def generate_pdf_report(estimate_json, issues_data, output_path):
    """Generate PDF report from estimate and issues data."""

    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )

    # Container for PDF elements
    story = []

    # Get styles
    styles = getSampleStyleSheet()

    # Custom styles - Paul Davis brand palette (charcoal + gold, from the
    # company logo) in place of the generic blue used previously.
    banner_style = ParagraphStyle(
        'CustomBanner',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#C9A961'),
        alignment=TA_CENTER,
        leading=26
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#96742F'),
        spaceAfter=12,
        spaceBefore=20
    )

    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        spaceBefore=15
    )

    normal_style = styles['Normal']

    legend_text_style = ParagraphStyle(
        'LegendText',
        parent=normal_style,
        fontSize=10,
    )

    # Extract data
    estimate_id = estimate_json.get('estimate_id', 'Unknown')
    client = estimate_json.get('metadata', {}).get('client', 'Unknown')
    date = estimate_json.get('metadata', {}).get('date', 'Unknown')

    # Get carrier from issues
    carrier = "Unknown"
    for issue_type, data in issues_data.items():
        if data and 'carrier' in data:
            carrier = data['carrier']
            break

    # Calculate counts
    disallowed_count = 0
    quantities_count = 0
    f9_notes_count = 0
    observations_count = 0

    if issues_data['disallowed']:
        disallowed_count = issues_data['disallowed'].get('issues_found', 0)

    if issues_data['quantities']:
        quantities_count = issues_data['quantities'].get('issues_found', 0)

    if issues_data['f9_notes']:
        f9_notes_count = issues_data['f9_notes'].get('f9_notes_required', 0)

    if issues_data['observations']:
        observations_count = issues_data['observations'].get('observations_found', 0)

    # Violations = disallowed items + quantity limit violations (must be
    # resolved). Warnings = F9 note requirements (resolvable with a note).
    # Cautions = observations (informational).
    violations_count = disallowed_count + quantities_count
    warnings_count = f9_notes_count
    cautions_count = observations_count
    total_alerts = violations_count + warnings_count + cautions_count

    # Estimate totals
    summary = estimate_json.get('summary', {})
    line_item_total = summary.get('line_item_total', 0)
    overhead = summary.get('overhead', 0)
    profit = summary.get('profit', 0)
    rcv_total = line_item_total + overhead + profit

    # Title banner - charcoal background with gold text, matching the Paul
    # Davis logo treatment.
    banner_table = Table([[Paragraph("QA REVIEW REPORT", banner_style)]], colWidths=[7*inch])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#141414')),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 0.25*inch))

    # Header info table
    header_data = [
        ['Estimate ID:', estimate_id, 'Client:', client],
        ['Estimate Date:', date, 'Review Date:', datetime.now().strftime('%Y-%m-%d')],
        ['Carrier:', carrier, 'Original Total:', f'${rcv_total:,.2f}']
    ]

    header_table = Table(header_data, colWidths=[1.2*inch, 2*inch, 1.2*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F7F3EC')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F7F3EC')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.3*inch))

    # Alerts legend - explains the three alert types up front, same as the
    # in-app legend, so the report reads the same way regardless of where
    # someone encounters it.
    story.append(Paragraph("Alerts", heading_style))
    story.append(Paragraph(
        "Alerts make it easier to find what and where problems are and how to fix them, "
        "using rules in the estimate. There are three distinct types of alerts.",
        normal_style
    ))
    story.append(Spacer(1, 0.1*inch))

    legend_rows = []
    for kind in ('violation', 'warning', 'caution'):
        style_info = ALERT_STYLES[kind]
        icon = make_alert_icon(kind, size=18)
        text = Paragraph(f"<b>{style_info['label']}</b><br/>{style_info['description']}", legend_text_style)
        legend_rows.append([icon, text])

    legend_table = Table(legend_rows, colWidths=[0.35*inch, 6*inch])
    legend_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(legend_table)
    story.append(Spacer(1, 0.2*inch))

    # Summary Section
    story.append(Paragraph("Summary", heading_style))

    summary_data = [
        ['Total Alerts:', str(total_alerts)],
        ['Violations:', str(violations_count)],
        ['Warnings:', str(warnings_count)],
        ['Cautions:', str(cautions_count)],
    ]

    summary_table = Table(summary_data, colWidths=[3*inch, 3.5*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F7F3EC')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor(ALERT_STYLES['violation']['bg'])),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor(ALERT_STYLES['warning']['bg'])),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor(ALERT_STYLES['caution']['bg'])),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))

    # Issues Detail
    if total_alerts == 0:
        # No issues found
        story.append(Paragraph("Results", heading_style))

        result_text = Paragraph(
            '<para align="center" backColor="#d4edda" borderColor="#c3e6cb" '
            'borderWidth="1" borderPadding="10" fontSize="12">'
            '<b>[OK]</b> No issues found - estimate appears compliant with carrier guidelines.'
            '</para>',
            normal_style
        )
        story.append(result_text)
    else:
        # Violations section - disallowed items + quantity limit violations,
        # merged since both represent things the carrier will not allow.
        if violations_count > 0:
            story.append(alert_heading('violation', f'Violations ({violations_count})', heading_style))
            story.append(Paragraph(
                "These line items violate carrier guidelines and must be resolved before the estimate is submitted.",
                normal_style
            ))
            story.append(Spacer(1, 0.15*inch))

            violation_idx = 1
            violation_row_style = TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(ALERT_STYLES['violation']['bg'])),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ])

            if disallowed_count > 0:
                for issue in issues_data['disallowed']['issues']:
                    story.append(Paragraph(f"Violation #{violation_idx}: {issue['description']}", subheading_style))

                    issue_data = [
                        ['Line Item:', f"#{issue['line_item']}"],
                        ['Category:', issue.get('category', 'N/A')],
                        ['Amount:', f"${issue['total']:.2f}"],
                        ['Confidence:', f"{issue['confidence']}%"],
                        ['Reason:', Paragraph(issue['reason'], normal_style)],
                        ['Recommendation:', Paragraph(issue['recommendation'], normal_style)],
                        ['Reference:', issue['guideline_reference']]
                    ]

                    issue_table = Table(issue_data, colWidths=[1.5*inch, 5*inch])
                    issue_table.setStyle(violation_row_style)
                    story.append(issue_table)
                    story.append(Spacer(1, 0.2*inch))
                    violation_idx += 1

            if quantities_count > 0:
                for issue in issues_data['quantities']['issues']:
                    story.append(Paragraph(f"Violation #{violation_idx}: {issue['description']}", subheading_style))

                    issue_data = [
                        ['Line Item:', f"#{issue['line_item']}"],
                        ['Category:', issue.get('category', 'N/A')],
                        ['Amount:', f"${issue['total']:.2f}"],
                        ['Max Allowed:', f"{issue['max_allowed']} {issue.get('unit', 'units')}"],
                        ['Excess:', str(issue['excess'])],
                        ['Reason:', Paragraph(issue['reason'], normal_style)],
                        ['Recommendation:', Paragraph(issue['recommendation'], normal_style)],
                        ['Reference:', issue.get('guideline_reference', 'N/A')]
                    ]

                    issue_table = Table(issue_data, colWidths=[1.5*inch, 5*inch])
                    issue_table.setStyle(violation_row_style)
                    story.append(issue_table)
                    story.append(Spacer(1, 0.2*inch))
                    violation_idx += 1

    # Warnings section (F9 notes) - ALWAYS show if there are any
    if warnings_count > 0:
        story.append(PageBreak())
        story.append(alert_heading('warning', f'Warnings ({warnings_count})', heading_style))
        story.append(Paragraph(
            f"Found {warnings_count} line item(s) that require a line-item (F9) note in Xactimate to justify their inclusion:",
            normal_style
        ))
        story.append(Spacer(1, 0.15*inch))

        # Create table header
        f9_table_data = [
            ['Line #', 'Description', 'Requirement', 'Recommended Note', 'Guideline Ref']
        ]

        # Add each F9 note requirement
        for flag in issues_data['f9_notes']['flags']:
            f9_table_data.append([
                f"#{flag['line_item']}",
                Paragraph(flag['description'], normal_style),
                Paragraph(flag['requirement'], normal_style),
                Paragraph(flag['recommended_note'], normal_style),
                Paragraph(flag.get('guideline_reference', 'N/A'), normal_style)
            ])

        f9_table = Table(f9_table_data, colWidths=[0.5*inch, 1.9*inch, 1.6*inch, 1.9*inch, 0.9*inch])
        f9_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ALERT_STYLES['warning']['color'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(ALERT_STYLES['warning']['bg'])),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor(ALERT_STYLES['warning']['bg']), colors.white])
        ]))
        story.append(f9_table)
        story.append(Spacer(1, 0.3*inch))

    # Cautions section (observations) - ALWAYS show if there are any
    if cautions_count > 0:
        if warnings_count == 0:
            story.append(PageBreak())
        story.append(alert_heading('caution', f'Cautions ({cautions_count})', heading_style))
        story.append(Paragraph(
            f"Found {cautions_count} line item(s) worth reviewing - no action is required unless they don't apply:",
            normal_style
        ))
        story.append(Spacer(1, 0.15*inch))

        # Create table header
        obs_table_data = [
            ['Line #', 'Description', 'Observation', 'Recommendation', 'Guideline Ref']
        ]

        # Add each observation
        for obs in issues_data['observations']['observations']:
            obs_table_data.append([
                f"#{obs['line_item']}",
                Paragraph(obs['description'], normal_style),
                Paragraph(obs['reason'], normal_style),
                Paragraph(obs['recommendation'], normal_style),
                Paragraph(obs.get('guideline_reference', 'N/A'), normal_style)
            ])

        obs_table = Table(obs_table_data, colWidths=[0.5*inch, 1.9*inch, 1.7*inch, 1.6*inch, 0.9*inch])
        obs_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(ALERT_STYLES['caution']['color'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor(ALERT_STYLES['caution']['bg'])),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor(ALERT_STYLES['caution']['bg']), colors.white])
        ]))
        story.append(obs_table)
        story.append(Spacer(1, 0.3*inch))

    # Recommended actions - only if there are violations to act on
    if violations_count > 0:
        story.append(PageBreak())
        story.append(Paragraph("Recommended Actions", heading_style))

        action_num = 1
        total_adjustment = 0

        # Actions from disallowed items
        if disallowed_count > 0:
            for issue in issues_data['disallowed']['issues']:
                action = issue.get('action', 'review')
                if action == 'remove':
                    action_text = f"{action_num}. <b>Remove</b> line item #{issue['line_item']}: {issue['description']}<br/>   - Saves: ${issue['total']:.2f}"
                    total_adjustment += issue['total']
                else:
                    action_text = f"{action_num}. <b>Review with adjuster</b> line item #{issue['line_item']}: {issue['description']}<br/>   - Potential adjustment: ${issue['total']:.2f}"

                story.append(Paragraph(action_text, normal_style))
                story.append(Spacer(1, 0.1*inch))
                action_num += 1

        # Actions from quantity limit violations
        if quantities_count > 0:
            for issue in issues_data['quantities']['issues']:
                action_text = (
                    f"{action_num}. <b>Reduce quantity</b> on line item #{issue['line_item']}: "
                    f"{issue['description']}<br/>   - {issue['recommendation']}"
                )
                story.append(Paragraph(action_text, normal_style))
                story.append(Spacer(1, 0.1*inch))
                action_num += 1

        # Summary of adjustments
        if total_adjustment > 0:
            revised_total = rcv_total - total_adjustment

            adjustment_data = [
                ['Total Recommended Adjustment:', f'-${total_adjustment:.2f}'],
                ['Revised Estimate Total:', f'${revised_total:,.2f}']
            ]

            story.append(Spacer(1, 0.2*inch))
            adjustment_table = Table(adjustment_data, colWidths=[3.5*inch, 3*inch])
            adjustment_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#d4edda')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#28a745')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(adjustment_table)

    # Footer
    story.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=9,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    story.append(Paragraph("_" * 100, footer_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(
        "<i>This report was generated automatically by the QA Reconstruction Estimate Automation system.</i><br/>"
        "<i>Always verify recommendations with carrier guidelines and adjuster before finalizing changes.</i>",
        footer_style
    ))

    # Build PDF
    doc.build(story)


def main():
    """Main function."""
    if len(sys.argv) < 3:
        print("Usage: python generate_pdf_report.py <estimate_json> <issues_dir> [--output <output_path>]")
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

        # Determine output path
        if not output_path:
            output_dir = Path('.tmp/reports')
            output_dir.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime('%Y%m%d')
            output_path = output_dir / f'qa_report_{estimate_id}_{date_str}.pdf'

        # Generate PDF report
        print("Generating PDF report...")
        generate_pdf_report(estimate_json, issues_data, str(output_path))

        print(f"\nPDF report generated successfully!")
        print(f"Output saved to: {output_path}")

        # Print summary
        violations = sum([
            issues_data['disallowed'].get('issues_found', 0) if issues_data['disallowed'] else 0,
            issues_data['quantities'].get('issues_found', 0) if issues_data['quantities'] else 0
        ])
        warnings = issues_data['f9_notes'].get('f9_notes_required', 0) if issues_data['f9_notes'] else 0
        cautions = issues_data['observations'].get('observations_found', 0) if issues_data['observations'] else 0

        print(f"Violations: {violations} | Warnings: {warnings} | Cautions: {cautions}")

        return output_path

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
