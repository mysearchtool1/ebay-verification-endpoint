from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['POST'])
def ebay_verification():
    data = request.get_json()
    challenge = data.get('challenge')
    if challenge:
        return 'hyebaytoken123', 200  # Make sure this token matches the one in eBay
    return 'Missing challenge', 400
