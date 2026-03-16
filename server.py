from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from auth import auth
import uvicorn

app = FastAPI()

class Login(BaseModel):
    username: str
    password: str

@app.post("/login")
def login(data: Login):
    try:
        result = auth(data.username, data.password)
        return {
            "success": True,
            "role": result["role"],
            "info": result["info"]
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=9000)
