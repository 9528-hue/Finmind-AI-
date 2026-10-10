from app.database.base import Base
from app.database.session import engine

Base.metadata.create_all(bind=engine)

print("Database tables created successfully!")
