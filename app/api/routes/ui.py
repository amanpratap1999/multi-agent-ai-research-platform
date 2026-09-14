from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(tags=["UI"])


@router.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Renders the Adversarial War Room split-screen operations dashboard."""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"title": "Adversarial War Room | Multi-Agent AI Platform"}
    )
