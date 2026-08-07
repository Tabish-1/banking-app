from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from conversionservice.rates import (
    SUPPORTED_CURRENCIES,
    UnsupportedCurrency,
    convert,
    get_rate,
)

# Rates live in conversionservice.rates so that this endpoint and the internal
# callers in payapp/register cannot drift apart.

#: Rates are quoted to six decimal places in the response; the converted amount
#: itself is always rounded to two.
RATE_PRECISION = Decimal('0.000001')


@require_GET
def conversion_view(request, currency1, currency2, amount):
    """
    REST endpoint: GET /webapps2026/conversion/{currency1}/{currency2}/{amount}
    Returns the conversion rate and converted amount as JSON.

    Monetary values are serialised as strings rather than JSON numbers, so that
    clients decoding them cannot silently turn an exact decimal amount into a
    binary float.
    """
    currency1 = currency1.upper()
    currency2 = currency2.upper()

    if currency1 not in SUPPORTED_CURRENCIES or currency2 not in SUPPORTED_CURRENCIES:
        return JsonResponse(
            {'error': f'Unsupported currency. Supported: {", ".join(sorted(SUPPORTED_CURRENCIES))}'},
            status=400,
        )

    try:
        converted_amount = convert(currency1, currency2, amount)
    except UnsupportedCurrency as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except ValueError:
        return JsonResponse({'error': 'Invalid amount.'}, status=400)

    rate = get_rate(currency1, currency2).quantize(RATE_PRECISION)

    return JsonResponse({
        'from_currency': currency1,
        'to_currency': currency2,
        'rate': str(rate),
        'original_amount': str(Decimal(str(amount))),
        'converted_amount': str(converted_amount),
    })
