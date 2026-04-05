from fastapi import FastAPI, Form, Depends
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
import praw
from textblob import TextBlob
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.lib import colors
import os
from datetime import datetime

# ---------------- DB Setup ----------------
DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)
    history = relationship("History", back_populates="user")

class History(Base):
    __tablename__ = "history"
    id = Column(Integer, primary_key=True)
    subreddit = Column(String)
    positive = Column(String)
    negative = Column(String)
    neutral = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="history")

Base.metadata.create_all(bind=engine)

# ---------------- FastAPI App ----------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------- Reddit API Setup ----------------
reddit = praw.Reddit(
    client_id="AmJiqtl0oidQr4TljBSRUw",
    client_secret="lXyHbhjpwmsMXOQjAWj7ESSR52ItfQ",
    user_agent="sentiment-app-v1"
)

# ---------------- User Routes ----------------
@app.post("/register")
def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == username).first():
        return {"status": "error", "message": "User already exists"}
    new_user = User(username=username, password=password)
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "Registered successfully"}

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.password == password).first()
    if user:
        return {"status": "success", "message": "Login successful", "user_id": user.id}
    return {"status": "error", "message": "Invalid credentials"}

# ---------------- Sentiment Analysis ----------------
# ---------------- Sentiment Analysis ----------------
@app.get("/analyze/{user_id}/{subreddit_name}")
def analyze(user_id: int, subreddit_name: str, db: Session = Depends(get_db), limit: int = 100):
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"status": "error", "message": "User not found"}

    # Fetch comments
    comments = []
    for submission in reddit.subreddit(subreddit_name).hot(limit=5):
        submission.comments.replace_more(limit=0)
        for comment in submission.comments.list()[:limit]:
            comments.append(comment.body)

    positive, negative, neutral = 0, 0, 0
    for text in comments:
        polarity = TextBlob(text).sentiment.polarity
        if polarity > 0:
            positive += 1
        elif polarity < 0:
            negative += 1
        else:
            neutral += 1

    total = positive + negative + neutral
    if total == 0:
        return {"status": "error", "message": "No comments found"}

    result = {
        "positive": round((positive / total) * 100, 2),
        "negative": round((negative / total) * 100, 2),
        "neutral": round((neutral / total) * 100, 2),
        "total_comments": total
    }

    # Save history correctly
    history_entry = History(
        subreddit=subreddit_name,
        positive=str(result["positive"]),
        negative=str(result["negative"]),
        neutral=str(result["neutral"]),
        user=user  # associate full user object, safer
    )
    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)  # ensures object gets ID and timestamp
    print(f"✅ Saved history for {user.username}: {history_entry.subreddit} at {history_entry.timestamp}")

    return {"status": "success", "result": result, "history_id": history_entry.id}


# ---------------- Get History ----------------
@app.get("/history/{user_id}")
def get_history(user_id: int, db: Session = Depends(get_db)):
    history = db.query(History).filter(History.user_id == user_id).order_by(History.timestamp.desc()).all()
    if not history:
        return {"status": "error", "message": "No history found for this user"}

    result = []
    for h in history:
        result.append({
            "id": h.id,
            "subreddit": h.subreddit,
            "positive": h.positive,
            "negative": h.negative,
            "neutral": h.neutral,
            "timestamp": h.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "pdf_url": f"/download/{user_id}/{h.id}"
        })
    return {"status": "success", "history": result}

# ---------------- Download PDF per record with Pie Chart ----------------
@app.get("/download/{user_id}/{history_id}")
def download_history_pdf(user_id: int, history_id: int, db: Session = Depends(get_db)):
    record = db.query(History).filter(History.user_id == user_id, History.id == history_id).first()
    if not record:
        return {"status": "error", "message": "Record not found"}

    os.makedirs("reports", exist_ok=True)
    filename = f"reports/report_user_{user_id}_{history_id}.pdf"

    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    content = []

    # Title
    content.append(Paragraph("Reddit Sentiment Analysis Report", styles['Title']))
    content.append(Spacer(1, 20))

    # Record details
    content.append(Paragraph(
        f"<b>Subreddit:</b> {record.subreddit} <br/>"
        f"<b>Positive:</b> {record.positive}% <br/>"
        f"<b>Negative:</b> {record.negative}% <br/>"
        f"<b>Neutral:</b> {record.neutral}% <br/>"
        f"<b>Date:</b> {record.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        styles['Normal']
    ))
    content.append(Spacer(1, 30))

    # Pie chart
    drawing = Drawing(300, 200)
    pie = Pie()
    pie.x = 125
    pie.y = 15
    pie.width = 150
    pie.height = 150
    pie.data = [
        float(record.positive),
        float(record.negative),
        float(record.neutral)
    ]
    pie.labels = [
    f"Positive ({float(record.positive):.2f}%)",
    f"Negative ({float(record.negative):.2f}%)",
    f"Neutral ({float(record.neutral):.2f}%)"
    ]
    pie.sideLabels = True
    pie.simpleLabels = False
    pie.slices.strokeWidth = 0.5
    pie.slices[0].fillColor = colors.green
    pie.slices[1].fillColor = colors.red
    pie.slices[2].fillColor = colors.orange  # yellow
    drawing.add(pie)
    content.append(drawing)

    doc.build(content)
    return FileResponse(filename, media_type="application/pdf", filename=f"user_{user_id}_history_{history_id}.pdf")
