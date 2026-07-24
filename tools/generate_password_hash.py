#!/usr/bin/env python3
"""
Generate a bcrypt password hash to paste into .streamlit/secrets.toml.

Usage:
    python tools/generate_password_hash.py

Prompts for a password (hidden input) and prints the hash to paste in as
that user's "password" value. Never paste the plaintext password itself
into secrets.toml - only the hash this script prints.
"""

import getpass
import streamlit_authenticator as stauth


def main():
    password = getpass.getpass("Enter the new password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords didn't match - try again.")
        return

    if not password:
        print("Password can't be empty.")
        return

    hashed = stauth.Hasher.hash(password)
    print("\nAdd this as the user's password in .streamlit/secrets.toml:\n")
    print(hashed)


if __name__ == "__main__":
    main()
