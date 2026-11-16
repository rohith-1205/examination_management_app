import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "emp-dev-key-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///emp.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
