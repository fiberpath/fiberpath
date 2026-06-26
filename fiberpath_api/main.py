"""Entry point for the FiberPath FastAPI service."""

from __future__ import annotations

from importlib.metadata import version

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fiberpath.planning import PlanningError
from fiberpath.simulation import SimulationError
from fiberpath.visualization import PlotError

from .routes import plan, plot, simulate, validate


def _bad_request(request: Request, exc: Exception) -> JSONResponse:
    """Map recoverable core-engine input errors to HTTP 400."""
    return JSONResponse(status_code=400, content={"detail": str(exc)})


def create_app() -> FastAPI:
    application = FastAPI(title="FiberPath API", version=version("fiberpath"))

    # The desktop webview fetches this sidecar cross-origin (its tauri:// origin
    # to 127.0.0.1:<port>), so the browser enforces CORS: without these headers
    # the webview can't read responses ("TypeError: Load failed") and POST
    # preflights fail. The sidecar binds loopback only and is never network-
    # exposed, so allowing any origin is safe.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe the sidecar supervisor polls for readiness."""
        return {"status": "ok"}

    application.include_router(plan.router, prefix="/plan", tags=["planning"])
    application.include_router(simulate.router, prefix="/simulate", tags=["simulation"])
    application.include_router(validate.router, prefix="/validate", tags=["validation"])
    application.include_router(plot.router, prefix="/plot", tags=["plot"])

    # Map core-engine input errors to 4xx instead of letting them surface as 500s.
    # PlanningError covers its subclass LayerValidationError via isinstance dispatch.
    application.add_exception_handler(PlanningError, _bad_request)
    application.add_exception_handler(SimulationError, _bad_request)
    application.add_exception_handler(PlotError, _bad_request)
    return application


app = create_app()
