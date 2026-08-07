# WebApps 2026

[![CI](https://github.com/Tabish-1/banking-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Tabish-1/banking-app/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![Django 4.2](https://img.shields.io/badge/django-4.2-092E20)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A peer-to-peer payment web application built with Django. Users can send and request money from each other with automatic currency conversion between GBP, USD, and EUR.

## Features

- User registration and authentication
- Send payments to other users by email address
- Request payments from other users
- Accept or reject incoming payment requests
- Currency conversion via an internal REST service
- Notification system for all payment activity
- Admin dashboard for managing users and viewing all transactions

## Tech Stack

- Python / Django 4.2
- SQLite (development database)
- Bootstrap 5 via django-crispy-forms
- HTTPS via django-extensions / Werkzeug + self-signed certificate

## Project Structure

```
webapps2026/
├── conversionservice/   # Internal REST API for currency conversion
│   ├── rates.py         #   the rate table — single source of truth
│   ├── client.py        #   how the rest of the project consumes the service
│   └── views.py         #   the HTTP endpoint
├── payapp/              # Core payment logic, transactions, notifications
├── register/            # User registration and profile management
├── templates/           # HTML templates
├── static/              # CSS and static assets
└── webapps2026/         # Django project settings and URL config
```

## Getting Started

**Prerequisites:** Python 3.10 or newer. Nothing else — the database is SQLite and is created for you.

### macOS / Linux

```bash
git clone https://github.com/Tabish-1/banking-app.git
cd banking-app

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # sets DJANGO_DEBUG=True for local work
python manage.py migrate

./run_https.sh                # generates a self-signed certificate on first run
```

### Windows (PowerShell)

```powershell
git clone https://github.com/Tabish-1/banking-app.git
cd banking-app

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
python manage.py migrate

# run_https.sh needs a bash shell. In PowerShell, use plain HTTP instead —
# first set DJANGO_USE_HTTPS=False in your .env, then:
python manage.py runserver
```

> **Copy `.env.example` to `.env` before anything else.** Settings default to
> production-safe values, so without it every `manage.py` command stops with
> *"DJANGO_SECRET_KEY must be set when DEBUG is off"*. The `.env` file is
> gitignored and never leaves your machine.

Open **https://localhost:8000/webapps2026/** (or `http://` if you used `runserver`).

Your browser will warn about the self-signed certificate. That is expected — click through it.

### HTTP instead of HTTPS

`run_https.sh` is the recommended way to run this, since the app is designed around HTTPS. If you would rather skip the certificate warning, or you are on a shell without bash, set `DJANGO_USE_HTTPS=False` in your `.env` and use `python manage.py runserver`.

That flag matters: session and CSRF cookies are marked *secure*, meaning browsers refuse to send them over plain HTTP. Leave it `True` on an HTTP server and you will be unable to stay logged in — which looks like a broken login rather than a configuration issue.

## Trying It Out

This is a peer-to-peer payment app, so **you need two accounts** to see anything interesting.

1. **Register** at `/webapps2026/register/`. Pick GBP. You start with **500.00**.
2. **Register a second account** in a private/incognito window — choose **USD** this time, so you can watch the currency conversion work. It starts with 635.00 USD, the same 500 GBP converted.
3. **Send money.** From the first account, go to *Send Money* and use the second account's email. Send 100. The recipient is credited **127.00 USD** — converted through the REST service.
4. **Request money.** From the second account, request 50 USD from the first. The first account sees it under *Transactions* and can accept or reject; accepting debits them the GBP equivalent.
5. **Check notifications.** Both sides get one for every event.

To see the admin dashboard, create an admin account (below) and sign in as it — you get every user, balance and transaction in one place.

## Admin Access

There is **no default administrator account** — creating one is an explicit step:

```bash
python manage.py create_admin --username yourname --email you@example.com
```

You will be prompted for a password, checked against Django's password validators. For non-interactive use, set `DJANGO_ADMIN_PASSWORD` in your environment and pass `--noinput`.

Django superusers created with `createsuperuser` are also granted the in-app admin role the first time they sign in.

## Running the Tests

```bash
python manage.py test
```

65 tests covering the conversion rate table and endpoint, the transfer and payment-request flows (insufficient funds, double-settlement, cross-currency), notification ownership, output escaping, CSRF-protected sign-out, and admin access control. They never touch the network — the conversion client is stubbed onto its local fallback.

### Continuous integration

Every push runs three jobs on GitHub Actions:

| Job | What it proves |
|---|---|
| **Tests** | The suite passes on Python 3.10, 3.11 and 3.12 |
| **Setup path** | The README instructions work on a clean machine — venv, `.env.example`, migrations, then `run_https.sh` generating its own certificate and serving over HTTPS |
| **Deploy checks** | `manage.py check --deploy` is clean with `DEBUG` off, and a missing `DJANGO_SECRET_KEY` is a hard failure rather than a warning |

The setup job deliberately runs the same commands the README gives you, so instructions that drift out of date break the build instead of the reader.

## Troubleshooting

**`DJANGO_SECRET_KEY must be set when DEBUG is off`**
You skipped copying `.env.example` to `.env`.

**Login appears to succeed but you are still logged out**
You are on plain HTTP with `DJANGO_USE_HTTPS=True`. Set it to `False` in `.env`.

**`./run_https.sh: command not found` or permission denied**
Run `chmod +x run_https.sh`. On Windows this script needs Git Bash — use the `runserver` route above instead.

**Amounts convert but the rate looks stale**
The app calls its own REST endpoint and falls back to a local table if that fails; the fallback logs a warning naming the URL it tried. If you changed the port, update `DJANGO_CONVERSION_SERVICE_URL` in `.env`.

**`no such table` errors**
Run `python manage.py migrate`.

## Currency Conversion

The conversion service is a REST endpoint inside the same Django application. `payapp` and `register` reach it over HTTP through `conversionservice/client.py`, which keeps the service boundary explicit; if the call fails, the client logs a warning and falls back to the same rate table the endpoint uses.

```
GET /webapps2026/conversion/{from}/{to}/{amount}/
```

Example:

```
GET /webapps2026/conversion/GBP/USD/100/

{
  "from_currency": "GBP",
  "to_currency": "USD",
  "rate": "1.270000",
  "original_amount": "100",
  "converted_amount": "127.00"
}
```

Supported currencies: GBP, USD, EUR. Monetary values are strings rather than JSON numbers so that clients cannot silently decode an exact decimal amount into a binary float. Rates are stored against a single base currency, so conversions round-trip exactly.

## Environment Variables

Set these in `.env` (copy `.env.example` to get started) or as real environment variables — actual environment variables take precedence, so the same settings module works unchanged in production. `DJANGO_SECRET_KEY` is required as soon as `DJANGO_DEBUG` is off.

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Django secret key. **Required** unless `DJANGO_DEBUG=True`. |
| `DJANGO_DEBUG` | `False` | Enables debug mode. Never enable on a public host. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]` | Comma-separated list of permitted hosts. |
| `DJANGO_USE_HTTPS` | `True` | Marks session and CSRF cookies secure. Set to `False` if you serve over plain HTTP, otherwise login will not work. |
| `DJANGO_CONVERSION_SERVICE_URL` | `https://localhost:8000/webapps2026/conversion` | Base URL of the conversion service. |
| `DJANGO_CONVERSION_VERIFY_TLS` | `False` | Verify the conversion service's certificate. Off by default because development uses a self-signed cert; turn on in production. |
| `DJANGO_CONVERSION_TIMEOUT` | `3` | Conversion request timeout, in seconds. |
| `DJANGO_INITIAL_BALANCE_GBP` | `500.00` | Starting balance for a new member, converted into their chosen currency. |
| `DJANGO_ADMIN_PASSWORD` | — | Read by `manage.py create_admin` so the password never appears in shell history. |

Generate a secret key with:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Security Notes

This is a demonstration project, not a production payment system. Things worth knowing if you run or extend it:

- **SQLite** is fine for a demo but serialises all writes. Balance updates use `select_for_update()`, which SQLite ignores; move to PostgreSQL for the locking to be real under concurrency.
- **Certificate verification** for the conversion service is disabled by default, because the development server presents a self-signed certificate. Set `DJANGO_CONVERSION_VERIFY_TLS=True` behind a real certificate.
- **Exchange rates are hard-coded** in `conversionservice/rates.py`. Swap that module for a rate provider to make them live.
- Debug mode, allowed hosts, and cookie security are all environment-driven and default to the safe setting.

## Author

Tabish Shoukat

## License

MIT — see [LICENSE](LICENSE).
