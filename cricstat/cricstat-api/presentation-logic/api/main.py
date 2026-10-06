"""ASGI entry point: uvicorn presentation_logic.api.main:app"""
from presentation_logic.api.app import create_app

app = create_app()
