"""Main application entry point."""

from fastapi import FastAPI

app = FastAPI(title="AI Agent Webapp API")

@app.get("/")
def read_root():
    return {"message": "Welcome to AI Agent Webapp API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
