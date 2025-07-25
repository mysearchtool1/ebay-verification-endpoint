from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "eBay endpoint is live 🎉"}

@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.body()
    print(body)
    return {"status": "received"}

