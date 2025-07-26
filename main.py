from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/privacy", methods=["GET"])
def privacy():
    # serve a minimal privacy policy
    return """<h1>Privacy Policy</h1>
<p>MyResearchTool only fetches and displays public, read-only item and seller data. No eBay user data is ever stored or persisted.</p>""", 200

@app.route("/callback", methods=["GET"])
def callback():
    # OAuth redirect here
    code = request.args.get("code")
    error = request.args.get("error")
    if code:
        # in real life you'd exchange this for tokens here
        return f"Success! Your auth code is: <code>{code}</code>"
    elif error:
        return f"OAuth error: {error}", 400
    return "No code or error provided", 400

@app.route("/decline", methods=["GET"])
def decline():
    return "<h1>Authorization Declined</h1><p>You chose not to sign in.</p>", 200

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # STEP A: eBay’s verification challenge on GET
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            return make_response(challenge, 200)
        return "Missing challenge", 400

    # STEP B: real notifications arrive as POST
    payload = request.get_json(force=True)
    print("Received event:", payload)
    return {"status": "received"}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
