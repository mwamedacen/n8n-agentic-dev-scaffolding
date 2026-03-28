"""
Cloud Functions Service - Dynamic Function Endpoints

A FastAPI application providing endpoints for processing functions.
Endpoints are automatically generated from the function registry.
"""

import asyncio
import inspect
from functools import partial

from fastapi import FastAPI, HTTPException, Query

import registry

app = FastAPI(title="Cloud Functions Service")


@app.get("/")
async def root():
    """Root health check endpoint."""
    return {"status": "ok", "service": "Cloud Functions Service"}


@app.get("/health")
async def health():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "service": "Cloud Functions Service",
        "functions": list(registry.EXPOSED_FUNCTIONS.keys()),
    }


@app.get("/echo/{message}")
async def echo(message: str):
    """Echo back the provided message."""
    return {"echo": message}


def create_endpoint(func):
    """Create a FastAPI endpoint from a function.

    Uses asyncio.to_thread for non-blocking execution of synchronous functions.
    """
    sig = inspect.signature(func)

    async def endpoint(**kwargs):
        try:
            bound = sig.bind(**kwargs)
            bound.apply_defaults()
            result = await asyncio.to_thread(partial(func, **bound.arguments))
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Build query parameters from the function signature
    params = []
    for name, param in sig.parameters.items():
        default = param.default if param.default is not inspect.Parameter.empty else ...
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=Query(default),
                annotation=annotation,
            )
        )

    endpoint.__signature__ = inspect.Signature(params)
    endpoint.__name__ = func.__name__
    endpoint.__doc__ = func.__doc__
    return endpoint


def register_functions():
    """Register all exposed functions as API endpoints."""
    for name, func in registry.EXPOSED_FUNCTIONS.items():
        endpoint = create_endpoint(func)
        app.post(f"/{name}", name=name)(endpoint)


register_functions()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
