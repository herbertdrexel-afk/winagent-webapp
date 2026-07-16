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
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language: str | None = "de"
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
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    language: str | None = None


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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    is_self = user_id == current_user.id
    is_admin = current_user.role == "admin"
    if not is_self and not is_admin:
        raise HTTPException(403, "Nicht erlaubt")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if is_admin:
        if body.is_approved is not None:
            user.is_approved = body.is_approved
        if body.role is not None:
            if body.role not in ("admin", "user"):
                raise HTTPException(400, "Rolle muss 'admin' oder 'user' sein")
            user.role = body.role
    if body.password:
        user.password_hash = hash_password(body.password)
    if body.email is not None:
        user.email = body.email or None
    if body.first_name is not None:
        user.first_name = body.first_name or None
    if body.last_name is not None:
        user.last_name = body.last_name or None
    if body.language is not None:
        user.language = body.language or "de"
    db.commit()
    db.refresh(user)
    return user


class SupplierAccessRequest(BaseModel):
    codes: list[str]


@router.get("/users/{user_id}/suppliers", response_model=list[str])
def get_user_suppliers(
    user_id: int,
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Zugewiesene Lieferanten-Codes eines Users. Leere Liste = alle sichtbar."""
    rows = (
        db.query(models.Supplier.code)
        .join(models.UserSupplierAccess,
              models.UserSupplierAccess.supplier_id == models.Supplier.id)
        .filter(models.UserSupplierAccess.user_id == user_id)
        .order_by(models.Supplier.code)
        .all()
    )
    return [r[0] for r in rows]


@router.put("/users/{user_id}/suppliers", response_model=list[str])
def set_user_suppliers(
    user_id: int,
    body: SupplierAccessRequest,
    _: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lieferanten-Freigaben eines Users komplett ersetzen. Leere Liste = alle sichtbar."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Benutzer nicht gefunden")

    codes = sorted({c.upper().strip() for c in body.codes if c.strip()})
    suppliers = (
        db.query(models.Supplier).filter(models.Supplier.code.in_(codes)).all()
        if codes else []
    )
    found_codes = {s.code for s in suppliers}
    missing = [c for c in codes if c not in found_codes]
    if missing:
        raise HTTPException(400, f"Unbekannte Lieferanten-Codes: {', '.join(missing)}")

    db.query(models.UserSupplierAccess).filter_by(user_id=user_id).delete()
    for s in suppliers:
        db.add(models.UserSupplierAccess(user_id=user_id, supplier_id=s.id))
    db.commit()
    return sorted(found_codes)


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
