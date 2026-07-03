#!/usr/bin/env python3
"""
Extract line items from Xactimate estimates using OCR for image-based PDFs.

This tool handles both text-based and image-based (scanned) PDFs by using
OCR when necessary to extract line item data.

Usage:
    python extract_estimate_with_ocr.py <pdf_path> [--output <output_path>]
"""

import sys
import json
import re
import os
from pathlib import Path
from datetime import datetime
import pdfplumber
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import io

# Set tesseract path (Windows default installation)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_with_ocr(pdf_path, start_page=0, end_page=None):
    """Extract text from PDF using OCR."""
    print(f"Using OCR to extract text from {pdf_path}...")

    # Open PDF with PyMuPDF
    doc = fitz.open(pdf_path)

    if end_page is None:
        end_page = len(doc)

    text_by_page = []
    for page_num in range(start_page, min(end_page, len(doc))):
        print(f"  Processing page {page_num + 1}/{len(doc)}...")

        # Get page
        page = doc[page_num]

        # Convert page to image
        pix = page.get_pixmap(dpi=300)  # High DPI for better OCR
        img_data = pix.tobytes("png")

        # Convert to PIL Image
        image = Image.open(io.BytesIO(img_data))

        # Use OCR to extract text
        text = pytesseract.image_to_string(image, config='--psm 6')
        text_by_page.append(text)

    doc.close()
    return text_by_page


