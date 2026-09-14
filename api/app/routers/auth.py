"""Authentication endpoints — login (bcrypt verify in-DB), current user.

Brute-force defence: after MAX_FAILED_ATTEMPTS the account is locked for
LOCKOUT_MINUTES; every failure and lockout is written to security_events.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from app.auth import (
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
    ROLE_LABELS,
    client_ip,
    get_current_user,
    log_security_event,
    make_token,
    record_audit,
)
from app.db import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, db=Depends(get_db)):
    ip = client_ip(request)
    email = body.email.lower().strip()
    row = db.execute(
        text(
            "SELECT id, email, role, is_active, failed_attempts, locked_until, "
            "       (password_hash = crypt(:pw, password_hash)) AS pw_ok "
            "FROM users WHERE email = :email"
        ),
        {"email": email, "pw": body.password},
    ).mappings().first()

    # Uniform error message — never reveal whether the email exists.
    invalid = HTTPException(status_code=401, detail="Invalid email or password")

    if not row:
        log_security_event(db, "login_failed", "medium", email, ip, "Unknown account")
        raise invalid

    if not row["is_active"]:
        log_security_event(db, "login_failed", "high", email, ip, "Disabled account")
        raise invalid

    if row["locked_until"] is not None:
        locked = db.execute(
            text("SELECT locked_until > now() AS still_locked FROM users WHERE id = :id"),
            {"id": row["id"]},
        ).scalar()
        if locked:
            log_security_event(db, "login_locked", "high", email, ip, "Attempt on locked account")
            raise HTTPException(status_code=423, detail="Account temporarily locked. Try again later.")

    if not row["pw_ok"]:
        attempts = (row["failed_attempts"] or 0) + 1
        if attempts >= MAX_FAILED_ATTEMPTS:
            db.execute(
                text(
                    "UPDATE users SET failed_attempts = :a, "
                    "locked_until = now() + (:mins || ' minutes')::interval WHERE id = :id"
                ),
                {"a": attempts, "mins": LOCKOUT_MINUTES, "id": row["id"]},
            )
            db.commit()
            log_security_event(db, "login_locked", "high", email, ip,
                               f"Account locked after {attempts} failed attempts")
        else:
            db.execute(text("UPDATE users SET failed_attempts = :a WHERE id = :id"),
                       {"a": attempts, "id": row["id"]})
            db.commit()
            log_security_event(db, "login_failed", "medium", email, ip,
                               f"Invalid password (attempt {attempts})")
        raise invalid

    # Success — reset counters, stamp last_login, issue token.
    db.execute(
        text("UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = now() WHERE id = :id"),
        {"id": row["id"]},
    )
    db.commit()
    user = {"id": str(row["id"]), "email": row["email"], "role": row["role"]}
    token = make_token(user)
    record_audit(db, user, "login", f"user:{row['email']}", ip=ip)
    return {
        "token": token,
        "user": {"email": row["email"], "role": row["role"], "role_label": ROLE_LABELS.get(row["role"], row["role"])},
    }


@router.get("/me")
def me(user=Depends(get_current_user)):
    return {
        "email": user["email"],
        "full_name": user["full_name"],
        "role": user["role"],
        "role_label": ROLE_LABELS.get(user["role"], user["role"]),
        "level": user["level"],
        "department_id": user["department_id"],
        "department_name": user["department_name"],
        "station_id": user["station_id"],
        "district": user["district"],
    }
