# models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    purchases = relationship("UserCourse", back_populates="user", cascade="all, delete-orphan")

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    price = Column(Integer, nullable=False)     # цена в у.е. / центах
    image_url = Column(String, nullable=True)   # картинка карточки
    video_url = Column(String, nullable=True)   # превью/урок (iframe/youtube/mp4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    buyers = relationship("UserCourse", back_populates="course", cascade="all, delete-orphan")

class UserCourse(Base):
    __tablename__ = "user_courses"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="purchases")
    course = relationship("Course", back_populates="buyers")
