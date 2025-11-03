from typing import Annotated
from openai import OpenAI
from pydantic import BaseModel, Field
from random import randint
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import os
from dotenv import load_dotenv
from urllib.parse import urlencode

import jwt
from fastapi import Depends, FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from models import User, UserORM, Task, TaskORM, CategoryORM
from db import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func

class Evaluation(BaseModel):
    score: int = Field(description="Score out of 10 for how well it meets description")
    comment: str = Field(description="Comment on how well the user answer meets the task description, and advice for how to improve it.")

app = FastAPI()
templates = Jinja2Templates(directory="templates")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
password_hash = PasswordHash.recommended()
load_dotenv()

SECRET_KEY = os.environ['SECRET_KEY']
ALGORITHM = os.environ['ALGORITHM']
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'])

def get_session():
    session = Session()
    try:
        yield session
    finally:
        session.close()
            
def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)
    
def get_password_hash(password):
    return password_hash.hash(password)
    
def authenticate_user(session, username: str, password: str):
    user = get_user(session, username)
    if not user:
        return False
    if not verify_password(password, user.password_hash):
        return False
    return user
        
def get_user(session, username: str):
    q = select(UserORM).where(UserORM.username==username)
    user_orm = session.scalar(q)
    if user_orm:
        return User(username=user_orm.username, email=user_orm.email, password_hash=user_orm.password_hash)
        
async def get_token(request: Request):
    cookie_token = request.cookies.get("access_token")
    if not cookie_token:
        raise HTTPException(status_code=401, detail="Could not authenticate")
    return cookie_token
    
async def get_current_user(token: Annotated[str, Depends(get_token)], session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(session, username=username)
    if not user:
        raise credentials_exception
    return user
    
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
    
@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    q = select(CategoryORM)
    categories = list(session.scalars(q))
    cats_as_dicts = []
    for category in categories:
        cats_as_dicts.append({"id": category.id, "name": category.name})
    return templates.TemplateResponse("index.html", {"request": request, "categories": cats_as_dicts})
    
    
@app.get("/mini-coi.js")
def mini_coi():
    return FileResponse(os.path.join(os.path.dirname(__file__), "mini-coi.js"),
                        media_type="application/javascript")
    
@app.get("/question", response_class=HTMLResponse)
async def question(request: Request, category: int = 1, task_id: int = 1, session: Session = Depends(get_session)):
    q = select(CategoryORM).where(CategoryORM.id == category)
    title = session.scalar(q).name
    q = select(TaskORM).where(TaskORM.category == category).where(TaskORM.task_id == task_id)
    task = session.scalar(q)
    description = task.description
    code = task.starting_code
    return templates.TemplateResponse("pyscript.html", {"request": request, "title": title, "description": description, "task_id": task_id, "code": code, "category": category})
    
@app.post("/answer", response_class=HTMLResponse)
async def answer(request: Request, user_code: str | None = Form(...), category: int = 1, task_id: int = 1, session: Session = Depends(get_session)):
    q = select(CategoryORM).where(CategoryORM.id == category)
    title = session.scalar(q).name
    q = select(TaskORM).where(TaskORM.category == category).where(TaskORM.task_id == task_id)
    task = session.scalar(q)
    description = task.description
    user_code = user_code.replace("\r", "")
    user_code = user_code.replace("\n", "\\n")
    user_code = user_code.replace("    ", "\\t")
    client = OpenAI(
      api_key=os.environ["XAI_API_KEY"],
      base_url="https://api.x.ai/v1",
    )

    completion = client.beta.chat.completions.parse(
      model="grok-4-fast-non-reasoning",
      messages=[
        {
          "role": "system",
          "content": "Decide how well the written code (in python) fulfills the listed task. Provide a score out of 10 and a comment explaining the evaluation and providing improvement advice."
        },
        {
          "role": "user",
          "content": f"Task Description: {description} User Answer: {user_code}"
        }
      ],
      response_format = Evaluation,
    )
    evaluation = completion.choices[0].message.parsed
    score = evaluation.score
    comment = evaluation.comment
    next_id = task_id + 1
    correct_code = task.correct_answer
    return templates.TemplateResponse("pyscript_answer.html", {"request": request, "title": title, "comment": comment, "next_id": next_id, "user_code": user_code, "correct_code": correct_code, "category": category})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...), session: Session = Depends(get_session)):
    user = get_user(session, username)
    params = urlencode({"error": "Invalid Login Credentials"})
    if not user:
        return RedirectResponse(f"/login?{params}", status_code=303)
    if not verify_password(password, user.password_hash):
        return RedirectResponse(f"/login?error={params}", status_code=303)
    token = create_access_token(data={"sub": user.username}, expires_delta = timedelta(minutes=30))
    response = RedirectResponse("/dashboard", status_code = 303)
    response.set_cookie(key = "access_token", value = token, httponly=True, samesite="lax", secure=False)
    return response
    
@app.get("/register", response_class=HTMLResponse)
async def register_form(request: Request, error: str | None = None):
    return templates.TemplateResponse("register.html", {"request": request, "error": error})
    
@app.post("/register")
async def register_submit(request: Request, username=Form(...), email=Form(...), password=Form(...), password_confirm=Form(...), session: Session = Depends(get_session)):
    q = select(UserORM).where(UserORM.username == username)
    if session.scalar(q):
        params = urlencode({"error": "Username already exists!"})
        return RedirectResponse(f"/register?{params}", status_code=303)
    if password != password_confirm:
        params = urlencode({"error": "Passwords do not match!"})
        return RedirectResponse(f"/register?{params}", status_code=303)
    pwd_hash = get_password_hash(password)
    user = UserORM(username=username, email=email, password_hash=pwd_hash)
    session.add(user)
    try:
        session.commit()
        return RedirectResponse("/login", status_code=303)
    except IntegrityError:
        params = urlencode({"error": "Username or email already exists"})
        return RedirectResponse(f"/register?{params}", status_code=303)
    except:
        session.rollback()
        params = urlencode({"error": "Database Error"})
        return RedirectResponse(f"/register?{params}", status_code=303)

    
@app.get("/dashboard")
async def dashboard(request: Request, user: Annotated[str, Depends(get_current_user)]):
    return {"username": user.username, "email": user.email}
 

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str | None = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("access_token")
    return response

