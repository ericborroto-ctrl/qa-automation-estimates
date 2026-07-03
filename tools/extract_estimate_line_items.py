#!/usr/bin/env python3
"""
Extract line items from Xactimate estimate PDFs.

This tool parses Xactimate PDF exports and extracts structured line item data
including descriptions, quantities, units, prices, and totals.

Usage:
    python extract_estimate_line_items.py <pdf_path> [--output <output_path>]
"""

import sys
import json
import os
from pathlib import Path
import pdfplumber
import re


def extract_estimate_id(pdf_path):
    """Extract estimate ID from filename."""
    filename = Path(pdf_path).stem
    # Remove common prefixes/suffixes
    estimate_id = filename.replace('_CON', '').replace('CLAUDE_TEST_', '').replace('ABBREVIATED_', '')
    return estimate_id or 'UNKNOWN'


def extract_line_items(pdf):
    """Extract line items from the PDF - handles both table and text formats."""
    line_items = []

    # Try to find line items on pages 2-3 (common Xactimate format)
    for page_num in range(min(len(pdf.pages), 5)):  # Check first 5 pages
        page = pdf.pages[page_num]
        text = page.extract_text() or ''

        # Look for line item pattern in text (Xactimate format)
        # Pattern: "1. Description 48.00 LF @ 19.98 = 959.04"
        lines = text.split('\n')

        for line in lines:
            # Match line item pattern: number. description quantity unit @ price = total
            # Example: "1. 1/2" - drywall per LF - up to 4' tall 48.00 LF @ 19.98 = 959.04"
            pattern = r'^(\d+)\.\s+(.+?)\s+([\d,]+\.?\d*)\s+([A-Z]+)\s+@\s+([\d,]+\.?\d*)\s+=\s+([\d,]+\.?\d*)$'
            match = re.match(pattern, line.strip())

            if match:
                item_number = int(match.group(1))
                description = match.group(2).strip()
                quantity = float(match.group(3).replace(',', ''))
                unit = match.group(4)
                unit_price = float(match.group(5).replace(',', ''))
                total = float(match.group(6).replace(',', ''))

                # Extract category from description if possible
                category = None
                # Common patterns: "drywall", "paint", "carpet", etc.
                desc_lower = description.lower()
                if 'drywall' in desc_lower:
                    category = 'DRYWALL'
                elif 'paint' in desc_lower or 'primer' in desc_lower or 'seal' in desc_lower:
                    category = 'PAINTING'
                elif 'texture' in desc_lower:
                    category = 'DRYWALL'
                elif 'trim' in desc_lower or 'baseboard' in desc_lower or 'door' in desc_lower or 'casing' in desc_lower:
                    category = 'FINISH CARPENTRY / TRIMWORK'
                elif 'carpet' in desc_lower or 'flooring' in desc_lower:
                    category = 'FLOORING'

                line_item = {
                    'item_number': item_number,
                    'description': description,
                    'category': category,
                    'quantity': quantity,
                    'unit': unit,
                    'unit_price': unit_price,
                    'total': total
                }

                line_items.append(line_item)

        # Also try table extraction as fallback
        tables = page.extract_tables()
        for table in tables:
            if not table or len(table) < 2:
                continue

            # Look for table headers that indicate line items
            header_row = table[0] if table else []
            header_text = ' '.join([str(cell) or '' for cell in header_row]).lower()

            # Check if this looks like a line items table
            if any(keyword in header_text for keyword in ['item', 'description', 'quantity', 'price', 'total']):
                # Process data rows
                for row_idx, row in enumerate(table[1:], start=1):
                    if not row or len(row) < 3:
                        continue

                    # Skip header rows and empty rows
                    row_text = ' '.join([str(cell) or '' for cell in row]).lower()
                    if any(keyword in row_text for keyword in ['item', 'description', 'quantity', 'unit']):
                        continue

                    # Try to parse line item data
                    try:
                        # Flexible parsing based on available columns
                        item_number = None
                        description = None
                        quantity = None
                        unit = None
                        unit_price = None
                        total = None
                        category = None

                        # Find description (usually longest text field)
                        for cell in row:
                            if cell and isinstance(cell, str) and len(cell) > 10:
                                if not description or len(str(cell)) > len(description):
                                    description = str(cell).strip()

                        # Find numeric values (quantities, prices)
                        numbers = []
                        for cell in row:
                            if cell:
                                # Try to parse as number
                                cell_str = str(cell).replace('$', '').replace(',', '').strip()
                                try:
                                    num = float(cell_str)
                                    numbers.append(num)
                                except ValueError:
                                    pass

                        # Assign numbers (typically: quantity, unit_price, total)
                        if len(numbers) >= 3:
                            quantity = numbers[0]
                            unit_price = numbers[1]
                            total = numbers[2]
                        elif len(numbers) == 2:
                            quantity = numbers[0]
                            total = numbers[1]

                        # Skip if no valid data
                        if not description or not total:
                            continue

                        # Try to extract category from description (UPPERCASE words)
                        category_match = re.search(r'\b([A-Z]{3,})\b', description)
                        if category_match:
                            category = category_match.group(1)

                        line_item = {
                            'item_number': len(line_items) + 1,
                            'description': description,
                            'category': category,
                            'quantity': quantity,
                            'unit': unit,
                            'unit_price': unit_price,
                            'total': total
                        }

                        line_items.append(line_item)

                    except Exception as e:
                        # Skip problematic rows
                        continue

    return line_items


