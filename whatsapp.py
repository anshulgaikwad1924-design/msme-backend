import os
from twilio.rest import Client


def send_whatsapp_alert(
    supplier_phone: str,
    product: str,
    current_stock: int,
    reorder_qty: int,
    days_left,
    store_name: str = "MSME Store",
) -> dict:
    """
    Send a WhatsApp message to the supplier via Twilio.

    Prerequisites:
    - TWILIO_ACCOUNT_SID in .env
    - TWILIO_AUTH_TOKEN  in .env
    - TWILIO_WHATSAPP_FROM in .env  (e.g. whatsapp:+14155238886)

    supplier_phone format: "+919876543210"
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        raise EnvironmentError(
            "Twilio credentials not set. Add TWILIO_ACCOUNT_SID and "
            "TWILIO_AUTH_TOKEN to your .env file."
        )

    message_body = _build_message(
        store_name, product, current_stock, days_left, reorder_qty
    )

    client = Client(account_sid, auth_token)
    msg = client.messages.create(
        body=message_body,
        from_=from_number,
        to=f"whatsapp:{supplier_phone}",
    )

    return {
        "status":       "sent",
        "message_sid":  msg.sid,
        "to":           supplier_phone,
        "preview":      message_body,
    }


def _build_message(store, product, stock, days_left, reorder_qty) -> str:
    days_str = f"{days_left} day(s)" if days_left not in (None, "N/A") else "very soon"
    return (
        f"🚨 *Reorder Alert — {store}*\n\n"
        f"Product  : *{product}*\n"
        f"Stock    : {stock} units remaining\n"
        f"Runs out : in {days_str}\n"
        f"Please send *{reorder_qty} units* at the earliest.\n\n"
        f"_Powered by MSME Demand Forecaster AI_"
    )
