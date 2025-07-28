from flask import Flask, Response, request, redirect, url_for
import logging

app = Flask(__name__)

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)

@app.route('/')
def home():
    return """
    <h1>eBay Verification Endpoint</h1>
    <p>Available routes:</p>
    <ul>
        <li><a href="/privacy">Privacy Policy</a></li>
        <li><a href="/ebay/auth-success?code=TEST">Test Auth Success</a></li>
        <li><a href="/ebay/auth-fail">Test Auth Fail</a></li>
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
        <p><strong>Last updated:</strong> July 28, 2025</p>

        <h2>1. Information We Access</h2>
        <p>My Research Tool only accesses publicly available, read-only item and seller data via the eBay API. We do <em>not</em> access or store any private eBay member information (e.g. buyer names, addresses, payment details).</p>

        <h2>2. No Personal Data Collection</h2>
        <p>We do not collect, store, or share any personally identifiable information (PII) about you. All data shown in the application comes directly from eBay's public endpoints at the moment you request it.</p>

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

@app.route('/ebay/auth-success')
def auth_success():
    # Log the incoming request for debugging
    code = request.args.get('code')
    state = request.args.get('state')
    
    app.logger.info(f"Auth success called with code: {code}, state: {state}")
    app.logger.info(f"All args: {request.args}")
    
    html_content = f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Authorization Success - My Research Tool</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .success {{ color: green; }}
            .code {{ background: #f0f0f0; padding: 10px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1 class="success">✅ Authorization Successful!</h1>
        <p>Thank you for authorizing My Research Tool!</p>
        {f'<div class="code"><strong>Authorization Code:</strong> {code}</div>' if code else ''}
        <p>You can now close this window and return to the application.</p>
        <hr>
        <p><small>Received at: {request.url}</small></p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

@app.route('/ebay/auth-fail')
def auth_fail():
    # Log the incoming request for debugging
    error = request.args.get('error')
    error_description = request.args.get('error_description')
    
    app.logger.info(f"Auth fail called with error: {error}")
    app.logger.info(f"All args: {request.args}")
    
    html_content = f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <title>Authorization Declined - My Research Tool</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .error {{ color: red; }}
        </style>
    </head>
    <body>
        <h1 class="error">❌ Authorization Declined</h1>
        <p>You have declined to authorize the application.</p>
        {f'<p><strong>Error:</strong> {error}</p>' if error else ''}
        {f'<p><strong>Description:</strong> {error_description}</p>' if error_description else ''}
        <p>Please try again if you wish to continue.</p>
        <hr>
        <p><small>Received at: {request.url}</small></p>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html')

# Legacy routes for backward compatibility
@app.route('/callback')
def callback():
    code = request.args.get("code")
    if code:
        return redirect(url_for('auth_success', code=code))
    else:
        return redirect(url_for('auth_fail'))

@app.route('/decline')
def decline():
    return redirect(url_for('auth_fail'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
