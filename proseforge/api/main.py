from fastapi import FastAPI


def create_app() -> FastAPI:
    return FastAPI(title="ProseForge API", version="1.0.0")


app = create_app()
