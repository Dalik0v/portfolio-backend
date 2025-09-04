from pathlib import Path
import os

from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from dotenv import load_dotenv
from db import Base, engine, get_db, SessionLocal
from models import User, Course, UserCourse
from auth import router as auth_router
from courses import router as courses_router

import stripe
from fastapi.responses import RedirectResponse

# --- Загружаем .env ---
load_dotenv()

# Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
APP_DOMAIN = os.getenv("APP_DOMAIN", "http://localhost:8000")

print("DEBUG STRIPE KEY:", stripe.api_key)

# --- Пути к папкам ---
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR

# --- Создаём приложение ---
app = FastAPI()

# --- База ---
Base.metadata.create_all(bind=engine)

# --- Шаблоны ---
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))
app.state.templates = templates

# --- Статика ---
app.mount("/static", StaticFiles(directory=str(ROOT_DIR / "static")), name="static")

# --- Сессии ---
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "dev"),
    session_cookie="portfolio_session",
    same_site="lax",
    https_only=True,
)

# --- Роуты ---
app.include_router(auth_router)
app.include_router(courses_router)

# === PAYMENTS ===
@app.post("/course/{course_id}/buy")
def buy_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    print("DEBUG SESSION FULL (buy):", dict(request.session))
    user_id = request.session.get("user_id")
    print("DEBUG SESSION user_id:", user_id)

    if not user_id:
        return RedirectResponse(url="/login")

    course = db.query(Course).get(course_id)
    if not course:
        return RedirectResponse(url="/courses")

    owned = db.query(UserCourse).filter_by(user_id=user_id, course_id=course_id).first()
    print("DEBUG BUY:", user_id, course_id, owned)
    if owned:
        return RedirectResponse(url="/my-courses")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": course.title},
                    "unit_amount": course.price * 100,
                },
                "quantity": 1,
            }],
            success_url=f"{APP_DOMAIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&course_id={course.id}",
            cancel_url=f"{APP_DOMAIN}/payment/cancel?course_id={course.id}",
        )
        print("DEBUG STRIPE SESSION:", session)
        print("DEBUG STRIPE URL:", session.url)
        return RedirectResponse(session.url, status_code=303)
    except Exception as e:
        print("Stripe error:", e)
        return RedirectResponse(url="/courses")


@app.get("/payment/success")
def payment_success(session_id: str, course_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")

    course = db.query(Course).get(course_id)
    if not course:
        return RedirectResponse(url="/courses")

    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == "paid":
        exists = db.query(UserCourse).filter_by(user_id=user_id, course_id=course_id).first()
        if not exists:
            db.add(UserCourse(user_id=user_id, course_id=course_id))
            db.commit()

    return templates.TemplateResponse(
        "payment_success.html",
        {"request": request, "user": db.query(User).get(user_id), "course": course},
    )


@app.get("/payment/cancel")
def payment_cancel(request: Request, course_id: int, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    course = db.query(Course).get(course_id)
    return templates.TemplateResponse(
        "payment_cancel.html",
        {"request": request, "user": user, "course": course},
    )

# === ADMIN ===
@app.get("/admin/reset-courses")
def admin_reset_courses(request: Request, db: Session = Depends(get_db)):
    """Очистить все покупки (user_courses). Только для user_id=1."""
    uid = request.session.get("user_id")
    if not uid or uid != 1:
        return RedirectResponse(url="/", status_code=302)

    deleted = db.query(UserCourse).delete()
    db.commit()
    print(f"DEBUG ADMIN: удалено {deleted} записей из user_courses")
    return {"status": "ok", "deleted": deleted}

# === Главная ===
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    print("DEBUG SESSION FULL (home):", dict(request.session))
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
def contact_post(
    request: Request,
    email: str = Form(...),
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    print("CONTACT:", email, message)
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse(
        "contact.html",
        {"request": request, "user": user, "success": True}
    )

# --- Демо-курсы (seed) ---
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
