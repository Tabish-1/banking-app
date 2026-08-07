#!/bin/bash
# Start the Django development server over HTTPS using a self-signed certificate.
# Access the application at: https://localhost:8000/webapps2026/
#
# This is the development entrypoint, so it opts into DEBUG explicitly. Settings
# default to production-safe values; nothing here should be used to deploy.
set -euo pipefail

cd "$(dirname "$0")"

export DJANGO_DEBUG="${DJANGO_DEBUG:-True}"

if [ ! -f certs/cert.pem ] || [ ! -f certs/key.pem ]; then
    echo "No certificate found — generating a self-signed pair in certs/ ..."
    mkdir -p certs
    openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
        -keyout certs/key.pem -out certs/cert.pem -subj "/CN=localhost"
fi

python3 manage.py runserver_plus \
    --cert-file certs/cert.pem \
    --key-file  certs/key.pem \
    0.0.0.0:8000
