"""
Generates secrets.toml from creds.json.
Run once:  python generate_secrets.py
"""

import json, os, sys, subprocess

CREDS_PATHS = ["creds.json", "../creds.json"]

def find_creds():
    for p in CREDS_PATHS:
        if os.path.exists(p):
            return p
    return None

def v(value):
    # json.dumps produces a properly-escaped TOML-compatible quoted string
    return json.dumps(str(value))

def main():
    path = find_creds()
    if not path:
        print("ERROR: creds.json not found.")
        sys.exit(1)

    with open(path) as f:
        c = json.load(f)

    sheet_id = input("Paste your Google Sheet ID (from the sheet URL): ").strip()
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

    # Write .streamlit/secrets.toml (for local dev)
    os.makedirs(".streamlit", exist_ok=True)
    local_path = os.path.join(".streamlit", "secrets.toml")
    with open(local_path, "w") as f:
        f.write(toml)

    # Write a plain copy for Streamlit Cloud — open it in Notepad
    cloud_path = os.path.abspath("streamlit_cloud_secrets.txt")
    with open(cloud_path, "w") as f:
        f.write(toml)

    print(f"\n✓ Done!")
    print(f"  Local dev  → {local_path}")
    print(f"  Cloud copy → {cloud_path}  (opening in Notepad...)\n")
    print("Copy everything from Notepad and paste into:")
    print("Streamlit Cloud → App settings → Secrets → Save\n")

    # Open the file in Notepad so user can Ctrl+A, Ctrl+C
    try:
        subprocess.Popen(["notepad.exe", cloud_path])
    except Exception:
        print(f"(Open {cloud_path} manually and copy its contents)")

if __name__ == "__main__":
    main()
