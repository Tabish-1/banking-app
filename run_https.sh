#!/bin/bash
# Start the Django development server over HTTPS using a self-signed certificate.
# Access the application at: https://localhost:8000/webapps2026/
python3 manage.py runserver_plus \
    --cert-file certs/cert.pem \
    --key-file  certs/key.pem \
    0.0.0.0:8000
