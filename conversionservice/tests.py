from decimal import Decimal
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from conversionservice.client import convert as convert_via_service
from conversionservice.rates import UnsupportedCurrency, convert, get_rate
from conversionservice.testutils import LocalRatesMixin, QuietLogsMixin


class RateTableTests(SimpleTestCase):

    def test_same_currency_is_identity(self):
        self.assertEqual(convert('GBP', 'GBP', '100'), Decimal('100.00'))

    def test_known_pair(self):
        self.assertEqual(convert('GBP', 'USD', '100'), Decimal('127.00'))
        self.assertEqual(convert('GBP', 'EUR', '100'), Decimal('117.00'))

    def test_round_trip_preserves_value(self):
        """Rates derive from one base, so a round trip must not lose money.

        The previous per-pair table used 1.27 out and 0.79 back, which quietly
        destroyed about 1.7% of the amount on every round trip.
        """
        for currency in ('USD', 'EUR'):
            with self.subTest(currency=currency):
                out = convert('GBP', currency, Decimal('500'))
                self.assertEqual(convert(currency, 'GBP', out), Decimal('500.00'))

    def test_result_is_quantised_to_two_places(self):
        self.assertEqual(convert('GBP', 'USD', '0.01').as_tuple().exponent, -2)

    def test_unsupported_currency(self):
        with self.assertRaises(UnsupportedCurrency):
            convert('GBP', 'JPY', '10')

    def test_negative_amount(self):
        with self.assertRaises(ValueError):
            convert('GBP', 'USD', '-1')

    def test_unparseable_amount(self):
        with self.assertRaises(ValueError):
            convert('GBP', 'USD', 'abc')

    def test_rates_are_inverses_of_each_other(self):
        # Not exactly 1: the reverse rate is a repeating decimal truncated to
        # the Decimal context's precision. It only has to be close enough that
        # a converted amount still rounds back to the original.
        product = get_rate('GBP', 'USD') * get_rate('USD', 'GBP')
        self.assertLess(abs(product - Decimal('1')), Decimal('1e-20'))


class ConversionEndpointTests(QuietLogsMixin, TestCase):

    def test_returns_converted_amount(self):
        response = self.client.get(reverse('conversion', args=['GBP', 'USD', '100']))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['from_currency'], 'GBP')
        self.assertEqual(body['to_currency'], 'USD')
        self.assertEqual(Decimal(body['converted_amount']), Decimal('127.00'))

    def test_currency_codes_are_case_insensitive(self):
        response = self.client.get(reverse('conversion', args=['gbp', 'usd', '100']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()['converted_amount']), Decimal('127.00'))

    def test_rejects_unsupported_currency(self):
        response = self.client.get(reverse('conversion', args=['GBP', 'JPY', '100']))

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_rejects_invalid_amount(self):
        response = self.client.get(reverse('conversion', args=['GBP', 'USD', 'abc']))
        self.assertEqual(response.status_code, 400)

    def test_rejects_negative_amount(self):
        response = self.client.get(reverse('conversion', args=['GBP', 'USD', '-5']))
        self.assertEqual(response.status_code, 400)

    def test_rejects_non_get(self):
        response = self.client.post(reverse('conversion', args=['GBP', 'USD', '100']))
        self.assertEqual(response.status_code, 405)


class ConversionClientTests(SimpleTestCase):

    def test_uses_the_service_response_when_reachable(self):
        with patch('conversionservice.client.requests.get') as mock_get:
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {'converted_amount': '999.99'}

            self.assertEqual(convert_via_service('GBP', 'USD', '100'), Decimal('999.99'))

        requested_url = mock_get.call_args.args[0]
        self.assertTrue(
            requested_url.endswith('/GBP/USD/100/'),
            f'expected a trailing slash to avoid an APPEND_SLASH redirect, got {requested_url}',
        )

    def test_falls_back_to_local_rates_when_unreachable(self):
        # assertLogs both asserts the warning and keeps it out of test output.
        # A silent fallback is the bug this replaced: a misconfigured service
        # URL used to be completely invisible.
        with patch(
            'conversionservice.client.requests.get',
            side_effect=requests.RequestException('service down'),
        ), self.assertLogs('conversionservice.client', level='WARNING'):
            self.assertEqual(convert_via_service('GBP', 'USD', '100'), Decimal('127.00'))

    def test_falls_back_when_response_is_malformed(self):
        with patch('conversionservice.client.requests.get') as mock_get, \
                self.assertLogs('conversionservice.client', level='WARNING'):
            mock_get.return_value.raise_for_status.return_value = None
            mock_get.return_value.json.return_value = {'unexpected': 'shape'}

            self.assertEqual(convert_via_service('GBP', 'USD', '100'), Decimal('127.00'))


class LocalRatesMixinTests(LocalRatesMixin, SimpleTestCase):

    def test_mixin_forces_local_rates(self):
        self.assertEqual(convert_via_service('GBP', 'EUR', '100'), Decimal('117.00'))
