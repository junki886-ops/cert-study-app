from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    options = Column(Text, nullable=True)   # JSON string으로 보기 저장
    answer = Column(String(50), nullable=True)
    explanation = Column(Text, nullable=True)

# DB 연결
engine = create_engine("sqlite:///data/questions.db", echo=True)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)
