# QA Estimate Review Workflow

## Objective
Compare Xactimate reconstruction estimates against insurance carrier guidelines to identify disallowed items, depreciation errors, and quantity limit violations. Generate an actionable report with specific recommendations for estimate adjustments.

## Required Inputs
1. **Estimate PDF**: Xactimate export in standard format (text-based, not scanned)
2. **Carrier Name**: Insurance company for this claim (e.g., "State Farm", "Allstate", "USAA")
3. **Carrier Guidelines**: Pre-loaded JSON rules file in `.tmp/carriers/[carrier]_rules.json`

## Tools Used
1. `tools/extract_estimate_line_items.py` - Parse Xactimate PDF and extract line items
2. `tools/check_disallowed_items.py` - Validate line items against disallowed materials list
3. `tools/check_quantity_limits.py` - Verify quantities don't exceed carrier maximums
4. `tools/generate_qa_report.py` - Create consolidated markdown report

## Step-by-Step Process

### Step 1: Extract Estimate Data

**Command:**
```bash
python tools/extract_estimate_line_items.py "<estimate_pdf_path>"
```

**What it does:**
- Parses the Xactimate PDF
- Extracts all line items with descriptions, quantities, units, prices, and totals
- Extracts summary totals (line item total, overhead, profit, RCV)
- Extracts metadata (client name, date, etc.)

**Output:**
- JSON file: `.tmp/estimates/<estimate_id>_line_items.json`

**Verification:**
- Check that line items were extracted (should show "Line items extracted: X" where X > 0)
- If 0 line items extracted, PDF format may not be supported - check PDF structure with `debug_pdf_structure.py`

---

### Step 2: Check for Disallowed Items

**Command:**
```bash
python tools/check_disallowed_items.py ".tmp/estimates/<estimate_id>_line_items.json" ".tmp/carriers/state_farm_rules.json"
```

**What it does:**
- Loads estimate line items and carrier disallowed items rules
- Uses fuzzy matching to identify line items that match disallowed patterns
- Calculates confidence scores for each match
- Flags items for removal, review, or manual inspection

**Output:**
- JSON file: `.tmp/issues/disallowed_<estimate_id>.json`
- Console output showing issues found with confidence levels

**Verification:**
- Review flagged items and confidence scores
- High confidence (>90%) = likely violation
- Medium confidence (70-90%) = review with adjuster
- Adjust confidence threshold if too many false positives

---

### Step 3: Check for Quantity Limit Violations

**Command:**
```bash
python tools/check_quantity_limits.py ".tmp/estimates/<estimate_id>_line_items.json" ".tmp/carriers/state_farm_rules.json"
```

**What it does:**
- Loads estimate line items and carrier quantity limit rules
- Checks for paint coat counts (1 coat vs 2 coat limits)
- Validates quantities against carrier-approved maximums
- Flags items that exceed limits with excess amounts

**Output:**
- JSON file: `.tmp/issues/quantities_<estimate_id>.json`
- Console output showing violations with excess amounts

**Verification:**
- Review flagged items and excess quantities
- Check if exceptions apply (e.g., smoke damage warranting extra sealing)
- Consult carrier guidelines for clarification if needed

---

### Step 4: Generate QA Report

**Command:**
```bash
python tools/generate_qa_report.py ".tmp/estimates/<estimate_id>_line_items.json" ".tmp/issues"
```

**What it does:**
- Consolidates all validation issues from Steps 2 and 3
- Generates a comprehensive markdown report with:
  - Summary of issues found
  - Detailed breakdown of each issue
  - Specific recommendations (remove, adjust, review)
  - Cost impact analysis
  - Revised estimate total

**Output:**
- Markdown report: `.tmp/reports/qa_report_<estimate_id>_<date>.md`

**Verification:**
- Read the report to ensure all issues are captured
- Verify recommendations are actionable
- Check that cost calculations are correct

---

## Expected Outputs

**After completing all steps:**

1. **Extracted Data** (`.tmp/estimates/`)
   - `<estimate_id>_line_items.json` - Structured line item data

2. **Validation Issues** (`.tmp/issues/`)
   - `disallowed_<estimate_id>.json` - Disallowed items violations
   - `quantities_<estimate_id>.json` - Quantity limit violations

3. **Final Report** (`.tmp/reports/`)
   - `qa_report_<estimate_id>_<date>.md` - Comprehensive QA report

**Report includes:**
- Total issues found (by category)
- Original estimate total
- Detailed issue breakdown with line item references
- Specific recommendations for each issue
- Total recommended adjustment amount
- Revised estimate total

---

## Edge Cases & Troubleshooting

