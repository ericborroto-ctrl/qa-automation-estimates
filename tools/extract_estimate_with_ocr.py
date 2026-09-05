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

# On Windows, point pytesseract at the default Tesseract install location.
# On Linux (e.g. Streamlit Cloud), Tesseract is installed via packages.txt
# and is already on PATH, so leave pytesseract's default lookup alone.
if sys.platform == 'win32':
    _default_windows_tesseract = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(_default_windows_tesseract):
        pytesseract.pytesseract.tesseract_cmd = _default_windows_tesseract


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


SYMBILITY_ITEM_PATTERN = re.compile(
    r'^(\d+)\s+(.+?)\s+([\d,]+(?:\.\d+)?)\s+\$([\d,]+\.\d{2})\s+([A-Za-z]{1,4})\s+\$([\d,]+\.\d{2})\s*$'
)


def is_symbility_format(text):
    """Detect Symbility/CoreLogic-style estimates (e.g. THIG/CastleCare
    reports), which lay out line items completely differently from
    Xactimate: single-line items with '$' before both the unit price and
    total ("Toilet, Two-Piece, Good - Rem/Reset 1 $306.71 EA $306.71"), no
    leading CAT-code prefix on the description, and room names declared
    BEFORE their items via a Length/Width/Height block rather than a
    trailing 'Totals:' line.

    Checked line by line rather than as one re.search over the whole text -
    SYMBILITY_ITEM_PATTERN anchors on ^/$, which without re.MULTILINE only
    matches the very start/end of the entire string, not each line."""
    return any(SYMBILITY_ITEM_PATTERN.match(line.strip()) for line in text.split('\n'))


def extract_line_items_from_symbility_text(text, estimate_id):
    """Extract line items from a Symbility/CoreLogic-formatted estimate.

    Room name is the line immediately before its "Length: ... Width: ...
    Height: ..." dimension block (confirmed against a real THIG/CastleCare
    export - every room in that sample followed this exact layout), or,
    for a room continued onto a later page, the line ending in "(con't)"
    (with or without a space before the parenthesis - both appear in real
    exports). Recap/materials/labor summary sections that follow the last
    room are skipped entirely, since e.g. the labor breakdown ("1
    DRYWALLER ~26.95 hrs $113.85 $3,066.81") also starts with a digit but
    isn't a line item.
    """
    line_items = []
    lines = text.split('\n')

    dimension_pattern = re.compile(r'^Length:\s')
    continuation_pattern = re.compile(r"^(.+?)\s*\(con't\)\s*$")
    summary_section_starts = ('Recap by', 'MATERIALS', 'LABOR', 'FLOORPLAN: Floor Plan')

    current_room = 'Unknown'
    in_summary_section = False

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith(summary_section_starts):
            in_summary_section = True
        if in_summary_section:
            continue

        if dimension_pattern.match(line) and i > 0:
            candidate = lines[i - 1].strip()
            if candidate:
                current_room = candidate
            continue

        continuation_match = continuation_pattern.match(line)
        if continuation_match:
            current_room = continuation_match.group(1).strip()
            continue

        item_match = SYMBILITY_ITEM_PATTERN.match(line)
        if item_match:
            line_num, description, quantity, unit_price, unit, total = item_match.groups()
            description = description.strip()
            try:
                line_items.append({
                    'line_number': int(line_num),
                    'description': description,
                    'quantity': float(quantity.replace(',', '')),
                    'unit': unit,
                    'unit_price': float(unit_price.replace(',', '')),
                    'total': float(total.replace(',', '')),
                    'category': categorize_line_item(description),
                    'room': current_room,
                })
            except (ValueError, IndexError):
                pass

    return line_items


