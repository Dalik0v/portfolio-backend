# payments.py
import os
import stripe
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from db import get_db
from models import Course, UserCourse

router = APIRouter()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
YOUR_DOMAIN = os.getenv("APP_DOMAIN", "http://localhost:8000")

@router.post("/course/{course_id}/buy")
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
        success_url=f"{YOUR_DOMAIN}/payment/success?session_id={{CHECKOUT_SESSION_ID}}&course_id={course.id}",
        cancel_url=f"{YOUR_DOMAIN}/payment/cancel",
    )
    return RedirectResponse(session.url, status_code=303)
