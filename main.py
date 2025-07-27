from flask import Flask, Response, request

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>eBay Verification Endpoint</h1>
    <p>Available routes:</p>
    <ul>
      <li><a href="/privacy">Privacy Policy</a></li>
      <li><a href="/callback?code=TEST">Callback</a></li>
      <li><a href="/decline">Decline</a></li>
    </ul>
    """

@app.route('/privacy')
def privacy():
    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Privacy Policy - My Research Tool</title>
    </head>
    <body>
      <h1>Privacy Policy</h1>
      <p><strong>Last updated:</strong> July 26, 2025</p>

      <h2>1. Information We Access</h2>
      <p>My Research Tool only accesses publicly available, read-only item and seller data via the eBay API. We do <em>not</em> access or store any private eBay member information (e.g. buyer names, addresses, payment details).</p>

      <h2>2. No Personal Data Collection</h2>
      <p>We do not collect, store, or share any personally identifiable information (PII) about you. All data shown in the application comes directly from eBay’s public endpoints at the moment you request it.</p>

      <h2>3. Data Retention</h2>
      <p>We do not retain any eBay user or listing data beyond the lifetime of your browser session. No databases, logs, or caches persist your data on our servers.</p>

      <h2>4. Cookies & Analytics</h2>
      <p>We do not use cookies or third-party analytics tools to track your activity.</p>

      <h2>5. Contact Us</h2>
      <p>If you have any questions or concerns about this Privacy Policy, please contact us at <a href="mailto:hello@myresearchtool.com">hello@myresearchtool.com</a>.</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/callback')
def callback():
    code = request.args.get("code")
    if code:
        return f"<h1>Authorization code received:</h1><p>{code}</p>"
    else:
        return "<h1>No authorization code found.</h1>", 400

@app.route('/decline')
def decline():
    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Authorization Declined</title>
    </head>
    <body>
      <h1>Authorization Declined</h1>
      <p>You have declined to authorize the application. Please try again if you wish to continue.</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/ebay/auth-success')
def auth_success():
    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Authorization Success</title>
    </head>
    <body>
      <h1>Authorization Successful</h1>
      <p>Thank you for authorizing the app. You can now close this window.</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/ebay/auth-fail')
def auth_fail():
    html_content = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <title>Authorization Failed</title>
    </head>
    <body>
      <h1>Authorization Declined</h1>
      <p>You have declined to authorize the application. Please try again if you wish to continue.</p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
