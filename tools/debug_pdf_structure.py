#!/usr/bin/env python3
"""Debug script to examine PDF structure."""

import sys
import pdfplumber

def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "CLAUDE_TEST_ABBREVIATED_CON.pdf"

    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF: {pdf_path}")
        print(f"Total pages: {len(pdf.pages)}\n")

        for page_num, page in enumerate(pdf.pages, start=1):
            print(f"=" * 80)
            print(f"PAGE {page_num}")
            print(f"=" * 80)

            # Extract tables
            tables = page.extract_tables()
            print(f"\nTables found: {len(tables)}")

            for table_num, table in enumerate(tables, start=1):
                print(f"\n--- Table {table_num} ---")
                print(f"Rows: {len(table)}")
                print(f"Columns: {len(table[0]) if table else 0}")

                # Show first few rows
                for row_idx, row in enumerate(table[:5]):
                    print(f"Row {row_idx}: {row}")

                if len(table) > 5:
                    print(f"... ({len(table) - 5} more rows)")

            # Also show some text
            text = page.extract_text()
            if text:
                lines = text.split('\n')[:10]
                print(f"\nFirst 10 text lines:")
                for i, line in enumerate(lines, 1):
                    print(f"{i}: {line}")

            print()

if __name__ == '__main__':
    main()
