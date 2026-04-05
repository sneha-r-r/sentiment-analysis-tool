from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal, User

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()
    if user and user.password == password:
        return user
    raise HTTPException(status_code=400, detail="Invalid username or password")