### Issue: No line items extracted (0 items)

**Symptom:** `extract_estimate_line_items.py` returns 0 line items

**Possible Causes:**
- PDF is scanned/image-based (not text-based)
- Xactimate export format is different from expected
- PDF has non-standard line item format

**Solutions:**
1. Run `python tools/debug_pdf_structure.py "<pdf_path>"` to examine PDF structure
2. Check if PDF has text layer (open in PDF reader and try to select text)
3. If scanned, PDF needs OCR processing first (future feature)
4. If format is different, adjust extraction regex pattern in tool

---

### Issue: Too many false positives in disallowed items

**Symptom:** Many items flagged that shouldn't be violations

**Solutions:**
1. Adjust confidence threshold: Run with `--confidence 85` to require higher matches
2. Review carrier rules JSON - patterns may be too broad
3. Refine item patterns in `state_farm_rules.json` to be more specific
4. Add exceptions or category filters to rules

---

### Issue: Missing carrier guidelines

**Symptom:** Error "Guidelines file not found"

**Solution:**
1. Check if `.tmp/carriers/<carrier>_rules.json` exists
2. If missing, create using template from existing rules file
3. Populate with carrier-specific rules (see State Farm rules as example)
4. One-time setup per carrier, reusable for all estimates

---

### Issue: Line item descriptions unclear or abbreviated

**Symptom:** Validation misses issues because descriptions don't match patterns

**Solutions:**
1. Expand item patterns in carrier rules to include abbreviations
2. Add category-based matching (e.g., flag all "heavy texture" in DRYWALL category)
3. Use fuzzy matching confidence scores - lower threshold may catch more variants
4. Manually review low-confidence flags for missed issues

---

## Example: Full Workflow Run

```bash
# Navigate to project directory
cd "c:\Users\EABor\Desktop\Claude\Agentic work flows\QA recon estimates"

# Step 1: Extract estimate data
python tools/extract_estimate_line_items.py "CLAUDE_TEST_ABBREVIATED_CON.pdf"
# Output: Line items extracted: 8

# Step 2: Check disallowed items
python tools/check_disallowed_items.py ".tmp/estimates/ABBREVIATED_line_items.json" ".tmp/carriers/state_farm_rules.json"
# Output: Issues found: 1

# Step 3: Check quantity limits
python tools/check_quantity_limits.py ".tmp/estimates/ABBREVIATED_line_items.json" ".tmp/carriers/state_farm_rules.json"
# Output: Issues found: 0

# Step 4: Generate report
python tools/generate_qa_report.py ".tmp/estimates/ABBREVIATED_line_items.json" ".tmp/issues"
# Output: Report generated successfully!

# Review the report
# Open: .tmp/reports/qa_report_ABBREVIATED_<date>.md
```

**Result:**
- Report shows 1 issue: "Texture drywall - heavy hand texture" ($436.80)
- Recommendation: Remove line item
- Revised estimate: $3,318.26 → $2,857.07 (savings of $436.80)

---

## Rate Limits / Constraints

- **None** - All processing is local, no API calls
- **PDF Size**: Large PDFs (100+ pages) may be slow to parse - consider pagination if needed
- **Carrier Rules**: JSON files are loaded into memory - keep rules under 10MB per carrier

---

## Success Criteria

✓ **All line items extracted correctly** (100% capture rate on standard Xactimate PDFs)
✓ **Issues identified match manual review** (spot-check validation against carrier guidelines)
✓ **Report is actionable** (clear recommendations with line-item references)
✓ **Processing time under 1 minute** per estimate (typical 10-20 line item estimate)

---

## Future Enhancements (Phase 2+)

- **Depreciation validation** - Add `check_depreciation_rules.py` with age-based calculations
- **Multi-carrier comparison** - Run estimate against multiple carriers simultaneously
- **Batch processing** - Process multiple estimates in one workflow run
- **Google Sheets export** - Automatic upload of reports to cloud spreadsheet
- **Format validator** - Pre-flight check to ensure PDF is parseable before processing
- **Automated guideline extraction** - Semi-automated parsing of carrier PDF guidelines

---

## Notes

- **Carrier rules must be current**: Review and update `.tmp/carriers/<carrier>_rules.json` quarterly
- **Always verify recommendations**: This tool assists with QA, but final decisions require human judgment
- **Keep audit trail**: `.tmp/` files serve as audit trail - archive before cleanup
- **One-time setup per carrier**: Creating rules JSON is 1-2 hour investment, then reusable for all estimates

---

*Last updated: 2026-02-15*
*WAT Framework - Workflows, Agents, Tools*
