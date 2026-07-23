"""
Estimate QA Automation - Streamlit Web App

This web application allows users to upload Xactimate estimate PDFs and receive
automated QA validation reports based on carrier guidelines.
"""

import streamlit as st
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
import shutil

# Page config
st.set_page_config(
    page_title="Estimate QA Automation",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #C9A961;
        text-align: center;
        letter-spacing: 1px;
        padding: 1.25rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0.5rem;
        background: linear-gradient(135deg, #000000, #2b2b2b);
        border: 1px solid #96742F;
    }
    .main-subheader {
        text-align: center;
        color: #D9D9D9;
        letter-spacing: 2px;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-top: -0.5rem;
        margin-bottom: 1.5rem;
    }
    h2, h3 {
        color: #FFFFFF !important;
        border-bottom: 2px solid #C9A961;
        padding-bottom: 0.3rem;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #1A1A1A;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #1F1F1F;
        border: 1px solid #96742F;
        color: #FFFFFF;
        margin: 1rem 0;
    }
    .brand-footer {
        text-align: center;
        color: #D9D9D9;
        padding: 1.5rem 1rem;
        border-radius: 0.5rem;
        background: linear-gradient(135deg, #000000, #2b2b2b);
        border: 1px solid #96742F;
    }
    .brand-footer strong { color: #C9A961; }
    .alert-legend-row {
        display: flex;
        align-items: flex-start;
        gap: 0.6rem;
        margin: 0.5rem 0;
    }
    .alert-badge {
        flex-shrink: 0;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 1rem;
    }
    .alert-legend-text b { display: block; color: #FFFFFF; }
    .alert-legend-text span { color: #B3B3B3; font-size: 0.85rem; }
    .alert-summary-card {
        border-radius: 0.5rem;
        padding: 1rem;
        text-align: center;
        border: 1px solid;
    }
    .alert-summary-count { font-size: 2rem; font-weight: bold; }
    .alert-summary-label { font-weight: 600; margin-top: 0.25rem; color: #1A1A1A; }
    .alert-summary-sub { font-size: 0.8rem; color: #555555; }
    </style>
""", unsafe_allow_html=True)

# Alert type definitions - mirrors Xactimate's own QA scrub taxonomy so
# results read consistently with what estimators already know: Violations
# must be resolved in the estimate, Warnings can be resolved with a note
# explaining why the flagged item is justified, Cautions are informational.
ALERT_TYPES = {
    'violation': {'color': '#dc3545', 'bg': '#f8d7da', 'symbol': '!', 'label': 'Violation',
                  'description': "Must be resolved inside the estimate."},
    'warning': {'color': '#e67e22', 'bg': '#fdebd0', 'symbol': '!', 'label': 'Warning',
                'description': "Can be resolved, or explained with a line-item note."},
    'caution': {'color': '#f0ad4e', 'bg': '#fff3cd', 'symbol': 'i', 'label': 'Caution',
                'description': "Worth noting, but no action is required."},
}


def alert_badge_html(kind):
    a = ALERT_TYPES[kind]
    return f'<div class="alert-badge" style="background-color:{a["color"]};">{a["symbol"]}</div>'


def render_alert_legend():
    st.markdown("#### Alerts")
    st.caption("Alerts make it easier to find what and where problems are and how to fix them, using rules in the estimate.")
    for kind in ('violation', 'warning', 'caution'):
        a = ALERT_TYPES[kind]
        st.markdown(
            f'<div class="alert-legend-row">{alert_badge_html(kind)}'
            f'<div class="alert-legend-text"><b>{a["label"]}</b><span>{a["description"]}</span></div></div>',
            unsafe_allow_html=True
        )


def render_alert_summary(violations, warnings, cautions):
    cols = st.columns(3)
    counts = {'violation': violations, 'warning': warnings, 'caution': cautions}
    for col, kind in zip(cols, ('violation', 'warning', 'caution')):
        a = ALERT_TYPES[kind]
        with col:
            st.markdown(
                f'<div class="alert-summary-card" style="background-color:{a["bg"]};border-color:{a["color"]};">'
                f'{alert_badge_html(kind)}'
                f'<div class="alert-summary-count" style="color:{a["color"]};">{counts[kind]}</div>'
                f'<div class="alert-summary-label">{a["label"]}s</div>'
                f'<div class="alert-summary-sub">{a["description"]}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

# Initialize session state
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'report_path' not in st.session_state:
    st.session_state.report_path = None

# Header
st.markdown('<div class="main-header">🔍 Estimate QA Automation</div>', unsafe_allow_html=True)
st.markdown('<div class="main-subheader">Paul Davis &bull; Property Restoration Experts</div>', unsafe_allow_html=True)
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")

    carrier = st.selectbox(
        "Select Carrier",
        ["USAA", "Allstate"],
        help="Choose the insurance carrier for validation"
    )

    st.markdown("---")

    st.header("📊 System Info")
    st.markdown("""
    <div class="info-box">
    <b>Status:</b> ✅ Ready<br><br>
    <b>Features:</b>
    <ul style="margin:0.25rem 0 0 0; padding-left: 1.1rem;">
    <li>OCR support for scanned PDFs</li>
    <li>Carrier-specific validation</li>
    <li>F9 note recommendations</li>
    <li>Professional PDF reports</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    st.header("📖 How to Use")
    st.markdown("""
    1. Upload estimate PDF
    2. Select carrier
    3. Click 'Run QA Analysis'
    4. Download report
    """)

    st.markdown("---")

    render_alert_legend()

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📤 Upload Estimate")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload a Xactimate estimate PDF for QA validation"
    )

with col2:
    if uploaded_file:
        st.metric("File Name", uploaded_file.name)
        st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")

# Process file
if uploaded_file:
    # Save uploaded file
    upload_dir = Path(".tmp/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = upload_dir / uploaded_file.name

    with open(pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success(f"✅ File uploaded successfully: {uploaded_file.name}")

    # Run analysis button
    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        run_button = st.button(
            "🚀 Run QA Analysis",
            type="primary",
            use_container_width=True
        )

    if run_button:
        st.session_state.processed = False
        st.session_state.report_path = None

        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            # Step 1: Extract line items
            status_text.text("📄 Step 1/4: Extracting line items from PDF...")
            progress_bar.progress(25)

            result = subprocess.run(
                [sys.executable, "tools/extract_estimate_with_ocr.py", str(pdf_path)],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0:
                st.error(f"❌ Error extracting line items:\n{result.stderr}")
                st.stop()

            # Get estimate JSON path
            estimate_id = pdf_path.stem
            estimate_json = Path(".tmp/estimates") / f"{estimate_id}_line_items.json"

            if not estimate_json.exists():
                st.error("❌ Failed to extract line items from PDF")
                st.stop()

            # Load and display summary
            with open(estimate_json) as f:
                estimate_data = json.load(f)

            st.success(f"✅ Extracted {len(estimate_data['line_items'])} line items")

            # Step 2: Run validations
            status_text.text("🔍 Step 2/4: Validating against carrier guidelines...")
            progress_bar.progress(50)

            rules_path = Path(".tmp/carriers") / f"{carrier.lower().replace(' ', '_')}_rules.json"

            if not rules_path.exists():
                st.error(f"❌ Carrier rules not found for {carrier}")
                st.stop()

            # Run all validations
            validations = [
                ("check_disallowed_items.py", "Disallowed Items"),
                ("check_f9_notes.py", "F9 Notes"),
                ("check_observations.py", "Observations"),
                ("check_quantity_limits.py", "Quantity Limits")
            ]

            validation_results = {}

            for script, name in validations:
                result = subprocess.run(
                    [sys.executable, f"tools/{script}", str(estimate_json), str(rules_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode == 0:
                    validation_results[name] = "✅ Passed"
                else:
                    validation_results[name] = "⚠️ Issues found"

            st.success("✅ Validation complete")

            # Step 3: Load results
            status_text.text("📊 Step 3/4: Analyzing results...")
            progress_bar.progress(75)

            # Load issue counts
            issues_dir = Path(".tmp/issues")

            disallowed_file = issues_dir / f"disallowed_{estimate_id}.json"
            quantities_file = issues_dir / f"quantities_{estimate_id}.json"
            f9_notes_file = issues_dir / f"f9_notes_{estimate_id}.json"
            observations_file = issues_dir / f"observations_{estimate_id}.json"

            disallowed_count = 0
            quantities_count = 0
            f9_count = 0
            obs_count = 0

            if disallowed_file.exists():
                with open(disallowed_file) as f:
                    disallowed_count = json.load(f).get('issues_found', 0)

            if quantities_file.exists():
                with open(quantities_file) as f:
                    quantities_count = json.load(f).get('issues_found', 0)

            if f9_notes_file.exists():
                with open(f9_notes_file) as f:
                    f9_count = json.load(f).get('f9_notes_required', 0)

            if observations_file.exists():
                with open(observations_file) as f:
                    obs_count = json.load(f).get('observations_found', 0)

            # Violations = things the carrier won't allow (disallowed items,
            # quantity limits exceeded) - must be resolved in the estimate.
            # Warnings = things that need a line-item note to justify them
            # (F9 note requirements) - resolvable with a good note.
            # Cautions = worth reviewing, no action required (observations).
            violations_count = disallowed_count + quantities_count
            warnings_count = f9_count
            cautions_count = obs_count

            # Display results
            st.markdown("### 📊 Validation Results")
            render_alert_summary(violations_count, warnings_count, cautions_count)

            # Step 4: Generate PDF report
            status_text.text("📄 Step 4/4: Generating PDF report...")
            progress_bar.progress(90)

            result = subprocess.run(
                [sys.executable, "tools/generate_pdf_report.py", str(estimate_json), str(issues_dir)],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                st.error(f"❌ Error generating report:\n{result.stderr}")
                st.stop()

            # Find the generated report
            date_str = datetime.now().strftime('%Y%m%d')
            report_path = Path(".tmp/reports") / f"qa_report_{estimate_id}_{date_str}.pdf"

            if not report_path.exists():
                # Try without date
                reports = list(Path(".tmp/reports").glob(f"qa_report_{estimate_id}*.pdf"))
                if reports:
                    report_path = reports[-1]  # Get most recent

            if report_path.exists():
                st.session_state.report_path = report_path
                st.session_state.processed = True
                progress_bar.progress(100)
                status_text.text("✅ Analysis complete!")
            else:
                st.error("❌ Report generation failed")
                st.stop()

        except subprocess.TimeoutExpired:
            st.error("❌ Processing timeout - estimate may be too large")
            st.stop()
        except Exception as e:
            st.error(f"❌ Error during processing: {str(e)}")
            st.stop()

# Show download button if processed
if st.session_state.processed and st.session_state.report_path:
    st.markdown("---")
    st.markdown("### 🎉 Report Ready!")

    with open(st.session_state.report_path, "rb") as f:
        pdf_data = f.read()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.download_button(
            label="📥 Download QA Report (PDF)",
            data=pdf_data,
            file_name=f"QA_Report_{uploaded_file.name if uploaded_file else 'estimate'}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )

    st.success("✅ Report generated successfully! Click above to download.")

# Footer
st.markdown("---")
st.markdown("""
<div class="brand-footer">
    <p><strong>Paul Davis &bull; QA Reconstruction Estimate Automation System</strong></p>
    <p>Automated validation against carrier guidelines | Powered by OCR & AI</p>
</div>
""", unsafe_allow_html=True)
