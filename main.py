from flask import Flask, request, make_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def ebay_webhook():
    # STEP A: eBay’s verification comes as a GET ?challenge=TOKEN
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            # echo back the token as plain text
            return make_response(challenge, 200)

    # STEP B: real notifications will be POSTs here
    if request.method == "POST":
        payload = request.get_json(force=True)
        print("Received event:", payload)
        return {"status": "received"}, 200

    # anything else isn’t supported
    return "", 405

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
