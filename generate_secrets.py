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

def main():
    path = find_creds()
    if not path:
        print("ERROR: creds.json not found. Place it next to this script or one folder up.")
        sys.exit(1)

    with open(path) as f:
        c = json.load(f)

    # Ask for spreadsheet ID
    sheet_id = input("Paste your Google Sheet ID (from the URL): ").strip()
    if not sheet_id:
        print("ERROR: Sheet ID is required.")
        sys.exit(1)

    # Escape private key for TOML (replace literal \n with \\n for toml string)
    private_key = c.get("private_key", "").replace("\n", "\\n")

    toml = f'''[gcp_service_account]
type                        = "{c.get('type', '')}"
project_id                  = "{c.get('project_id', '')}"
private_key_id              = "{c.get('private_key_id', '')}"
private_key                 = "{private_key}"
client_email                = "{c.get('client_email', '')}"
client_id                   = "{c.get('client_id', '')}"
auth_uri                    = "{c.get('auth_uri', '')}"
token_uri                   = "{c.get('token_uri', '')}"
auth_provider_x509_cert_url = "{c.get('auth_provider_x509_cert_url', '')}"
client_x509_cert_url        = "{c.get('client_x509_cert_url', '')}"

spreadsheet_id = "{sheet_id}"
'''

    # Write local secrets.toml
    os.makedirs(".streamlit", exist_ok=True)
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    with open(secrets_path, "w") as f:
        f.write(toml)

    print(f"\n✓ Written to {secrets_path}")
    print("\n" + "="*60)
    print("STREAMLIT CLOUD — paste the following into the Secrets editor:")
    print("="*60)
    print(toml)

if __name__ == "__main__":
    main()