def extract_line_items_from_text(text, estimate_id):
    """Extract line items from text using regex patterns."""
    line_items = []

    lines = text.split('\n')

    # Two-line format parser for OCR text
    # Line 1: 169. TIL SWR>+ & R&R Tile shower - 101 to 120 SF - High grade
    # Line 2: 1 1.00 EA 387.11+ 3,481.63 = 85.22 790.78 4,744.74

    # Room boundaries are marked by a "Totals: <Room Name> <tax> [o&p] <total>"
    # line once every item in that room has been listed (the final level-wide
    # rollup uses the singular "Total:"). The room-name text that appears
    # where a room *starts* is overlaid on the room's sketch diagram in the
    # source PDF and OCRs unreliably, so instead of parsing that we
    # retroactively tag each pending item once its room's totals line is
    # found - that text isn't overlaid on the diagram and OCRs cleanly.
    # Some estimates show tax+O&P+total (3 numbers), others just tax+total
    # (2 numbers, when O&P isn't broken out as its own column).
    total_pattern = re.compile(
        r'^Totals?:\s*(.+?)\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}(?:\s+[\d,]+\.\d{2})?\s*$'
    )
    pending_items = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        total_match = total_pattern.match(line)
        if total_match:
            room_name = total_match.group(1).strip()
            if room_name and not any(ch.isdigit() for ch in room_name):
                for pending_item in pending_items:
                    pending_item['room'] = room_name
                pending_items = []
            i += 1
            continue

        # Look for line number and description pattern
        desc_pattern = r'^(\d+)\.\s+([A-Z]{2,}[^0-9]+.+?)$'
        desc_match = re.match(desc_pattern, line)

        if desc_match and i + 1 < len(lines):
            line_num = desc_match.group(1)
            description = desc_match.group(2).strip()

            # Look at next line for quantity/price data
            next_line = lines[i + 1].strip()

            # Quantity/unit is sometimes preceded by a raw multiplier and a
            # space (OCR'd text: "1 1.00 EA 387.11+ ..."), and sometimes by
            # a bare calc code with no digit at all, with qty+unit fused and
            # no space (native-text PDF extraction: "PC 26.37LF 0.00+ ...").
            # Rather than anchor on what precedes the quantity, anchor on
            # QTY+UNIT+PRICE wherever it appears on the line, then lazily
            # capture the final dollar amount as the total.
            # Between UNIT and the price, Xactimate sometimes inserts an
            # extra token with no "+" suffix: an ITEL price-override marker
            # ("526.22SF [*] 0.00+ ...") or a reference value on detach/reset
            # items ("1.00EA 23.59 0.00+ ..."). Skip over any such tokens
            # non-greedily rather than requiring the price to immediately
            # follow the unit. The leading negative lookbehind and requiring
            # a digit after any decimal point keep this from starting a
            # match mid-identifier - e.g. the "0." inside a calc code like
            # "FNHTBAR_0.EA" would otherwise look like a valid quantity and
            # steal the match from the real "1.00EA" a few tokens later.
            qty_pattern = r'(?<![A-Za-z0-9_.])([\d,]+(?:\.\d+)?)\s*([A-Z]{1,4})\s+(?:\S+\s+)*?([\d,]+\.?\d*)\+.+?([\d,]+\.\d{2})\s*$'
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
                        'category': category,
                        'room': 'Unknown'
                    }

                    line_items.append(line_item)
                    pending_items.append(line_item)
                    i += 2  # Skip next line since we processed it
                    continue
                except (ValueError, IndexError):
                    pass  # Skip if parsing fails

        i += 1

    return line_items


# Xactimate CAT codes - the first token of every line item description
# (e.g. "WTR" in "WTR BARRZ + Peel & seal zipper") - map to a category
# unambiguously. This is checked before any keyword scan of the full
# description, since scanning the whole text for loose substrings like
# "SEAL" or "AC" produces false matches (e.g. "seal" inside a water-barrier
# item's description, or "AC" inside the word "replace").
CODE_PREFIX_CATEGORIES = {
    'DMO': 'DEMOLITION',
    'WTR': 'MITIGATION',
    'HMR': 'MITIGATION',
    'DRY': 'DRYWALL',
    'PNT': 'PAINTING',
    'TIL': 'FLOORING',
    'FCT': 'FLOORING',
    'CPT': 'FLOORING',
    'RFG': 'ROOFING',
    'SDG': 'SIDING',
    'STU': 'SIDING',
    'PLM': 'PLUMBING',
    'ELE': 'ELECTRICAL',
    'HVC': 'HVAC',
    'CLN': 'CLEANING',
    'FNH': 'OTHER',
    'LAB': 'GENERAL',
    'TMP': 'TARPING',
    'CPS': 'CONTENTS',
    'CDC': 'CONTENTS',
    'CON': 'CONTENTS',
    'CAB': 'CABINETRY',
}


