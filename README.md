# WebApps 2026

A peer-to-peer payment web application built with Django. Users can send and request money from each other with automatic currency conversion between GBP, USD, and EUR.

## Features

- User registration and authentication
- Send payments to other users by email address
- Request payments from other users
- Accept or reject incoming payment requests
- Real-time currency conversion via an internal REST service
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
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Generate a self-signed certificate for HTTPS
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes -subj "/CN=localhost"

# Start the server
./run_https.sh
```

The app will be available at `https://localhost:8000/webapps2026/`.

Your browser will show a certificate warning — this is expected with a self-signed cert. Proceed past it to use the app.

## Currency Conversion

The conversion service runs as a separate REST endpoint within the same Django application:

```
GET /webapps2026/conversion/{from}/{to}/{amount}
```

Example:
```
GET /webapps2026/conversion/GBP/USD/100
```

Supported currencies: GBP, USD, EUR.

## Environment Variables

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | Django secret key (required in production) |

## Admin Access

To create an admin user, register a normal account then set `is_admin=True` on that user's profile via the Django shell:

```bash
python manage.py shell
>>> from register.models import UserProfile
>>> p = UserProfile.objects.get(user__username='yourusername')
>>> p.is_admin = True
>>> p.save()
```
