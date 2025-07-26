from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# 1) Privacy‐policy page
@app.route("/privacy", methods=["GET"])
def privacy():
    return render_template_string("""
      <html><head><title>Privacy Policy</title></head><body>
      <h1>MyResearchTool Privacy Policy</h1>
      <p>Your privacy text goes here. We only fetch public, read-only item & seller data...</p>
      </body></html>
    """), 200

# 2) OAuth callback (success)
@app.route("/callback", methods=["GET"])
def callback():
    code  = request.args.get("code")
    error = request.args.get("error")
    if code:
        # exchange code for token, etc.
        return f"Thanks! Received authorization code: {code}", 200
    elif error:
        return f"OAuth error: {error}", 400
    return "No OAuth parameters found.", 400

# 3) Declined page
@app.route("/decline", methods=["GET"])
def decline():
    return "You declined to authorize MyResearchTool.", 200

# Existing eBay verification endpoint
@app.route("/", methods=["GET", "POST"])
def ebay_verification():
    if request.method == "GET":
        challenge = request.args.get("challenge")
        if challenge:
            return challenge, 200
    if request.method == "POST":
        # handle notifications here
        payload = request.get_json(force=True)
        print("Received event:", payload)
        return jsonify(status="received"), 200
    return "", 405

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
