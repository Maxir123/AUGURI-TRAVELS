from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

import os
import json
from datetime import datetime

from dotenv import load_dotenv

from twilio.rest import Client


load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CONTACT_LOG = os.path.join(DATA_DIR, "contact_submissions.jsonl")
BOOKING_LOG = os.path.join(DATA_DIR, "booking_submissions.jsonl")


def log_jsonl(path: str, payload: dict):
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds") + "Z",
        **payload,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def send_whatsapp_twilio(phone: str, message: str):
    """Send WhatsApp message via Twilio"""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_WHATSAPP_PHONE")  # e.g., "whatsapp:+1234567890"
    
    if not all([account_sid, auth_token, from_phone]):
        raise RuntimeError("Missing Twilio credentials in backend/.env")
    
    client = Client(account_sid, auth_token)
    
    # Ensure phone is in WhatsApp format
    if not phone.startswith("whatsapp:"):
        phone = f"whatsapp:{phone}"
    
    message_obj = client.messages.create(
        from_=from_phone,
        to=phone,
        body=message
    )
    
    return message_obj


# Email confirmation emails are handled by EmailJS (frontend).
# Backend keeps WhatsApp notifications + JSONL logging only.



def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app)

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.get("/about")
    def about():
        return render_template("about.html")

    @app.get("/contact")
    def contact():
        return render_template("contact.html")

    @app.post("/api/contact")
    def api_contact():
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        message = (data.get("message") or "").strip()

        if not name or not email or not message:
            return jsonify({"ok": False, "error": "name, email and message are required"}), 400

        log_jsonl(CONTACT_LOG, {"name": name, "email": email, "message": message})

        whatsapp_status = "not_sent"

        # Send WhatsApp notification to admin
        try:
            admin_phone = os.getenv("ADMIN_WHATSAPP_PHONE", "+2348082703423")
            whatsapp_msg = f"""📬 New Contact Submission from {name}

📧 Email: {email}
📝 Message: {message}

Received: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            send_whatsapp_twilio(admin_phone, whatsapp_msg)
            whatsapp_status = "sent"
        except Exception as e:
            whatsapp_status = "failed"
            print(f"Error sending WhatsApp notification: {e}")



        return jsonify({"ok": True, "message": "Contact message received", "whatsappStatus": whatsapp_status}), 200

    @app.post("/api/booking")
    def api_booking():
        data = request.get_json(silent=True) or {}

        required = ["fullName", "email", "phone", "destination", "departureDate"]
        missing = [k for k in required if not (data.get(k) or "").strip()]
        if missing:
            return jsonify({"ok": False, "error": "Missing required fields: " + ", ".join(missing)}), 400

        allowed = {
            "fullName",
            "email",
            "phone",
            "destination",
            "departureDate",
            "returnDate",
            "travelers",
            "travelClass",
            "specialRequests",
        }

        payload = {k: data.get(k) for k in allowed if k in data}
        for k, v in list(payload.items()):
            if isinstance(v, str):
                payload[k] = v.strip()

        log_jsonl(BOOKING_LOG, payload)

        whatsapp_status = "not_sent"

        # Send WhatsApp notification to admin
        try:
            admin_phone = os.getenv("ADMIN_WHATSAPP_PHONE", "+2348082703423")
            whatsapp_msg = f"""✈️ New Booking Request

👤 Name: {payload.get('fullName', 'N/A')}
📱 Phone: {payload.get('phone', 'N/A')}
📧 Email: {payload.get('email', 'N/A')}
🌍 Destination: {payload.get('destination', 'N/A')}
📅 Departure: {payload.get('departureDate', 'N/A')}
📅 Return: {payload.get('returnDate', 'N/A')}
👥 Travelers: {payload.get('travelers', 'N/A')}
✈️ Class: {payload.get('travelClass', 'N/A')}
💬 Special Requests: {payload.get('specialRequests', 'None')}

Received: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

            send_whatsapp_twilio(admin_phone, whatsapp_msg)
            whatsapp_status = "sent"
        except Exception as e:
            whatsapp_status = "failed"
            print(f"Error sending booking WhatsApp notification: {e}")

        # Confirmation emails are handled by EmailJS (frontend).
        return jsonify({"ok": True, "message": "Booking request received", "whatsappStatus": whatsapp_status}), 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
