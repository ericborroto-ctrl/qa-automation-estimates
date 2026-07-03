# Work PC Setup Guide

## One-Time Setup on Work Computer

### 1. Install Git
1. Go to: https://git-scm.com/download/win
2. Download and install with default settings
3. Verify: Open Command Prompt and type `git --version`

### 2. Install Python
1. Go to: https://www.python.org/downloads/
2. Download Python 3.11 or later
3. **IMPORTANT:** During installation, check ✅ "Add Python to PATH"
4. Verify: Open Command Prompt and type `python --version`

### 3. Install VS Code (Optional but Recommended)
1. Go to: https://code.visualstudio.com/
2. Download and install
3. Install Python extension from Extensions panel

### 4. Install Tesseract OCR
1. Open Command Prompt as Administrator
2. Run: `winget install UB-Mannheim.TesseractOCR`
3. Or download from: https://github.com/UB-Mannheim/tesseract/wiki

### 5. Clone Your Project from GitHub
1. Open Command Prompt or PowerShell
2. Navigate to where you want the project (e.g., `cd Desktop`)
3. Run:
   ```bash
   git clone https://github.com/ericborroto-ctrl/qa-automation-estimates.git
   cd qa-automation-estimates
   ```

### 6. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 7. Configure Git (First Time Only)
```bash
git config --global user.email "eric.borroto@pauldavis.com"
git config --global user.name "Eric Borroto"
```

---

## Running the App Locally

### Start the Web App:
```bash
streamlit run app.py
```

Your browser will open to: http://localhost:8501

### Stop the App:
Press `Ctrl+C` in the terminal

---

## Working Between Home & Work PCs

### Before You Start Working:
**Always pull the latest changes first!**
```bash
git pull
```

### After Making Changes:
**Commit and push your changes:**
```bash
git add .
git commit -m "Brief description of what you changed"
git push
```

### Example Workflow:

**At Work:**
1. `git pull` (get latest from home)
2. Make changes to code
3. Test: `streamlit run app.py`
4. `git add .`
5. `git commit -m "Added new feature"`
6. `git push`

**At Home:**
1. `git pull` (get changes from work)
2. Continue working
3. `git push` when done

**Remember:** Always `git pull` before starting work!

---

## Live App URL

**Production App (works from anywhere):**
https://app-automation-estimates-e59qqb4dgs3yimlywqvopd.streamlit.app/

- No installation needed
- Works from any computer
- Sleeps after 15 minutes (takes 30-60 seconds to wake up)
- Load it 1-2 minutes before demos/meetings

---

## Making Changes & Deploying

### How Changes Get Deployed:

1. **Make changes locally** (VS Code on home or work PC)
2. **Test locally**: `streamlit run app.py`
3. **Commit changes**: `git add .` → `git commit -m "message"` → `git push`
4. **Streamlit Cloud auto-deploys** (2-5 minutes)
5. **Your URL stays the same** - just refresh to see changes

### You NEVER edit code on Streamlit Cloud
All development happens locally, then push to GitHub!

---

## Common Git Commands

```bash
# See what files changed
git status

# See recent commits
git log --oneline

# Undo uncommitted changes to a file
git checkout -- filename.py

# Pull latest changes
git pull

# Push your changes
git push
```

---

## Troubleshooting

### "Repository not found" when pushing:
Check your remote URL:
```bash
git remote -v
```
Should show: `https://github.com/ericborroto-ctrl/qa-automation-estimates.git`

### Merge conflicts:
1. Open the conflicted file
2. Look for `<<<<<<<`, `=======`, `>>>>>>>` markers
3. Edit to keep what you want
4. Remove the markers
5. `git add .` → `git commit` → `git push`

### Streamlit app not updating:
1. Check GitHub - did your push succeed?
2. Go to Streamlit Cloud → "Manage app" → "Reboot"

---

## Need Help?

1. Check this guide
2. Check GitHub: https://github.com/ericborroto-ctrl/qa-automation-estimates
3. Ask Claude Code for help!

---

## Project Structure

```
qa-automation-estimates/
├── app.py                          # Main Streamlit web app
├── requirements.txt                # Python dependencies
├── packages.txt                    # System dependencies (Tesseract)
├── .streamlit/config.toml         # Streamlit configuration
├── tools/                         # QA validation scripts
│   ├── extract_estimate_with_ocr.py
│   ├── check_disallowed_items.py
│   ├── check_f9_notes.py
│   ├── check_observations.py
│   └── generate_pdf_report.py
└── .tmp/carriers/                 # Carrier rules (USAA, State Farm)
    ├── usaa_rules.json
    └── state_farm_rules.json
```

---

**Questions?** Email yourself at: eric.borroto@pauldavis.com
