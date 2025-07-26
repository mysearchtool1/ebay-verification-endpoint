from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # STEP A: eBay’s webhook verification comes as a GET ?challenge=TOKEN
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            return make_response(challenge, 200)
        return "Missing challenge", 400

    # STEP B: real notifications will be POSTs here
    if request.method == "POST":
        payload = request.get_json(force=True)
        print("Received event:", payload)
        return {"status": "received"}, 200

    return "", 405

@app.route("/privacy", methods=["GET"])
def privacy():
    return """
    <html>
      <head><title>Privacy policy</title></head>
      <body>
        <h1>Privacy policy</h1>
        <p>
          This application only fetches &amp; displays public, read-only item and seller data. 
          No eBay user data is ever stored or persisted.
        </p>
      </body>
    </html>
    """, 200

@app.route("/callback", methods=["GET"])
def callback():
    code = request.args.get("code")
    if code:
        return make_response(code, 200)
    return "Missing code", 400

@app.route("/decline", methods=["GET"])
def decline():
    return """
    <html>
      <head><title>Authorization Declined</title></head>
      <body>
        <h1>Authorization Declined</h1>
        <p>
          You declined to authorize. If you change your mind you can retry the login flow.
        </p>
      </body>
    </html>
    """, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