def extract_summary(pdf):
    """Extract summary totals from the PDF."""
    summary = {
        'line_item_total': None,
        'overhead': None,
        'profit': None,
        'rcv': None,
        'acv': None
    }

    # Look for summary section in last few pages
    for page_num in range(min(len(pdf.pages), 5)):
        page = pdf.pages[page_num]
        text = page.extract_text() or ''

        # Look for key summary terms and extract values
        patterns = {
            'line_item_total': r'(?:sub[\s-]?total|line item total)[:\s]*\$?\s*([\d,]+\.?\d*)',
            'overhead': r'overhead[:\s]*\$?\s*([\d,]+\.?\d*)',
            'profit': r'profit[:\s]*\$?\s*([\d,]+\.?\d*)',
            'rcv': r'(?:rcv|replacement cost)[:\s]*\$?\s*([\d,]+\.?\d*)',
            'acv': r'(?:acv|actual cash)[:\s]*\$?\s*([\d,]+\.?\d*)'
        }

        for key, pattern in patterns.items():
            if summary[key] is None:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        value_str = match.group(1).replace(',', '')
                        summary[key] = float(value_str)
                    except ValueError:
                        pass

    return summary


def extract_metadata(pdf, pdf_path):
    """Extract estimate metadata."""
    metadata = {
        'source_file': os.path.basename(pdf_path),
        'total_pages': len(pdf.pages),
        'client': None,
        'date': None,
        'address': None
    }

    # Try to extract from first page
    if pdf.pages:
        first_page_text = pdf.pages[0].extract_text() or ''

        # Look for common metadata patterns
        # Date pattern
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', first_page_text)
        if date_match:
            metadata['date'] = date_match.group(1)

        # Client/Insured pattern
        client_match = re.search(r'(?:client|insured)[:\s]*([^\n]+)', first_page_text, re.IGNORECASE)
        if client_match:
            metadata['client'] = client_match.group(1).strip()

    return metadata


def main():
    """Main extraction function."""
    if len(sys.argv) < 2:
        print("Usage: python extract_estimate_line_items.py <pdf_path> [--output <output_path>]")
        sys.exit(1)

    pdf_path = sys.argv[1]

    # Check if output path is specified
    output_path = None
    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output')
        if output_idx + 1 < len(sys.argv):
            output_path = sys.argv[output_idx + 1]

    # Validate input file
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting data from: {pdf_path}")

    try:
        # Open PDF and extract data
        with pdfplumber.open(pdf_path) as pdf:
            estimate_id = extract_estimate_id(pdf_path)
            line_items = extract_line_items(pdf)
            summary = extract_summary(pdf)
            metadata = extract_metadata(pdf, pdf_path)

            # Build output JSON
            output = {
                'estimate_id': estimate_id,
                'metadata': metadata,
                'line_items': line_items,
                'summary': summary,
                'extraction_stats': {
                    'total_line_items': len(line_items),
                    'extraction_method': 'pdfplumber',
                    'success': True
                }
            }

            # Determine output path
            if not output_path:
                output_dir = Path('.tmp/estimates')
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f'{estimate_id}_line_items.json'

            # Write JSON output
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2)

            print(f"\nExtraction complete!")
            print(f"Estimate ID: {estimate_id}")
            print(f"Line items extracted: {len(line_items)}")
            print(f"Output saved to: {output_path}")

            # Print summary
            if summary['rcv']:
                print(f"RCV Total: ${summary['rcv']:.2f}")

            return output

    except Exception as e:
        print(f"Error extracting PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
