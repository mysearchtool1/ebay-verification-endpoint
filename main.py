from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # Verification handshake (eBay sends GET ?challenge=TOKEN)
    if request.method == "GET":
        token = request.args.get("challenge")
        if token:
            # echo the token as plain text
            return make_response(token, 200)
        # no challenge => bad request
        return make_response("missing challenge", 400)

    # Actual notifications will arrive as POST JSON bodies
    if request.method == "POST":
        payload = request.get_json(force=True)
        # TODO: process payload here
        print("📬 Received event:", payload)
        return {"status": "received"}, 200

    # any other method => not allowed
    return "", 405

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