def categorize_line_item(description):
    """Categorize line item, preferring the Xactimate CAT code prefix."""
    code_match = re.match(r'^([A-Z]{2,6})\b', description.strip())
    code = code_match.group(1) if code_match else None

    if code and code in CODE_PREFIX_CATEGORIES:
        return CODE_PREFIX_CATEGORIES[code]

    categories = {
        # Bare 'DRY' deliberately excluded here (and from MITIGATION below)
        # - it's a substring of "Dryer" (APPLIANCES), which Symbility
        # descriptions spell out in full English rather than an Xactimate
        # code, unlike the CODE_PREFIX_CATEGORIES 'DRY' entry above, which
        # only matches at the very start of the description. Bare 'AC' is
        # excluded from HVAC for the same reason - it's a substring of
        # ordinary words like "Backerboard" or "surface".
        'DRYWALL': ['DRYWALL', 'SHEETROCK', 'GYPSUM', 'TEXTURE'],
        'PAINTING': ['PAINT', 'PNT', 'PRIME', 'SEAL'],
        'CABINETRY': ['CABINET', 'VANITY'],
        'DOORS': ['DOOR'],
        'FLOORING': ['CARPET', 'FLOOR', 'VINYL PLANK', 'TILE', 'HARDWOOD', 'LAMINATE', 'UNDERLAYMENT, FOAM'],
        'ROOFING': ['ROOF', 'SHINGLE', 'FLASHING', 'UNDERLAYMENT'],
        'PLUMBING': ['PLB', 'PLUMB', 'PIPE', 'FIXTURE', 'FAUCET', 'TOILET', 'VALVE', 'P-TRAP', 'BATHTUB'],
        # Checked before ELECTRICAL: "Dryer, Electric, Standard" names the
        # power source as a plain adjective, not the electrical trade -
        # ELECTRICAL's 'ELECT' keyword would otherwise catch it first.
        'APPLIANCES': ['DRYER', 'WASHER', 'APPLIANCE'],
        'ELECTRICAL': ['ELC', 'ELECT', 'WIRE', 'OUTLET', 'SWITCH'],
        'HVAC': ['HVAC', 'DUCT', 'FURNACE', 'AIR COND'],
        'WINDOWS': ['BLINDS', 'WINDOW TREATMENT'],
        'INSULATION': ['INSULATION'],
        'TRIM': ['BASE MOLDING', 'QUARTER ROUND', 'CASING'],
        'DEMOLITION': ['DEMO', 'REMOVE', 'RMV', 'TEAR OUT'],
        'MITIGATION': ['MITIGATION', 'EXTRACT', 'DEHUMID'],
        'CLEANING': ['CLEAN', 'CLN'],
        'CONTENTS': ['CONTENT MANIPULATION'],
        'GENERAL': ['LABOR', 'LAB', 'MINIMUM', 'MIN']
    }

    # Symbility-style descriptions put the actual operation at the end,
    # after the last " - " (e.g. "Drywall/Plaster Wall - Prime & Paint" is
    # a painting operation on a drywall surface, not a drywall install).
    # The portion before that dash is a material/spec description that can
    # itself contain misleading terms - e.g. "Quarter Round, Paint Grade -
    # Tear Out" names a trim grade, not a paint action, so scanning the
    # whole string for "PAINT" would wrongly categorize it as painting.
    # When an action suffix exists, use it (and only it) to detect a paint
    # operation, then scan just the material portion - skipping PAINTING's
    # own keywords - for everything else.
    if ' - ' in description:
        noun_part, action_suffix = description.rsplit(' - ', 1)
        if 'PAINT' in action_suffix.upper() or 'SEAL' in action_suffix.upper():
            return 'PAINTING'

        noun_upper = noun_part.upper()
        for category, keywords in categories.items():
            if category == 'PAINTING':
                continue
            for keyword in keywords:
                if keyword in noun_upper:
                    return category
        return 'OTHER'

    desc_upper = description.upper()
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

    # Symbility exports end with an authoritative "Estimate Total: $X" line
    # (after tax, O&P, deductible). The generic 'Total'/'Subtotal' pattern
    # above grabs the FIRST such match in the document, which for
    # Symbility is a single room's own "<Room> - Subtotal $X" line, not
    # the real total - override with the actual final total when present.
    estimate_total_matches = re.findall(r'Estimate Total:\s*\$?([\d,]+\.\d{2})', text, re.IGNORECASE)
    if estimate_total_matches:
        total_value = float(estimate_total_matches[-1].replace(',', ''))
        summary['line_item_total'] = total_value
        summary['overhead'] = 0
        summary['profit'] = 0

    return summary


def extract_metadata(text, pdf_path):
    """Extract estimate metadata."""
    metadata = {
        'client': 'Unknown',
        'date': 'Unknown',
        'address': 'Unknown',
        'adjuster': 'Unknown',
        'has_paul_davis_header': bool(re.search(r'paul\s+davis', text, re.IGNORECASE))
    }

    # Try to extract metadata from text. "Insured: Name (phone)..." is a
    # clean, reliable pattern where it appears (e.g. THIG/Symbility desk
    # adjuster notes) - checked first. The generic fallback intentionally
    # excludes newlines from the connective whitespace: with a bare \s,
    # "...INSURED\nPolicy No.: W027828140 Ray Kwilos" (a two-column header
    # table, where "INSURED" is just a section label with no value on its
    # own line) would match across the line break and capture the WRONG
    # column's text as the client name.
    client_match = re.search(r'Insured:\s*([^\n(]+?)\s*(?:\(|\n)', text)
    if client_match:
        metadata['client'] = client_match.group(1).strip()
    else:
        client_match = re.search(r'(?:Insured|Name|Client)[ \t:]+(.+)', text, re.IGNORECASE)
        if client_match:
            metadata['client'] = client_match.group(1).strip()

    date_match = re.search(r'(?:Date|Estimate\s+Date)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
    if date_match:
        metadata['date'] = date_match.group(1).strip()

    address_match = re.search(r'(?:Address|Loss\s+Address)[ \t:]+(.+)', text, re.IGNORECASE)
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

        # Extract line items - Symbility/CoreLogic estimates (e.g. THIG/
        # CastleCare) use a completely different line-item layout than
        # Xactimate, so detect the format from the text itself rather than
        # assuming based on carrier, since other future carriers may also
        # use either platform.
        print("\nExtracting line items...")
        if is_symbility_format(full_text):
            print("Detected Symbility/CoreLogic format")
            line_items = extract_line_items_from_symbility_text(full_text, estimate_id)
        else:
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
