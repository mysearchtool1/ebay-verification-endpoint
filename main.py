from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # eBay’s initial verification comes as a GET with ?challenge=<token>
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            # echo back the raw token, exactly as text
            return make_response(challenge, 200)

    # Once verified, eBay will POST actual notifications here
    if request.method == "POST":
        payload = request.get_json(force=True)
        # you can inspect / log payload here
        print("Event body:", payload)
        return {"status": "received"}, 200

    # everything else is not allowed
    return "", 405

if __name__ == "__main__":
    # only used for local testing
    app.run(host="0.0.0.0", port=10000)
