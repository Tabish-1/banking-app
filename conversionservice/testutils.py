"""Shared test helpers for code that consumes the conversion service."""

import logging
from unittest.mock import patch

import requests


class QuietLogsMixin:
    """Silence logging for tests that deliberately exercise error paths.

    Those paths log by design; without this the suite's output is full of
    warnings and tracebacks from assertions that are passing.
    """

    def setUp(self):
        super().setUp()
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)


class LocalRatesMixin(QuietLogsMixin):
    """Force the conversion client onto its local fallback for the whole test.

    The client normally makes an HTTP call to this project's own conversion
    endpoint. No server is listening during tests, so rather than waiting for a
    real connection to time out we fail it immediately and deterministically —
    the resulting amounts come from conversionservice.rates, which is exactly
    what the endpoint would have returned anyway.
    """

    def setUp(self):
        super().setUp()

        patcher = patch(
            'conversionservice.client.requests.get',
            side_effect=requests.RequestException('no conversion server under test'),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
