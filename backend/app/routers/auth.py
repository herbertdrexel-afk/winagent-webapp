"""Authentication & user management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import (
    create_access_token, get_current_user, hash_password,
    require_admin, verify_password,
)
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_approved: bool

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str
    password: str


class UpdateUserRequest(BaseModel):
    is_approved: bool | None = None
    role: str | None = None
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Falscher Benutzername oder Passwort")
    if not user.is_approved:
        raise HTTPException(status_code=403, detail="Account noch nicht freigegeben")
    token = create_access_token(user.id, user.username, user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == body.username).first():
        raise HTTPException(status_code=409, detail="Benutzername bereits vergeben")
    # First user becomes auto-approved admin
    is_first = db.query(models.User).count() == 0
    user = models.User(
        username=body.username,
        password_hash=hash_password(body.password),
        role="admin" if is_first else "user",
        is_approved=is_first,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(models.User).order_by(models.User.id).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if body.is_approved is not None:
        user.is_approved = body.is_approved
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(400, "Rolle muss 'admin' oder 'user' sein")
        user.role = body.role
    if body.password:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    current_user: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(400, "Eigenen Account kann man nicht löschen")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    db.delete(user)
    db.commit()
