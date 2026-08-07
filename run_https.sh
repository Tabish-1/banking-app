#!/bin/bash
# Start the Django development server over HTTPS using a self-signed certificate.
# Access the application at: https://localhost:8000/webapps2026/
#
# This is the development entrypoint, so it opts into DEBUG explicitly. Settings
# default to production-safe values; nothing here should be used to deploy.
set -euo pipefail

cd "$(dirname "$0")"

export DJANGO_DEBUG="${DJANGO_DEBUG:-True}"

# Prefer the project's virtualenv if it exists, so the script works whether or
# not it has been activated. A Windows venv puts the interpreter in Scripts/
# and provides no `python3` alias, which is why this is not just `python3`.
if [ -n "${PYTHON:-}" ]; then          : # honour an explicit override
elif [ -x venv/bin/python ];         then PYTHON=venv/bin/python
elif [ -x venv/Scripts/python.exe ]; then PYTHON=venv/Scripts/python.exe
elif command -v python3 >/dev/null 2>&1; then PYTHON=python3
elif command -v python  >/dev/null 2>&1; then PYTHON=python
else
    echo "No Python interpreter found. Create a virtualenv first:" >&2
    echo "  python3 -m venv venv && venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

if [ ! -f certs/cert.pem ] || [ ! -f certs/key.pem ]; then
    echo "No certificate found — generating a self-signed pair in certs/ ..."
    mkdir -p certs
    # MSYS_NO_PATHCONV stops Git Bash on Windows rewriting the /CN=... subject
    # into a filesystem path. It is simply ignored on macOS and Linux.
    MSYS_NO_PATHCONV=1 openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
        -keyout certs/key.pem -out certs/cert.pem -subj "/CN=localhost" 2>/dev/null
    echo "Certificate written to certs/ (expires in 365 days)."
fi

"$PYTHON" manage.py runserver_plus \
    --cert-file certs/cert.pem \
    --key-file  certs/key.pem \
    0.0.0.0:8000
