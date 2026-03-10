from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

import database as db
import recommendation_agent as rec


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    print("[API] Globe Trotter API is running 🌍")
    yield
    print("[API] Shutting down.")


app = FastAPI(title="Globe Trotter API", version="1.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    name:     str      = Field(..., min_length=1, max_length=100)
    email:    EmailStr
    password: str      = Field(..., min_length=6)
    city:     str      = Field(..., min_length=1, max_length=100)
    state:    str      = Field(..., min_length=1, max_length=100)
    country:  str      = Field(..., min_length=1, max_length=100)

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str = Field(..., min_length=1)

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    city: str
    state: str
    country: str
    created_at: str


# ── Routes ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Globe Trotter API"}

@app.post("/api/register", response_model=UserResponse,
          status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(p: RegisterRequest):
    try:
        return db.create_user(p.name, p.email, p.password,
                              city=p.city, state=p.state, country=p.country)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))

@app.post("/api/login", response_model=UserResponse, tags=["Auth"])
def login(p: LoginRequest):
    user = db.find_user_by_email(p.email)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            detail="No account found. Please register first.")
    if not db.verify_password(p.password, user["password"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect password. Please try again.")
    return {k: user[k] for k in ("id", "name", "email", "city", "state", "country", "created_at")}

@app.get("/api/users", response_model=list[UserResponse], tags=["Admin"])
def list_users():
    return db.get_all_users()

@app.get("/api/recommendations", tags=["Recommendations"])
async def recommendations(email: str):
    user = db.find_user_by_email(email)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found.")
    return await rec.get_recommendations(
        user.get("city", ""),
        user.get("state", ""),
        user.get("country", "India"),
    )
