"""
Run this once to generate .streamlit/secrets.toml for local dev
AND to print what to paste into Streamlit Cloud.

Usage:
    python generate_secrets.py
"""

import json, os, sys

CREDS_PATHS = ["creds.json", "../creds.json"]

def find_creds():
    for p in CREDS_PATHS:
        if os.path.exists(p):
            return p
    return None

def v(value):
    """Escape a value as a valid TOML string (JSON escaping is compatible)."""
    return json.dumps(str(value))   # returns "value" with surrounding quotes + proper escaping

def main():
    path = find_creds()
    if not path:
        print("ERROR: creds.json not found. Place it next to this script or one folder up.")
        sys.exit(1)

    with open(path) as f:
        c = json.load(f)

    sheet_id = input("Paste your Google Sheet ID (from the URL): ").strip()
    if not sheet_id:
        print("ERROR: Sheet ID is required.")
        sys.exit(1)

    toml = (
        "[gcp_service_account]\n"
        f"type                        = {v(c.get('type', ''))}\n"
        f"project_id                  = {v(c.get('project_id', ''))}\n"
        f"private_key_id              = {v(c.get('private_key_id', ''))}\n"
        f"private_key                 = {v(c.get('private_key', ''))}\n"
        f"client_email                = {v(c.get('client_email', ''))}\n"
        f"client_id                   = {v(c.get('client_id', ''))}\n"
        f"auth_uri                    = {v(c.get('auth_uri', ''))}\n"
        f"token_uri                   = {v(c.get('token_uri', ''))}\n"
        f"auth_provider_x509_cert_url = {v(c.get('auth_provider_x509_cert_url', ''))}\n"
        f"client_x509_cert_url        = {v(c.get('client_x509_cert_url', ''))}\n"
        f"\nspreadsheet_id = {v(sheet_id)}\n"
    )

    # Write local secrets.toml
    os.makedirs(".streamlit", exist_ok=True)
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    with open(secrets_path, "w") as f:
        f.write(toml)

    print(f"\n✓ Written to {secrets_path}")
    print("\n" + "=" * 60)
    print("STREAMLIT CLOUD — paste the following into the Secrets editor:")
    print("=" * 60)
    print(toml)

if __name__ == "__main__":
    main()
