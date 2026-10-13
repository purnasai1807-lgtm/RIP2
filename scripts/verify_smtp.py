"""Send a real SMTP delivery probe using deployment environment variables."""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from email.message import EmailMessage


def main() -> int:
    allow_no_auth = os.environ.get("SMTP_ALLOW_NO_AUTH", "false").lower() == "true"
    required = ["MAIL_SERVER", "MAIL_PORT", "MAIL_DEFAULT_SENDER", "SMTP_TEST_RECIPIENT"]
    if not allow_no_auth:
        required.extend(("MAIL_USERNAME", "MAIL_PASSWORD"))
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        print("ERROR: missing SMTP test settings: " + ", ".join(missing), file=sys.stderr)
        return 2
    host = os.environ["MAIL_SERVER"]
    port = int(os.environ["MAIL_PORT"])
    username = os.environ.get("MAIL_USERNAME", "")
    password = os.environ.get("MAIL_PASSWORD", "")
    sender = os.environ["MAIL_DEFAULT_SENDER"]
    recipient = os.environ["SMTP_TEST_RECIPIENT"]
    use_ssl = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    use_tls = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    if use_ssl and use_tls:
        print("ERROR: enable only one of MAIL_USE_SSL or MAIL_USE_TLS.", file=sys.stderr)
        return 2
    message = EmailMessage()
    message["Subject"] = "CampusRipple SMTP configuration test"
    message["From"] = sender
    message["To"] = recipient
    message.set_content("CampusRipple successfully submitted this SMTP configuration test. This message does not verify the app's full email-verification workflow.")
    try:
        context = ssl.create_default_context()
        timeout = int(os.environ.get("MAIL_TIMEOUT", "10"))
        if timeout < 1 or timeout > 120:
            print("ERROR: MAIL_TIMEOUT must be between 1 and 120 seconds.", file=sys.stderr)
            return 2
        if use_ssl:
            client = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
        else:
            client = smtplib.SMTP(host, port, timeout=timeout)
            client.ehlo()
            if use_tls:
                client.starttls(context=context)
                client.ehlo()
        with client:
            if username and not allow_no_auth:
                client.login(username, password)
            client.send_message(message)
        print("PASS: SMTP server accepted the test message. Confirm receipt and spam-folder status in the recipient inbox.")
        return 0
    except Exception as exc:
        print(f"FAIL: SMTP probe failed ({type(exc).__name__}). Check host, port, TLS mode, sender authorization, and app password.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
