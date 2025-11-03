import csv
from db import Model, Session, engine
from models import UserORM, TaskORM, CategoryORM
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

def main():
    Model.metadata.drop_all(engine)
    Model.metadata.create_all(engine)
    
    with Session() as session:
        with session.begin():
            with open('data\\initial_users.csv', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pwd_hash = password_hash.hash(row['password'])
                    user = UserORM(username=row['username'], email=row['email'], password_hash=pwd_hash)
                    session.add(user)
            with open('data\\questions.csv', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    task = TaskORM(category=row['category'], task_id =row['task_id'], description=row['description'], starting_code = row['starting_code'], correct_answer=row['correct_answer'])
                    session.add(task)
            with open('data\\categories.csv', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    category = CategoryORM(id=row['id'], name=row['name'])
                    session.add(category)
   

if __name__ == '__main__':
    main()