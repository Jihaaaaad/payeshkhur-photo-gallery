from fastapi import FastAPI, File, UploadFile, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from PIL import Image
import secrets
import json

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_FILE = BASE_DIR / "data.json"

UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_MB = 10

# Keys
MEMBER_KEY = "gudmotalabib"      # required for uploading
ADMIN_KEY = "payeshkhur123"      # required for deleting (change later)

def safe_ext(filename: str) -> str:
    return Path(filename).suffix.lower()

def verify_image(path: Path) -> None:
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file")

def load_db() -> dict:
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_db(db: dict) -> None:
    DATA_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def upload_photo(
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str = Form(""),
    member_key: str = Form(...)
):
    # Member key check
    if member_key != MEMBER_KEY:
        raise HTTPException(status_code=403, detail="Wrong member key")

    ext = safe_ext(file.filename)
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Only JPG/PNG/WEBP allowed")

    data = await file.read()
    if len(data) > MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Max {MAX_MB}MB allowed")

    name = secrets.token_hex(12) + ext
    out_path = UPLOAD_DIR / name
    out_path.write_bytes(data)

    verify_image(out_path)

    db = load_db()
    db[name] = {
        "title": (title or "").strip(),
        "description": (description or "").strip()
    }
    save_db(db)

    return RedirectResponse(url="/gallery", status_code=303)

@app.get("/gallery", response_class=HTMLResponse)
def gallery(request: Request):
    files = sorted([p.name for p in UPLOAD_DIR.iterdir() if p.is_file()], reverse=True)
    db = load_db()

    items = []
    for f in files:
        meta = db.get(f, {})
        items.append({
            "filename": f,
            "title": meta.get("title", ""),
            "description": meta.get("description", "")
        })

    return templates.TemplateResponse("gallery.html", {"request": request, "items": items})

@app.get("/photo/{filename}", response_class=HTMLResponse)
def photo_view(request: Request, filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    db = load_db()
    meta = db.get(filename, {"title": "", "description": ""})

    return templates.TemplateResponse(
        "photo.html",
        {"request": request, "filename": filename, "meta": meta}
    )

@app.post("/delete")
def delete_photo(filename: str = Form(...), admin_key: str = Form(...)):
    if admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Wrong admin key")

    path = UPLOAD_DIR / filename
    if path.exists() and path.is_file():
        path.unlink()

    db = load_db()
    if filename in db:
        del db[filename]
        save_db(db)

    return RedirectResponse(url="/gallery", status_code=303)