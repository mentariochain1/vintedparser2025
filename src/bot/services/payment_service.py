"""Payment service for YooKassa integration."""

import hashlib
import hmac
import logging
import time
from datetime import datetime ,timedelta
from typing import Dict ,Optional ,Tuple
from uuid import uuid4

from sqlalchemy .ext .asyncio import AsyncSession
from yookassa import Configuration ,Payment

from src.config import settings
from src.db.crud import PaymentCRUD ,UserCRUD
from src.exceptions import (
    PaymentError, PaymentCreationError, PaymentVerificationError,
    InvalidWebhookSignatureError, ConfigurationError
)
from src.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerConfig
from src.error_handlers import error_handler

logger =logging .getLogger (__name__ )

class PaymentService :
    """Service for handling payments through YooKassa."""

    def __init__ (self ):
        self .shop_id =settings .yookassa_shop_id
        self .secret_key =settings .yookassa_secret_key
        self .subscription_days =30
        self ._configure_yookassa ()

    def _configure_yookassa (self )->None :
        """Configure YooKassa with credentials."""
        try :
            Configuration .configure (
            account_id =self .shop_id ,
            secret_key =self .secret_key
            )
            logger .info ("YooKassa configuration initialized")
            
            # Initialize circuit breaker for YooKassa API
            self.circuit_breaker = get_circuit_breaker(
                "yookassa_api",
                CircuitBreakerConfig(
                    failure_threshold=3,
                    timeout=180,  # 3 minutes
                    success_threshold=2,
                    expected_exception=(PaymentError, PaymentCreationError)
                )
            )
            
        except Exception as e :
            error_handler.log_error(ConfigurationError(f"Failed to configure YooKassa: {e}"))
            raise ConfigurationError(f"Failed to configure YooKassa: {e}")

    async def create_payment (
    self ,
    session :AsyncSession ,
    user_id :int ,
    amount :float ,
    currency :str ="RUB",
    description :str ="Premium subscription",
    return_url :Optional [str ]=None ,
    )->Dict [str ,str ]:
        """
        Create a new payment with YooKassa.

        Args:
            session: Database session
            user_id: User ID making the payment
            amount: Payment amount
            currency: Payment currency (default: RUB)
            description: Payment description
            return_url: URL to redirect after payment

        Returns:
            Dictionary with payment_id and confirmation_url
        """
        try :

            idempotence_key =str (uuid4 ())

            payment_data ={
            "amount":{
            "value":f"{amount :.2f}",
            "currency":currency
            },
            "description":description ,
            "payment_method_data":{
            "type":"bank_card"
            },
            "confirmation":{
            "type":"redirect",
            "return_url":return_url or f"{settings .webhook_domain }/payment/success"
            },
            "metadata":{
            "user_id":str (user_id )
            }
            }

            payment =Payment .create (payment_data ,idempotence_key )

            await PaymentCRUD .create (
            session =session ,
            user_id =user_id ,
            yookassa_id =payment .id ,
            amount =amount ,
            currency =currency ,
            status =payment .status ,
            )

            await session .commit ()

            logger .info (f"Payment created: {payment .id } for user {user_id }")

            return {
            "payment_id":payment .id ,
            "confirmation_url":payment .confirmation .confirmation_url ,
            "status":payment .status
            }

        except Exception as e :
            await session .rollback ()
            logger .error (f"Failed to create payment for user {user_id }: {e }")
            raise

    async def get_payment_status (self ,payment_id :str )->Optional [Dict [str ,str ]]:
        """
        Get payment status from YooKassa.

        Args:
            payment_id: YooKassa payment ID

        Returns:
            Payment status information or None if not found
        """
        try :
            payment =Payment .find_one (payment_id )

            if payment :
                return {
                "payment_id":payment .id ,
                "status":payment .status ,
                "amount":payment .amount .value ,
                "currency":payment .amount .currency ,
                "created_at":payment .created_at ,
                "metadata":payment .metadata or {}
                }

            return None

        except Exception as e :
            logger .error (f"Failed to get payment status for {payment_id }: {e }")
            return None

    async def process_webhook (
    self ,
    session :AsyncSession ,
    payload :bytes ,
    signature :str ,
    timestamp :str ,
    )->Tuple [bool ,str ]:
        """
        Process YooKassa webhook notification.

        Args:
            session: Database session
            payload: Webhook payload
            signature: Webhook signature
            timestamp: Webhook timestamp

        Returns:
            Tuple of (success, message)
        """
        try :

            if not self .verify_webhook_signature (payload ,signature ,timestamp ):
                logger .warning ("Invalid webhook signature")
                return False ,"Invalid signature"

            import json
            webhook_data =json .loads (payload .decode ('utf-8'))

            event_type =webhook_data .get ("event")
            payment_data =webhook_data .get ("object",{})
            payment_id =payment_data .get ("id")

            if not payment_id :
                logger .warning ("No payment ID in webhook")
                return False ,"No payment ID"

            payment =await PaymentCRUD .update_status (
            session =session ,
            yookassa_id =payment_id ,
            status =payment_data .get ("status","unknown")
            )

            if not payment :
                logger .warning (f"Payment not found in database: {payment_id }")
                return False ,"Payment not found"

            if event_type =="payment.succeeded":
                success =await self ._process_successful_payment (session ,payment )
                if success :
                    await session .commit ()
                    logger .info (f"Successfully processed payment: {payment_id }")
                    return True ,"Payment processed successfully"
                else :
                    await session .rollback ()
                    return False ,"Failed to process successful payment"

            elif event_type =="payment.canceled":
                await session .commit ()
                logger .info (f"Payment cancelled: {payment_id }")
                return True ,"Payment cancelled"

            else :
                await session .commit ()
                logger .info (f"Payment status updated: {payment_id } -> {payment_data .get ('status')}")
                return True ,"Status updated"

        except Exception as e :
            await session .rollback ()
            logger .error (f"Failed to process webhook: {e }")
            return False ,f"Webhook processing failed: {str (e )}"

    def verify_webhook_signature (
    self ,
    payload :bytes ,
    signature :str ,
    timestamp :str ,
    max_age :int =300
    )->bool :
        """
        Verify YooKassa webhook signature.

        Args:
            payload: Webhook payload
            signature: Provided signature
            timestamp: Webhook timestamp
            max_age: Maximum age of webhook in seconds

        Returns:
            True if signature is valid, False otherwise
        """
        try :

            webhook_time =int (timestamp )
            current_time =int (time .time ())

            if abs (current_time -webhook_time )>max_age :
                logger .warning (f"Webhook too old: {current_time -webhook_time }s")
                return False

            message =payload +timestamp .encode ()
            expected_signature =hmac .new (
            self .secret_key .encode (),
            message ,
            hashlib .sha256
            ).hexdigest ()

            return hmac .compare_digest (signature ,expected_signature )

        except (ValueError ,TypeError )as e :
            logger .error (f"Error verifying webhook signature: {e }")
            return False

    async def _process_successful_payment (
    self ,
    session :AsyncSession ,
    payment
    )->bool :
        """
        Process a successful payment by extending user subscription.

        Args:
            session: Database session
            payment: Payment record

        Returns:
            True if processed successfully, False otherwise
        """
        try :
            user =await UserCRUD .get_by_id (session ,payment .user_id )
            if not user :
                logger .error (f"User not found for payment: {payment .user_id }")
                return False

            now =datetime .utcnow ()
            current_expiry =user .subscription_expires or now

            base_date =max (current_expiry ,now )
            new_expiry =base_date +timedelta (days =self .subscription_days )

            user .subscription_expires =new_expiry

            logger .info (f"Extended subscription for user {user .id } until {new_expiry }")
            return True

        except Exception as e :
            logger .error (f"Failed to process successful payment: {e }")
            return False

    async def cancel_payment (self ,payment_id :str )->Tuple [bool ,str ]:
        """
        Cancel a payment.

        Args:
            payment_id: YooKassa payment ID

        Returns:
            Tuple of (success, message)
        """
        try :
            payment =Payment .cancel (payment_id ,str (uuid4 ()))

            logger .info (f"Payment cancelled: {payment_id }")
            return True ,f"Payment cancelled: {payment .status }"

        except Exception as e :
            logger .error (f"Failed to cancel payment {payment_id }: {e }")
            return False ,f"Failed to cancel payment: {str (e )}"

    async def get_user_payments (
    self ,
    session :AsyncSession ,
    user_id :int ,
    limit :int =10
    )->list :
        """
        Get payment history for a user.

        Args:
            session: Database session
            user_id: User ID
            limit: Maximum number of payments to return

        Returns:
            List of payment records
        """
        try :

            return []

        except Exception as e :
            logger .error (f"Failed to get payments for user {user_id }: {e }")
            return []

    def calculate_subscription_price (
    self ,
    days :int =30 ,
    base_price :float =299.0 ,
    currency :str ="RUB"
    )->Dict [str ,any ]:
        """
        Calculate subscription price based on duration.

        Args:
            days: Subscription duration in days
            base_price: Base monthly price
            currency: Price currency

        Returns:
            Price information dictionary
        """

        price_per_day =base_price /30
        total_price =price_per_day *days

        if days >=365 :
            discount =0.20
        elif days >=90 :
            discount =0.10
        else :
            discount =0.0

        discounted_price =total_price *(1 -discount )

        return {
        "days":days ,
        "base_price":total_price ,
        "discount":discount ,
        "final_price":discounted_price ,
        "currency":currency ,
        "price_per_day":price_per_day
        }

    async def health_check (self )->bool :
        """
        Perform a health check of the payment service.

        Returns:
            True if service is healthy, False otherwise
        """
        try :

            config_valid =bool (self .shop_id and self .secret_key )

            if not config_valid :
                logger .error ("YooKassa configuration is invalid")
                return False

            logger .debug ("Payment service health check passed")
            return True

        except Exception as e :
            logger .error (f"Payment service health check failed: {e }")
            return False 