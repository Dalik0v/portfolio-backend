# courses.py
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from db import get_db
from models import User, Course, UserCourse

router = APIRouter()

def get_current_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("user_id")
    return db.query(User).get(uid) if uid else None

def login_required(request: Request, db: Session):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return user

@router.get("/courses")
def courses_index(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    return request.app.state.templates.TemplateResponse(
        "courses/index.html", {"request": request, "user": user, "courses": courses}
    )

@router.get("/course/{course_id}")
def course_detail(course_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    course = db.query(Course).get(course_id)
    if not course:
        return RedirectResponse(url="/courses", status_code=status.HTTP_302_FOUND)
    # проверим купил ли пользователь
    owned = False
    if user:
        owned = db.query(UserCourse).filter_by(user_id=user.id, course_id=course.id).first() is not None
    return request.app.state.templates.TemplateResponse(
        "courses/detail.html", {"request": request, "user": user, "course": course, "owned": owned}
    )

@router.post("/course/{course_id}/buy")
def buy_course(course_id: int, request: Request, db: Session = Depends(get_db)):
    # требуется логин
    user = login_required(request, db)
    if isinstance(user, RedirectResponse):
        return user

    course = db.query(Course).get(course_id)
    if not course:
        return RedirectResponse(url="/courses", status_code=status.HTTP_302_FOUND)

    # уже куплен?
    exists = db.query(UserCourse).filter_by(user_id=user.id, course_id=course.id).first()
    if not exists:
        db.add(UserCourse(user_id=user.id, course_id=course.id))
        db.commit()
    return RedirectResponse(url=f"/my-courses", status_code=status.HTTP_302_FOUND)

@router.get("/my-courses")
def my_courses(request: Request, db: Session = Depends(get_db)):
    user = login_required(request, db)
    if isinstance(user, RedirectResponse):
        return user

    links = (
        db.query(UserCourse)
        .filter(UserCourse.user_id == user.id)
        .all()
    )
    # получим реальные курсы
    course_ids = [l.course_id for l in links]
    courses = db.query(Course).filter(Course.id.in_(course_ids)).all() if course_ids else []
    return request.app.state.templates.TemplateResponse(
        "courses/my.html", {"request": request, "user": user, "courses": courses}
    )
