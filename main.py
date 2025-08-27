# main.py
from pathlib import Path
import os

from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from dotenv import load_dotenv
load_dotenv()  # подтянет SECRET_KEY и т.п. из .env

from db import Base, engine, get_db, SessionLocal
from models import User, Course
from auth import router as auth_router
from courses import router as courses_router

app = FastAPI()

# --- Пути к папкам ---
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR if (BASE_DIR / "templates").exists() else BASE_DIR.parent

# 1) база
Base.metadata.create_all(bind=engine)

# 2) шаблоны
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))
app.state.templates = templates

# 3) статика
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")

# 4) сессии — секрет берём из окружения
app.add_middleware(SessionMiddleware, secret_key=os.getenv("c6f46ef010fe98f8f567bed2041c9000ca12a7783a46cac2223cb23d21dc92ce", "dev"))

# 5) роуты
app.include_router(auth_router)
app.include_router(courses_router)

# 6) главная
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("home.html", {"request": request, "user": user})

# === Pages ===
@app.get("/projects")
def projects(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("projects.html", {"request": request, "user": user})

@app.get("/about")
def about(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("about.html", {"request": request, "user": user})

@app.get("/contact")
def contact(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("contact.html", {"request": request, "user": user})

@app.post("/contact")
def contact_post(request: Request, email: str = Form(...), message: str = Form(...), db: Session = Depends(get_db)):
    print("CONTACT:", email, message)
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("contact.html", {"request": request, "user": user, "success": True})

# 7) сид курсов
def seed_courses():
    db = SessionLocal()
    try:
        if db.query(Course).count() == 0:
            demo = [
                Course(
                    title="Mastering Python for Web",
                    description="Основы Python, FastAPI, работа с БД, деплой.",
                    price=29,
                    image_url="/static/img/python.png",
                    video_url="https://www.youtube.com/embed/AJTtXXXM0z0",
                ),
                Course(
                    title="Frontend Basics",
                    description="HTML/CSS/JS, компоненты и сборка.",
                    price=99,
                    image_url="/static/img/frontend.png",
                    video_url="https://www.youtube.com/embed/AJTtXXXM0z0",
                ),
                Course(
                    title="Fullstack Pro",
                    description="Полный курс: от БД до продакшена.",
                    price=249,
                    image_url="/static/img/fullstack.png",
                    video_url="https://www.youtube.com/embed/AJTtXXXM0z0",
                ),
            ]
            db.add_all(demo)
            db.commit()
        else:
            # обновим видео у существующих курсов (если раньше был рикролл)
            vids = {
                "Mastering Python for Web": "https://www.youtube.com/embed/AJTtXXXM0z0",
                "Frontend Basics": "https://www.youtube.com/embed/AJTtXXXM0z0",
                "Fullstack Pro": "https://www.youtube.com/embed/AJTtXXXM0z0",
            }
            for title, url in vids.items():
                c = db.query(Course).filter(Course.title == title).first()
                if c and c.video_url != url:
                    c.video_url = url
            db.commit()
    finally:
        db.close()

seed_courses()