def is_text_based_pdf(pdf_path):
    """Check if PDF has extractable text or needs OCR."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Check first few pages for text
            for i in range(min(3, len(pdf.pages))):
                text = pdf.pages[i].extract_text()
                if text and len(text.strip()) > 100:
                    return True
        return False
    except:
        return False


def extract_line_items_from_text(text, estimate_id):
    """Extract line items from text using regex patterns."""
    line_items = []

    lines = text.split('\n')

    # Two-line format parser for OCR text
    # Line 1: 169. TIL SWR>+ & R&R Tile shower - 101 to 120 SF - High grade
    # Line 2: 1 1.00 EA 387.11+ 3,481.63 = 85.22 790.78 4,744.74

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Look for line number and description pattern
        desc_pattern = r'^(\d+)\.\s+([A-Z]{2,}[^0-9]+.+?)$'
        desc_match = re.match(desc_pattern, line)

        if desc_match and i + 1 < len(lines):
            line_num = desc_match.group(1)
            description = desc_match.group(2).strip()

            # Look at next line for quantity/price data
            next_line = lines[i + 1].strip()

            # Pattern for: 1 1.00 EA 387.11+ 3,481.63 = 85.22 790.78 4,744.74
            # or: 1642.76 1642.76SF 1.50+ 0.00 = 69.41 506.70 3,040.25
            qty_pattern = r'[\d,]+\.?\d*\s+([\d,]+\.?\d*)\s*([A-Z]{1,4})\s+([\d,]+\.?\d*)\+.+?[\d,]+\.?\d*\s+([\d,]+\.?\d*)$'
            qty_match = re.search(qty_pattern, next_line)

            if qty_match:
                quantity = qty_match.group(1).replace(',', '')
                unit = qty_match.group(2)
                unit_price = qty_match.group(3).replace(',', '')
                total = qty_match.group(4).replace(',', '')

                # Auto-categorize based on description
                category = categorize_line_item(description)

                try:
                    line_item = {
                        'line_number': int(line_num),
                        'description': description,
                        'quantity': float(quantity),
                        'unit': unit,
                        'unit_price': float(unit_price),
                        'total': float(total),
                        'category': category
                    }

                    line_items.append(line_item)
                    i += 2  # Skip next line since we processed it
                    continue
                except (ValueError, IndexError):
                    pass  # Skip if parsing fails

        i += 1

    return line_items


def categorize_line_item(description):
    """Categorize line item based on description keywords."""
    desc_upper = description.upper()

    categories = {
        'DRYWALL': ['DRY', 'DRYWALL', 'SHEETROCK', 'GYPSUM'],
        'PAINTING': ['PAINT', 'PNT', 'PRIME', 'SEAL'],
        'FLOORING': ['CARPET', 'FLOOR', 'VINYL', 'TILE', 'HARDWOOD', 'LAMINATE'],
        'ROOFING': ['ROOF', 'SHINGLE', 'FLASHING', 'UNDERLAYMENT'],
        'PLUMBING': ['PLB', 'PLUMB', 'PIPE', 'FIXTURE', 'FAUCET'],
        'ELECTRICAL': ['ELC', 'ELECT', 'WIRE', 'OUTLET', 'SWITCH'],
        'HVAC': ['HVAC', 'DUCT', 'FURNACE', 'AC', 'AIR COND'],
        'DEMOLITION': ['DEMO', 'REMOVE', 'RMV', 'TEAR OUT'],
        'MITIGATION': ['MITIGATION', 'DRY', 'EXTRACT', 'DEHUMID'],
        'CLEANING': ['CLEAN', 'CLN'],
        'GENERAL': ['LABOR', 'LAB', 'MINIMUM', 'MIN']
    }

    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return category

    return 'OTHER'


def extract_summary_totals(text):
    """Extract summary totals from estimate."""
    summary = {
        'line_item_total': 0,
        'overhead': 0,
        'profit': 0,
        'tax': 0,
        'rcv_total': 0
    }

    # Look for summary section patterns
    patterns = {
        'line_item_total': r'(?:Subtotal|Line\s+Item\s+Total|Total)[:\s]+\$?([\d,]+\.\d{2})',
        'overhead': r'Overhead[:\s]+\$?([\d,]+\.\d{2})',
        'profit': r'Profit[:\s]+\$?([\d,]+\.\d{2})',
        'tax': r'Tax[:\s]+\$?([\d,]+\.\d{2})',
        'rcv_total': r'(?:RCV|Total|Grand\s+Total)[:\s]+\$?([\d,]+\.\d{2})'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).replace(',', '')
            summary[key] = float(value)

    return summary


def extract_metadata(text, pdf_path):
    """Extract estimate metadata."""
    metadata = {
        'client': 'Unknown',
        'date': 'Unknown',
        'address': 'Unknown',
        'adjuster': 'Unknown'
    }

    # Try to extract metadata from text
    client_match = re.search(r'(?:Insured|Name|Client)[:\s]+(.+)', text, re.IGNORECASE)
    if client_match:
        metadata['client'] = client_match.group(1).strip()

    date_match = re.search(r'(?:Date|Estimate\s+Date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['date'] = date_match.group(1).strip()

    address_match = re.search(r'(?:Address|Loss\s+Address)[:\s]+(.+)', text, re.IGNORECASE)
    if address_match:
        metadata['address'] = address_match.group(1).strip()

    return metadata


def main():
    """Main extraction function."""
    if len(sys.argv) < 2:
        print("Usage: python extract_estimate_with_ocr.py <pdf_path> [--output <output_path>]")
        sys.exit(1)

    pdf_path = sys.argv[1]

    # Check if output path is specified
    output_path = None
    if '--output' in sys.argv:
        output_idx = sys.argv.index('--output')
        if output_idx + 1 < len(sys.argv):
            output_path = sys.argv[output_idx + 1]

    # Validate input
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting data from: {pdf_path}\n")

    try:
        # Check if PDF is text-based or needs OCR
        is_text_based = is_text_based_pdf(pdf_path)

        if is_text_based:
            print("PDF is text-based, using standard extraction...")
            with pdfplumber.open(pdf_path) as pdf:
                # Extract text from all pages
                full_text = ""
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        full_text += text + "\n"
        else:
            print("PDF is image-based, using OCR...")
            # Use OCR to extract text
            text_pages = extract_text_with_ocr(pdf_path)
            full_text = "\n".join(text_pages)

        # Extract estimate ID from filename
        estimate_id = Path(pdf_path).stem

        # Extract line items
        print("\nExtracting line items...")
        line_items = extract_line_items_from_text(full_text, estimate_id)

        # Extract metadata
        metadata = extract_metadata(full_text, pdf_path)

        # Extract summary totals
        summary = extract_summary_totals(full_text)

        # If summary totals not found, calculate from line items
        if summary['line_item_total'] == 0 and line_items:
            summary['line_item_total'] = sum(item['total'] for item in line_items)

        # Create output structure
        output_data = {
            'estimate_id': estimate_id,
            'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source_file': str(Path(pdf_path).name),
            'extraction_method': 'text' if is_text_based else 'ocr',
            'metadata': metadata,
            'line_items': line_items,
            'summary': summary
        }

        # Determine output path
        if not output_path:
            output_dir = Path('.tmp/estimates')
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f'{estimate_id}_line_items.json'

        # Save to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nExtraction complete!")
        print(f"Estimate ID: {estimate_id}")
        print(f"Line items extracted: {len(line_items)}")
        print(f"Output saved to: {output_path}")

        return output_path

    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
