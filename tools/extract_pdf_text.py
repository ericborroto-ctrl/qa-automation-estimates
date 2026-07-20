#!/usr/bin/env python3
"""Extract text from PDF to verify it's readable."""

import sys
import pdfplumber

def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "USAA_PDRP_Estimate_Guidelines_2026-02-25.pdf"

    print(f"Extracting text from: {pdf_path}\n")

    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}\n")

        # Check first 5 pages for text
        for page_num in range(min(5, len(pdf.pages))):
            page = pdf.pages[page_num]
            text = page.extract_text()

            print(f"=== PAGE {page_num + 1} ===")
            if text:
                # Show first 1000 characters
                print(text[:1000])
                print(f"\n... (Total characters: {len(text)})")
            else:
                print("(No text found - may be image-based PDF)")
            print("\n")

if __name__ == '__main__':
    main()
