from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

@app.post("/")
async def respond():
    return JSONResponse(content={"verificationToken": "my-verification-token-123"})
