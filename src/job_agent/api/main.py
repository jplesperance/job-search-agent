from fastapi import FastAPI

app = FastAPI(title="Job Agent System", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
