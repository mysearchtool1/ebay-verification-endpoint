from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # STEP A: eBay’s webhook verification: GET /?challenge=TOKEN
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            return make_response(challenge, 200)
        return "Missing challenge", 400

    # STEP B: real push notifications will POST JSON here
    if request.method == "POST":
        payload = request.get_json(force=True)
        print("Received event:", payload)
        return {"status": "received"}, 200

    return "", 405

# 1️⃣ Privacy policy URL
@app.route("/privacy", methods=["GET"])
def privacy():
    return """
      <html>
        <head><title>Privacy policy</title></head>
        <body>
          <h1>Privacy policy</h1>
          <p>
            This application only fetches &amp; displays public, read-only item and
            seller data. No eBay user data is ever stored or persisted.
          </p>
        </body>
      </html>
    """, 200

# 2️⃣ OAuth success callback: eBay will redirect you here with ?code=...
@app.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    if code:
        return make_response(f"Authorization code: {code}", 200)
    return "Missing code", 400

# 3️⃣ OAuth decline page
@app.route("/decline", methods=["GET"])
def decline():
    return """
      <html>
        <head><title>Authorization Declined</title></head>
        <body>
          <h1>Authorization Declined</h1>
          <p>
            You declined the sign-in. You can <a href="/">retry</a> if you change your mind.
          </p>
        </body>
      </html>
    """, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
