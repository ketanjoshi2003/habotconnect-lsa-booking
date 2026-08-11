"""
Mock Payment Gateway Service.

This module wraps calls to the external payment gateway using Python's
`requests` library with:
  - Proper exception handling (timeouts, connection errors, HTTP errors)
  - Structured logging for every attempt
  - Configurable endpoint (swap to real gateway in production)

This satisfies the "Third-Party Mock Integration" requirement.
"""

import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


class PaymentGatewayError(Exception):
    """Raised when the payment gateway call fails."""


class MockPaymentService:
    """
    Service layer that communicates with the (mock) payment gateway.

    In production, PAYMENT_GATEWAY_URL would point to Stripe/Razorpay/etc.
    For this simulation, it points to our own /api/v1/payments/mock-gateway/ endpoint.
    """

    def __init__(self):
        self.base_url = current_app.config.get(
            "PAYMENT_GATEWAY_URL",
            "http://localhost:5000/api/v1/payments/mock-gateway",
        )
        self.api_key = current_app.config.get("PAYMENT_GATEWAY_API_KEY", "test-key")
        self.timeout = 10  # seconds

    def initiate_payment(self, booking_id, reference, amount, currency="AED"):
        """
        Call the payment gateway to initiate a payment for a booking.

        Args:
            booking_id: Internal booking ID
            reference: Human-readable booking reference (HB-YYYYMMDD-XXXX)
            amount: Payment amount
            currency: ISO currency code

        Returns:
            dict: {"payment_id": "pay_...", "status": "success"|"failed"}

        Raises:
            PaymentGatewayError: On network failure, timeout, or HTTP error
        """
        payload = {
            "booking_id": booking_id,
            "booking_reference": reference,
            "amount": amount,
            "currency": currency,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            f"Initiating payment for booking {reference}: amount={amount} {currency}"
        )

        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Payment gateway response for {reference}: "
                f"status={result.get('status')}, payment_id={result.get('payment_id')}"
            )
            return result

        except requests.exceptions.Timeout:
            logger.error(f"Payment gateway timeout for booking {reference}")
            raise PaymentGatewayError("Payment gateway timed out")

        except requests.exceptions.ConnectionError:
            logger.error(f"Payment gateway connection error for booking {reference}")
            raise PaymentGatewayError("Cannot connect to payment gateway")

        except requests.exceptions.HTTPError as e:
            logger.error(
                f"Payment gateway HTTP error for booking {reference}: {e.response.status_code}"
            )
            raise PaymentGatewayError(f"Gateway returned HTTP {e.response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.error(f"Payment request failed for booking {reference}: {str(e)}")
            raise PaymentGatewayError(f"Payment request failed: {str(e)}")
