from fastapi import FastAPI


from app.routes import user_routers

app = FastAPI(
    title="Novichok++ Trading API",
    description="Backend for Novichok++ bot",
    version="0.1.0"
)


app.include_router(user_routers.router)


@app.get("/health")
def health():
    return {"status": "ok"}
