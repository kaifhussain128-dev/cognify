from fastapi import FastAPI

app = FastAPI(title="AI StudyMate")


@app.get("/")
def home():
    return {
        "message": "Welcome to AI StudyMate!"
    }