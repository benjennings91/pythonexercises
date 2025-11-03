import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import DeclarativeBase, sessionmaker

class Model(DeclarativeBase):
    metadata = MetaData()
    
load_dotenv()

engine=create_engine(os.environ['DATABASE_URL'])
Session = sessionmaker(engine)