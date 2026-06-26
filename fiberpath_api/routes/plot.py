"""Plot/preview endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from fiberpath.visualization import render_plot

from ..schemas import GcodeRequest

router = APIRouter()


@router.post("", responses={200: {"content": {"image/png": {}}}})
def plot(payload: GcodeRequest) -> Response:
    """Render an unwrapped 2D preview of a G-code program as a PNG."""
    program = payload.gcode.splitlines()
    if not any(line.strip() for line in program):
        raise HTTPException(status_code=400, detail="gcode contained no commands")
    png = render_plot(program).to_png_bytes()
    return Response(content=png, media_type="image/png")
