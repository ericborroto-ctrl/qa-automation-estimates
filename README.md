# USAA Estimate QA Automation

Automated QA validation for Xactimate reconstruction estimates against insurance carrier guidelines.

## Features

- 🔍 **Automated Line Item Extraction** - OCR support for scanned PDFs
- ✅ **Carrier-Specific Validation** - USAA, State Farm guidelines
- 📝 **F9 Note Recommendations** - Suggested documentation text
- 📊 **Professional PDF Reports** - Detailed validation reports
- 🌐 **Web Interface** - Access from any browser

## Quick Start (Local)

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR:
```bash
winget install UB-Mannheim.TesseractOCR
```

3. Run the web app:
```bash
streamlit run app.py
```

4. Open your browser to: http://localhost:8501

## Deployment to Streamlit Cloud

1. Push this repo to GitHub
2. Go to https://share.streamlit.io
3. Sign in with GitHub
4. Click "New app"
5. Select your repository
6. Set main file: app.py
7. Deploy!

## Usage

1. Upload an estimate PDF
2. Select carrier (USAA or State Farm)
3. Click "Run QA Analysis"
4. Download the PDF report
