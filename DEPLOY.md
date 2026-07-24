# Deploy in 3 Easy Steps

## Step 0: Set Up Login (do this first, once)

The app requires a username and password - nobody can use it without one.
Credentials are never stored in the code, so this step is required no matter
which option below you use.

1. **Copy the template:**
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
   - This new file is git-ignored - it never gets uploaded/shared, it's local to wherever the app runs

2. **Generate a password hash for each person:**
   ```
   python tools/generate_password_hash.py
   ```
   Type the person's password when prompted - it prints back a hash (starts with `$2b$`).

3. **Edit `.streamlit/secrets.toml`:**
   - Add one `[auth.credentials.usernames.THEIRUSERNAME]` block per person (copy the pattern already in the file)
   - Paste in their name, email, and the hash from step 2 (never the plaintext password)
   - Change `cookie_key` to any random string of your choosing

4. **If hosting on Streamlit Cloud (Option 2 below):** instead of the file, paste
   the same contents into your app's **Settings -> Secrets** box in the
   Streamlit Cloud dashboard - the file and the dashboard box work identically.

To add or remove a person later, just edit that file (or the Secrets box) -
no code changes needed.

---

## Option 1: Share via OneDrive/Google Drive (Easiest)

1. **Zip this entire folder**
   - Right-click the folder → Send to → Compressed (zipped) folder

2. **Upload to OneDrive/Google Drive**

3. **At the office/meeting:**
   - Download and unzip
   - Double-click: `streamlit run app.py`
   - Browser opens automatically!

**Time:** 5 minutes
**Internet needed:** Only for download
**Installation at office:** Python + Tesseract (one-time, 10 minutes)

---

## Option 2: Host Online (Best for demos)

### What you get:
A permanent URL like: `https://qa-automation.streamlit.app`
- Works from ANY computer
- Works from phones/tablets
- NO installation needed
- Just share the link!

### How to do it:

1. **Go to:** https://share.streamlit.io
2. **Sign in** with Google or GitHub
3. **Upload these files when asked:**
   - app.py
   - requirements.txt
   - packages.txt
   - tools/ folder
   - .tmp/carriers/ folder

4. **Click Deploy**

5. **Get your URL** - share it with anyone!

**Time:** 15 minutes
**Cost:** FREE
**Best for:** Professional demos, team access

---

## Which Should You Use?

**For your upcoming meeting:**
- Option 1 if it's next week (quick and easy)
- Option 2 if you have a few days (most impressive)

**Need help?** Just tell me which option you want and I'll walk you through it step by step.
