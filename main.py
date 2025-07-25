from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # eBay’s initial verification comes as a GET?challenge=<token>
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            # must return the raw token, not JSON
            return make_response(challenge, 200)

    # once verified, eBay will POST actual notifications
    if request.method == "POST":
        data = request.get_json(force=True)
        # TODO: handle notification payload here...
        print("Received event:", data)
        return {"status": "received"}, 200

    return "", 405
