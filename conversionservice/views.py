from django.http import JsonResponse
from django.views.decorators.http import require_GET


# Hard-coded exchange rates
EXCHANGE_RATES = {
    ('GBP', 'USD'): 1.27,
    ('GBP', 'EUR'): 1.17,
    ('USD', 'GBP'): 0.79,
    ('USD', 'EUR'): 0.92,
    ('EUR', 'GBP'): 0.85,
    ('EUR', 'USD'): 1.08,
    ('GBP', 'GBP'): 1.00,
    ('USD', 'USD'): 1.00,
    ('EUR', 'EUR'): 1.00,
}

SUPPORTED_CURRENCIES = {'GBP', 'USD', 'EUR'}


@require_GET
def conversion_view(request, currency1, currency2, amount):
    """
    REST endpoint: GET /webapps2026/conversion/{currency1}/{currency2}/{amount}
    Returns conversion rate and converted amount as JSON.
    """
    currency1 = currency1.upper()
    currency2 = currency2.upper()

    if currency1 not in SUPPORTED_CURRENCIES or currency2 not in SUPPORTED_CURRENCIES:
        return JsonResponse(
            {'error': f'Unsupported currency. Supported: {", ".join(SUPPORTED_CURRENCIES)}'},
            status=400
        )

    try:
        amount = float(amount)
        if amount < 0:
            return JsonResponse({'error': 'Amount must be positive.'}, status=400)
    except ValueError:
        return JsonResponse({'error': 'Invalid amount.'}, status=400)

    rate = EXCHANGE_RATES.get((currency1, currency2), 1.00)
    converted_amount = round(amount * rate, 2)

    return JsonResponse({
        'from_currency': currency1,
        'to_currency': currency2,
        'rate': rate,
        'original_amount': amount,
        'converted_amount': converted_amount,
    })