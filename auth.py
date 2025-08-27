from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from db import get_db
from models import User

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p: str) -> str:
    return pwd_context.hash(p)

def verify_password(p: str, hp: str) -> bool:
    return pwd_context.verify(p, hp)

@router.get("/login")
def login_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/login.html", {"request": request})

@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        # простая ошибка — без флешей, чтобы быстро
        return request.app.state.templates.TemplateResponse("auth/login.html", {"request": request, "error": "Неверный логин или пароль"}, status_code=400)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/register")
def register_page(request: Request):
    return request.app.state.templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    exists = db.query(User).filter(User.email == email).first()
    if exists:
        return request.app.state.templates.TemplateResponse("auth/register.html", {"request": request, "error": "Такой email уже есть"}, status_code=400)
    user = User(email=email, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
