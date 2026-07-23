"""AWS Lambda entrypoint — wraps the FastAPI app for API Gateway.

Mangum translates API Gateway events into ASGI calls, so the exact same app
runs locally under uvicorn and on Lambda with no branching.
"""
from mangum import Mangum

from backend.database import init_db
from backend.main import app

# FastAPI's startup event doesn't fire per Lambda invocation, so build the
# schema once here, at import time (i.e. once per cold start).
init_db()

handler = Mangum(app, lifespan="off")
