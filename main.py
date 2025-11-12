from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel, Field, Session, create_engine, select
import fitz  # PyMuPDF
import os

# -------------------- CONFIG --------------------
app = FastAPI(title="AI Resume Analyzer API")
# Allow frontend requests (CORS fix)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (you can restrict later)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_URL = "sqlite:///resume_data.db"
engine = create_engine(DB_URL, echo=False)

# -------------------- DATABASE MODEL --------------------
class ResumeData(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    total_words: int
    skills_found: str
    skills_missing: str
    resume_score: str
    suggestions: str

# -------------------- INITIALIZE DB --------------------
def init_db():
    SQLModel.metadata.create_all(engine)

init_db()

# -------------------- REQUIRED SKILLS --------------------
REQUIRED_SKILLS = [
    "python", "java", "c++", "machine learning", "fastapi", "sql",
    "data structures", "algorithms", "git", "api", "html", "css", "javascript"
]

# -------------------- ROUTES --------------------

@app.get("/")
def root():
    return {"message": "AI Resume Analyzer API is running 🚀"}


@app.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    text = extract_text_from_pdf(file_path)
    analysis = analyze_resume(text)

    resume_entry = ResumeData(
        filename=file.filename,
        total_words=len(text.split()),
        skills_found=", ".join(analysis["skills_found"]),
        skills_missing=", ".join(analysis["skills_missing"]),
        resume_score=analysis["resume_score"],
        suggestions="; ".join(analysis["suggestions"])
    )

    with Session(engine) as session:
        session.add(resume_entry)
        session.commit()
        session.refresh(resume_entry)

    return {
        "message": "Resume analyzed and saved successfully ✅",
        "resume_id": resume_entry.id,
        "analysis": analysis
    }


@app.get("/resumes")
def get_all_resumes():
    with Session(engine) as session:
        resumes = session.exec(select(ResumeData)).all()
        return resumes


@app.get("/resume/{resume_id}")
def get_resume(resume_id: int):
    with Session(engine) as session:
        resume = session.get(ResumeData, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        return resume


@app.delete("/resume/{resume_id}")
def delete_resume(resume_id: int):
    with Session(engine) as session:
        resume = session.get(ResumeData, resume_id)
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found")
        session.delete(resume)
        session.commit()
        return {"message": f"Deleted resume ID {resume_id}"}


@app.delete("/clear_all")
def clear_all_resumes():
    with Session(engine) as session:
        session.exec("DELETE FROM resumedata")
        session.commit()
    return {"message": "All resume analyses cleared 🗑️"}


# -------------------- HELPER FUNCTIONS --------------------
def extract_text_from_pdf(path):
    """Extract text from a PDF"""
    text = ""
    with fitz.open(path) as doc:
        for page in doc:
            text += page.get_text()
    return text.lower()


def analyze_resume(text):
    """Analyze resume text and score it"""
    found_skills = [skill for skill in REQUIRED_SKILLS if skill in text]
    missing_skills = [skill for skill in REQUIRED_SKILLS if skill not in text]
    score = int((len(found_skills) / len(REQUIRED_SKILLS)) * 100)

    suggestions = []
    if score < 60:
        suggestions.append("Add more technical skills relevant to your field.")
    if "project" not in text:
        suggestions.append("Include at least one project section.")
    if "experience" not in text:
        suggestions.append("Add an experience section even for internships.")

    return {
        "skills_found": found_skills,
        "skills_missing": missing_skills,
        "resume_score": f"{score}%",
        "suggestions": suggestions
    }
