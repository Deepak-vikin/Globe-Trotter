from contextlib import asynccontextmanager
        #For Startup and Shutdown of Fast API Events.
from fastapi import FastAPI, HTTPException, status
        #status is used for HTTP status codes.
from fastapi.middleware.cors import CORSMiddleware
        #Connect Front end to Back end.
        #Without CORS, we cannot access the API from the Front end,Browser Blocks it.
from pydantic import BaseModel, EmailStr, Field
        #BaseModel is used to define the structure of the data.
        #EmailStr is used to validate the email.
        #Field is used to add metadata to the data.

import database as db
        #Importing database.py as db

#STARTUP/SHUTDOWN LOGIC
@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()                          # create tables if not exist.
    print("[API] Globe Trotter API is running 🌍")
    yield                                 # Everything before yield runs on startup.
    print("[API] Shutting down.")

app = FastAPI(
    title="Globe Trotter API",
    description="Auth backend for Globe Trotter.",
    version="1.1.0",
    lifespan=lifespan,  #Connect the Startup/shutdown logic.
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    #ALLOWS ALL DOMAINS.
    allow_credentials=True, #ALLOWS AUTHENTICATION.
    allow_methods=["*"],    #ALLOWS ALL HTTP METHODS.
    allow_headers=["*"],    #ALLOWS ALL HEADERS.
)

#Schemas
class RegisterRequest(BaseModel):
    name:     str      = Field(..., min_length=1, max_length=100)
    email:    EmailStr
    password: str      = Field(..., min_length=6)
    city:     str      = Field(default="", max_length=100)
    state:    str      = Field(default="", max_length=100)
    country:  str      = Field(default="", max_length=100)

class LoginRequest(BaseModel):
    email:    EmailStr
    password: str      = Field(..., min_length=1)

class UserResponse(BaseModel):
    id:         int
    name:       str
    email:      str
    city:       str
    state:      str
    country:    str
    created_at: str

#Routes
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "Globe Trotter API"}

@app.post("/api/register", response_model=UserResponse,
          status_code=status.HTTP_201_CREATED, tags=["Auth"])
def register(p: RegisterRequest):
    try:
        return db.create_user(
            p.name, p.email, p.password,
            city=p.city, state=p.state, country=p.country
        )
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
