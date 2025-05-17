from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import requests
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Environment Variables
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
print("VERIFY_TOKEN:", VERIFY_TOKEN)
print("WHATSAPP_TOKEN:", WHATSAPP_TOKEN[:10], "...")  # don’t print full
print("WHATSAPP_PHONE_NUMBER_ID:", WHATSAPP_PHONE_NUMBER_ID)

# Initialize LLM
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0,
    max_tokens=None,
    max_retries=2
)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        response = llm.invoke(prompt)
        parsed = response.model_dump_json()
        content = json.loads(parsed)["content"]
        return jsonify({"response": content}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Webhook verification
@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

# Webhook for incoming WhatsApp messages
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        print("Received Webhook Payload:", json.dumps(data, indent=2))

        entry = data.get('entry', [])[0]
        changes = entry.get('changes', [])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])

        # Ignore if there are no messages (e.g., webhook ping or message status updates)
        if not messages:
            print("No message found in payload. Possibly a status update or verification.")
            return "ok", 200

        message = messages[0]
        sender = message['from']
        text = message['text']['body']

        # ✅ Call Groq API directly via LangChain
        response = llm.invoke(text)
        parsed = response.model_dump_json()
        reply_text = json.loads(parsed)["content"]

        # Send reply via WhatsApp
        requests.post(
            f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers={
                "Authorization": f"Bearer {WHATSAPP_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "messaging_product": "whatsapp",
                "to": sender,
                "text": {"body": reply_text}
            }
        )

    except Exception as e:
        print("Error:", e)
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
