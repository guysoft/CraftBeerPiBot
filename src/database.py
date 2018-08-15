from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from functools import wraps, partial
from sqlalchemy.orm import sessionmaker
import string
import random

Base = declarative_base()

class TelegramUser(Base):
    __tablename__ = "telegram_users"
    id = Column(Integer, primary_key=True)
    name = Column(String(30))
    role = Column(String(10))

    def __init__(self, id, name, role):
        self.id = id
        self.name = name
        self.role = role

    def __repr__(self):
        return "%id=s,role=%s,name=%s" % (self.id, self.role, self.name)


def mysql_init_db(uri, settings):
    mysql_engine = create_engine(uri)
    mysql_engine.execute("CREATE DATABASE IF NOT EXISTS {0} ".format(settings["db"]["db_name"]))
    return

def insert_new_user_to_db(engine, telegram_id, name, role="guest"):
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    entry = TelegramUser(id=telegram_id, name=name, role=role)
    session.add(entry)
    session.commit()
    return

def get_id(existing_ids=[]):
    new_id = ''.join(random.sample((string.ascii_uppercase+string.digits + string.ascii_lowercase),4))
    if new_id in existing_ids:
        return get_id(existing_ids)
    return new_id


def has_access(engine, telegram_id, roles):
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    result = session.query(TelegramUser).filter(TelegramUser.id == telegram_id).first()
    if result is not None:
        return result.role in roles
    return False

def has_user(engine, telegram_id):
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    result = session.query(TelegramUser).filter(TelegramUser.id == telegram_id).count()
    return result == 1


def restricted(func=None, *, roles=["user", "admin"]):
    if func is None:
        return partial(restricted, roles=roles)

    @wraps(func)
    def wrapper(*args, **kwargs):
        self = args[0]
        bot = args[1]
        update = args[2]

        user_id = update.effective_user.id
        if not has_access(self.engine, user_id, roles):
            bot.send_message(chat_id=update.message.chat_id,
                             text="You have no permission to use this command, use web UI to give authorization.",
                             reply_to_message_id=update.message.message_id)
            return
        return func(*args, **kwargs)
    return wrapper
