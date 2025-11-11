from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from db import Model

class User(BaseModel):
    username: str
    email: str | None = None
    password_hash: str

class UserORM(Model):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    
    def __repr__(self):
        return f'UserORM({self.id}, "{self.username}", "{self.password_hash}", "{self.email}")'
        
class Task(BaseModel):
        description: str
        correct_answer: str
        
class TaskORM(Model):
    __tablename__ = 'tasks'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[int]
    task_id: Mapped[int]
    description: Mapped[str] = mapped_column(String(2048), nullable=False)
    starting_code: Mapped[str] = mapped_column(String(512), nullable=True)
    correct_answer: Mapped[str] = mapped_column(String(1024), nullable=False)
    
class CategoryORM(Model):
    __tablename__ = 'categories'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)