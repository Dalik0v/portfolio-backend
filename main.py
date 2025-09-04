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

# --- Загружаем .env ---
load_dotenv()

# Stripe
stripe.api_key = os.getenv("sk_test_51S3hu5HGFepJfndUCgpHRMmInhenTTZz1RshpVx1t0MaqFblgWuj6iZrabL7T3PYvweg9NSBkAiDnV3L5faZIpz600RjoNgOr8")
APP_DOMAIN = os.getenv("APP_DOMAIN", "http://localhost:8000")

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
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev"))

# --- Роуты ---
app.include_router(auth_router)
app.include_router(courses_router)

# === PAYMENTS ===
from fastapi.responses import RedirectResponse

@app.post("/course/{course_id}/buy")
def buy_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")

    course = db.query(Course).get(course_id)
    if not course:
        return RedirectResponse(url="/courses")

    # создаём оплату в Stripe
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": course.title},
                "unit_amount": course.price * 100,  # цена в центах
            },
            "quantity": 1,
        }],
        success_url=f"{APP_DOMAIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&course_id={course.id}",
        cancel_url=f"{APP_DOMAIN}/payment/cancel",
    )
    return RedirectResponse(session.url, status_code=303)


@app.get("/payment/success")
def payment_success(session_id: str, course_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login")

    # проверим в Stripe
    session = stripe.checkout.Session.retrieve(session_id)
    if session.payment_status == "paid":
        exists = db.query(UserCourse).filter_by(user_id=user_id, course_id=course_id).first()
        if not exists:
            db.add(UserCourse(user_id=user_id, course_id=course_id))
            db.commit()

    return templates.TemplateResponse("payment_success.html", {"request": request, "user": db.query(User).get(user_id)})


@app.get("/payment/cancel")
def payment_cancel(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    user = db.query(User).get(uid) if uid else None
    return templates.TemplateResponse("payment_cancel.html", {"request": request, "user": user})

# === Главная ===
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
