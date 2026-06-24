"""Entry point for the FiberPath FastAPI service."""

from __future__ import annotations

from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fiberpath.planning import PlanningError
from fiberpath.simulation import SimulationError

from .routes import plan, simulate, stream, validate


def _bad_request(request: Request, exc: Exception) -> JSONResponse:
    """Map recoverable core-engine input errors to HTTP 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def create_app() -> FastAPI:
    application = FastAPI(title="FiberPath API", version=version("fiberpath"))
    application.include_router(plan.router, prefix="/plan", tags=["planning"])
    application.include_router(simulate.router, prefix="/simulate", tags=["simulation"])
    application.include_router(validate.router, prefix="/validate", tags=["validation"])
    application.include_router(stream.router, prefix="/stream", tags=["stream"])

    # Map core-engine input errors to 4xx instead of letting them surface as 500s.
    # PlanningError covers its subclass LayerValidationError via isinstance dispatch.
    application.add_exception_handler(PlanningError, _bad_request)
    application.add_exception_handler(SimulationError, _bad_request)
    return application


app = create_app()
