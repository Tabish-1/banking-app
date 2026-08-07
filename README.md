# WebApps 2026

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

**Prerequisites:** Python 3.10+

```bash
# Clone the repo
git clone https://github.com/yourusername/webapps2026.git
cd webapps2026

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
DJANGO_DEBUG=True python manage.py migrate

# Start the server (generates a self-signed certificate on first run)
./run_https.sh
```

The app will be available at `https://localhost:8000/webapps2026/`.

Your browser will show a certificate warning — this is expected with a self-signed cert. Proceed past it to use the app.

`run_https.sh` sets `DJANGO_DEBUG=True` for you, because settings default to production-safe values. Any `manage.py` command you run by hand needs the same variable, or a `DJANGO_SECRET_KEY`.

## Running the Tests

```bash
DJANGO_DEBUG=True python manage.py test
```

The tests cover the conversion rate table and endpoint, the transfer and payment-request flows (including insufficient funds, double-settlement and cross-currency cases), notification ownership, output escaping, and admin access control. They never touch the network — the conversion client is stubbed onto its local fallback.

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

All are optional in development; `DJANGO_SECRET_KEY` is required as soon as `DJANGO_DEBUG` is off.

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

## Admin Access

There is **no default administrator account** — creating one is an explicit step:

```bash
DJANGO_DEBUG=True python manage.py create_admin \
    --username yourname --email you@example.com
```

You will be prompted for a password, which is checked against Django's password validators. For non-interactive use, set `DJANGO_ADMIN_PASSWORD` and pass `--noinput`.

Django superusers created with `createsuperuser` are also granted the in-app admin role the first time they sign in.

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
