#!/usr/bin/env python3
"""
Verify that each rule's guideline_reference page citation in a carrier rules
JSON actually matches where its reason text appears in the source guideline
PDF.

Carrier guideline PDFs (unlike scanned Xactimate estimates) are native-text
PDFs, so page text can be extracted exactly with pdfplumber rather than
relying on someone visually skimming rendered pages and manually transcribing
what a rule says - this catches citation drift automatically instead of
requiring a manual page-by-page check.

Usage:
    python verify_guideline_citations.py <carrier_rules_json> <guideline_pdf> [--min-score 60]
"""

import sys
import json
import re
from pathlib import Path
from fuzzywuzzy import fuzz
import pdfplumber


def load_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_page_texts(pdf_path):
    """Return a list of (page_number, text) tuples, 1-indexed."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ''
            pages.append((i + 1, text))
    return pages


def parse_declared_pages(guideline_reference):
    """Parse a 'guideline_reference' string like 'Page 12-13' into a set of ints."""
    if not guideline_reference:
        return set()
    numbers = re.findall(r'\d+', guideline_reference)
    if len(numbers) == 1:
        return {int(numbers[0])}
    if len(numbers) >= 2:
        return set(range(int(numbers[0]), int(numbers[-1]) + 1))
    return set()


def find_best_page(reason_text, page_texts):
    """Fuzzy-match reason_text against every page; return (best_page, best_score)."""
    best_page, best_score = None, 0
    for page_num, text in page_texts:
        if not text:
            continue
        score = fuzz.partial_ratio(reason_text.lower(), text.lower())
        if score > best_score:
            best_score = score
            best_page = page_num
    return best_page, best_score


def collect_rules(rules_json):
    """Yield (section, rule) for every rule with a reason and guideline_reference."""
    sections = [
        'disallowed_items', 'quantity_limits', 'overhead_profit_restrictions',
        'f9_note_requirements', 'observations'
    ]
    for section in sections:
        for rule in rules_json.get(section, []):
            if rule.get('reason') and rule.get('guideline_reference'):
                yield section, rule


def main():
    if len(sys.argv) < 3:
        print("Usage: python verify_guideline_citations.py <carrier_rules_json> <guideline_pdf> [--min-score 60]")
        sys.exit(1)

    rules_path = sys.argv[1]
    pdf_path = sys.argv[2]

    min_score = 60
    if '--min-score' in sys.argv:
        idx = sys.argv.index('--min-score')
        if idx + 1 < len(sys.argv):
            min_score = int(sys.argv[idx + 1])

    rules_json = load_json(rules_path)
    print(f"Extracting text from: {pdf_path}")
    page_texts = extract_page_texts(pdf_path)
    print(f"  {len(page_texts)} pages extracted\n")

    mismatches = []
    unmatched = []
    checked = 0

    for section, rule in collect_rules(rules_json):
        checked += 1
        rule_id = rule.get('rule_id', '?')
        declared = rule['guideline_reference']
        declared_pages = parse_declared_pages(declared)

        best_page, best_score = find_best_page(rule['reason'], page_texts)

        if best_score < min_score:
            unmatched.append((section, rule_id, declared, best_page, best_score))
            print(f"[?] {rule_id} ({section}): no confident match anywhere "
                  f"(best guess page {best_page} at {best_score}%, declared {declared})")
        elif best_page not in declared_pages:
            mismatches.append((section, rule_id, declared, best_page, best_score))
            print(f"[X] {rule_id} ({section}): declared '{declared}' but reason text "
                  f"actually matches page {best_page} ({best_score}%)")
        else:
            print(f"[OK] {rule_id} ({section}): page {declared} confirmed ({best_score}%)")

    print(f"\nChecked {checked} rules: {len(mismatches)} wrong citations, "
          f"{len(unmatched)} with no confident match, "
          f"{checked - len(mismatches) - len(unmatched)} confirmed correct.")

    if mismatches:
        print("\nSuggested fixes:")
        for section, rule_id, declared, best_page, score in mismatches:
            print(f"  {rule_id}: '{declared}' -> 'Page {best_page}'")

    sys.exit(1 if mismatches else 0)


if __name__ == '__main__':
    main()
