"""Single source of truth for currency conversion.

Rates are hard-coded for this demo. A production system would fetch them from a
rate provider and cache them; the function signatures here are deliberately kept
simple so that source can be swapped without touching any caller.

Rates are stored against a single base currency (GBP) rather than as a table of
pairs, so that every pair is derived from one number and round-trips stay
consistent. A per-pair table has to be kept invertible by hand, and usually
isn't.
"""

from decimal import Decimal, ROUND_HALF_UP

#: Value of one unit of the base currency (GBP) in each supported currency.
_RATES_AGAINST_GBP = {
    'GBP': Decimal('1.00'),
    'USD': Decimal('1.27'),
    'EUR': Decimal('1.17'),
}

SUPPORTED_CURRENCIES = frozenset(_RATES_AGAINST_GBP)

CENTS = Decimal('0.01')


class UnsupportedCurrency(ValueError):
    """Raised when a currency code is outside SUPPORTED_CURRENCIES."""


def get_rate(from_currency, to_currency):
    """Return the exchange rate between two supported currencies as a Decimal."""
    try:
        source = _RATES_AGAINST_GBP[from_currency]
        target = _RATES_AGAINST_GBP[to_currency]
    except KeyError as exc:
        raise UnsupportedCurrency(f'Unsupported currency: {exc.args[0]}') from exc

    if from_currency == to_currency:
        return Decimal('1')
    return target / source


def convert(from_currency, to_currency, amount):
    """Convert amount between two currencies, rounded to two decimal places.

    Raises UnsupportedCurrency for unknown codes and ValueError for a negative
    or unparseable amount.
    """
    try:
        amount = Decimal(str(amount))
    except Exception as exc:
        raise ValueError(f'Invalid amount: {amount!r}') from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError('Amount must be a non-negative number.')

    if from_currency == to_currency:
        # Still validate the code so callers get a consistent error.
        get_rate(from_currency, to_currency)
        return amount.quantize(CENTS, rounding=ROUND_HALF_UP)

    converted = amount * get_rate(from_currency, to_currency)
    return converted.quantize(CENTS, rounding=ROUND_HALF_UP)
