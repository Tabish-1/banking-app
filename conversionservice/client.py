"""Client for the internal currency-conversion REST service.

The conversion service is exposed over HTTP (see conversionservice.views) to
demonstrate a service boundary, and this client is how the rest of the project
consumes it. If the call fails, we fall back to the same rate table the service
itself uses rather than failing a payment outright — but the failure is logged,
because a misconfigured CONVERSION_SERVICE_URL used to be completely invisible.
"""

import logging
from decimal import Decimal, InvalidOperation

import requests
import urllib3
from django.conf import settings

from conversionservice.rates import convert as convert_locally

logger = logging.getLogger(__name__)

if not settings.CONVERSION_SERVICE_VERIFY_TLS:
    # The development server uses a self-signed certificate, so certificate
    # verification is deliberately off for this loopback call and the resulting
    # warning would otherwise fire on every conversion. Set
    # DJANGO_CONVERSION_VERIFY_TLS=True once a real certificate is in place.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def convert(from_currency, to_currency, amount):
    """Convert `amount` between currencies, returning a two-decimal Decimal."""
    amount = Decimal(str(amount))

    if from_currency == to_currency:
        return convert_locally(from_currency, to_currency, amount)

    # Trailing slash matters: the URLconf pattern ends in one, and without it
    # every call paid for an APPEND_SLASH redirect before reaching the view.
    url = f'{settings.CONVERSION_SERVICE_URL}/{from_currency}/{to_currency}/{amount}/'

    try:
        response = requests.get(
            url,
            timeout=settings.CONVERSION_SERVICE_TIMEOUT,
            verify=settings.CONVERSION_SERVICE_VERIFY_TLS,
        )
        response.raise_for_status()
        return Decimal(str(response.json()['converted_amount']))
    except (requests.RequestException, ValueError, KeyError, InvalidOperation):
        logger.warning(
            'Conversion service unreachable or returned an unusable response '
            '(%s); falling back to local rates.',
            url,
            exc_info=True,
        )
        return convert_locally(from_currency, to_currency, amount)
