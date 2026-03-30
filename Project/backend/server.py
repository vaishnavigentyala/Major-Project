from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone

# Optional LLM integration (not required for local dev).
# If unavailable, we fall back to a deterministic recommendation engine.
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
except Exception:  # pragma: no cover
    LlmChat = None  # type: ignore
    UserMessage = None  # type: ignore


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StudentProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    age: int
    grade_level: str
    gpa: float
    subjects: Dict[str, float]  # {"Math": 95, "Science": 88, ...}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StudentProfileCreate(BaseModel):
    name: str
    email: str
    age: int
    grade_level: str
    gpa: float
    subjects: Dict[str, float]

class AptitudeTest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    technical_score: int
    creative_score: int
    technical_answers: Dict[str, str]
    creative_answers: Dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AptitudeTestCreate(BaseModel):
    student_id: str
    technical_answers: Dict[str, str]
    creative_answers: Dict[str, str]

class BehavioralTest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    personality_type: str
    interests: List[str]
    work_style: str
    answers: Dict[str, str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BehavioralTestCreate(BaseModel):
    student_id: str
    answers: Dict[str, str]

class CareerPrediction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    recommended_careers: List[Dict[str, str]]
    analysis: str
    strengths: List[str]
    improvement_areas: List[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Helper function to calculate scores
def calculate_technical_score(answers: Dict[str, str]) -> int:
    correct_answers = {
        "q1": "b",  # Algorithm complexity
        "q2": "c",  # Programming concept
        "q3": "a",  # Data structure
        "q4": "b",  # Engineering principle
        "q5": "c"   # Problem solving
    }
    score = sum(20 for k, v in answers.items() if correct_answers.get(k) == v)
    return score

def calculate_creative_score(answers: Dict[str, str]) -> int:
    # Creative answers are more subjective, give points based on engagement
    score = len([v for v in answers.values() if v]) * 20
    return min(score, 100)

def analyze_personality(answers: Dict[str, str]) -> str:
    # Simple personality analysis based on answer patterns
    if answers.get("q1") == "a" and answers.get("q3") == "a":
        return "Analytical Thinker"
    elif answers.get("q1") == "b" and answers.get("q2") == "a":
        return "Creative Innovator"
    elif answers.get("q3") == "b" and answers.get("q4") == "a":
        return "Practical Problem Solver"
    else:
        return "Balanced Learner"

def _top_subjects(subjects: Dict[str, float], n: int = 3) -> List[str]:
    return [k for k, _ in sorted(subjects.items(), key=lambda kv: kv[1], reverse=True)[:n]]

def _fallback_career_recommendation(
    student: Dict,
    aptitude: Dict,
    behavioral: Dict,
) -> Dict[str, object]:
    """
    Local, deterministic fallback that returns the same JSON structure
    expected by the frontend.
    """
    technical = int(aptitude.get("technical_score", 0) or 0)
    creative = int(aptitude.get("creative_score", 0) or 0)
    interests = behavioral.get("interests") or []
    if isinstance(interests, str):
        interests = [interests]
    interests_lower = {str(i).strip().lower() for i in interests if str(i).strip()}
    subjects = student.get("subjects") or {}
    top_subjects = _top_subjects(subjects, n=3) if isinstance(subjects, dict) else []

    careers: List[Dict[str, str]] = []

    def add(title: str, match: int, reason: str):
        careers.append({"title": title, "match_score": f"{max(0, min(match, 99))}%", "reason": reason})

    # Score-driven picks
    if technical >= 80:
        add(
            "Software Engineer",
            92,
            f"Strong technical aptitude ({technical}/100) and solid academics; good fit for building real-world systems.",
        )
        add(
            "Data Analyst / Data Scientist",
            89,
            f"High technical score ({technical}/100) plus strong performance in {', '.join(top_subjects) or 'core subjects'}.",
        )
        add(
            "Cybersecurity Analyst",
            84,
            "Technical strength aligns well with security fundamentals and structured problem-solving.",
        )
    if creative >= 80:
        add(
            "UI/UX Designer",
            90,
            f"High creative engagement ({creative}/100) suggests strong user empathy and ideation.",
        )
        add(
            "Product Designer / Creative Technologist",
            86,
            "Blend of creativity and technology suits building interactive, user-focused experiences.",
        )

    # Interest-driven picks
    if "technology" in interests_lower or "ai" in interests_lower or "innovation" in interests_lower:
        add(
            "AI / Machine Learning Engineer",
            91 if technical >= 70 else 80,
            "Interest in technology/AI and a strong technical base suits applied machine learning projects.",
        )
    if "arts & design" in interests_lower or "design" in interests_lower:
        add(
            "Graphic / Visual Designer",
            82,
            "Expressive and creative interests align with visual communication and branding work.",
        )
    if "science & research" in interests_lower or "research" in interests_lower:
        add(
            "Research Assistant / Research Intern",
            80,
            "Curiosity-driven interests align with experimentation, documentation, and analysis.",
        )

    # Ensure we always return 5
    defaults = [
        ("Project Manager (Tech)", 78, "Organizes teams and timelines; good for collaborative and goal-oriented students."),
        ("Business Analyst", 77, "Translates needs into solutions; fits balanced profiles with communication strengths."),
        ("Cloud Support / DevOps Associate", 76, "Operational + technical role; good stepping-stone into infrastructure."),
        ("Digital Marketing Analyst", 74, "Combines creativity with data; useful if you enjoy communication and metrics."),
        ("STEM Educator / Tutor", 73, "Shares knowledge and builds mastery; strong for high-performing students."),
    ]
    seen = set()
    deduped: List[Dict[str, str]] = []
    for c in careers:
        if c["title"] in seen:
            continue
        seen.add(c["title"])
        deduped.append(c)
    careers = deduped
    for title, match, reason in defaults:
        if len(careers) >= 5:
            break
        if title in seen:
            continue
        add(title, match, reason)
        seen.add(title)
    careers = careers[:5]

    strengths: List[str] = []
    if technical >= 70:
        strengths.append("Strong problem-solving and logical thinking")
    if creative >= 70:
        strengths.append("Creative ideation and willingness to explore solutions")
    if top_subjects:
        strengths.append(f"Academic strengths in {', '.join(top_subjects)}")
    if behavioral.get("work_style") == "Collaborative":
        strengths.append("Collaborative work style")
    strengths = strengths[:4] or ["Balanced academic and personal profile"]

    improvement_areas: List[str] = []
    if technical < 60:
        improvement_areas.append("Strengthen technical fundamentals (data structures, basic programming, logic)")
    if creative < 60:
        improvement_areas.append("Practice ideation and communication (projects, writing, presentations)")
    improvement_areas.extend(
        [
            "Build a portfolio (mini-projects, competitions, volunteer work)",
            "Explore careers via short courses and informational interviews",
        ]
    )
    improvement_areas = improvement_areas[:4]

    analysis = (
        f"Based on technical ({technical}/100) and creative ({creative}/100) aptitude plus interests "
        f"({', '.join(interests) if interests else 'not specified'}), these roles are strong starting points. "
        "You’ll get the best results by pairing coursework with small, real projects."
    )

    return {
        "careers": careers,
        "strengths": strengths,
        "improvement_areas": improvement_areas,
        "analysis": analysis,
    }

# Routes
@api_router.get("/")
async def root():
    return {"message": "Career Guidance System API"}

@api_router.post("/students", response_model=StudentProfile)
async def create_student(input: StudentProfileCreate):
    student_dict = input.model_dump()
    student_obj = StudentProfile(**student_dict)
    
    doc = student_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.students.insert_one(doc)
    return student_obj

@api_router.get("/students/{student_id}", response_model=StudentProfile)
async def get_student(student_id: str):
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    if isinstance(student['created_at'], str):
        student['created_at'] = datetime.fromisoformat(student['created_at'])
    
    return student

@api_router.post("/aptitude-test", response_model=AptitudeTest)
async def submit_aptitude_test(input: AptitudeTestCreate):
    # Calculate scores
    technical_score = calculate_technical_score(input.technical_answers)
    creative_score = calculate_creative_score(input.creative_answers)
    
    test_obj = AptitudeTest(
        student_id=input.student_id,
        technical_score=technical_score,
        creative_score=creative_score,
        technical_answers=input.technical_answers,
        creative_answers=input.creative_answers
    )
    
    doc = test_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.aptitude_tests.insert_one(doc)
    return test_obj

@api_router.post("/behavioral-test", response_model=BehavioralTest)
async def submit_behavioral_test(input: BehavioralTestCreate):
    # Analyze personality and extract insights
    personality_type = analyze_personality(input.answers)
    
    interests = []
    if input.answers.get("q2") == "a":
        interests.append("Technology")
    if input.answers.get("q2") == "b":
        interests.append("Arts & Design")
    if input.answers.get("q2") == "c":
        interests.append("Science & Research")
    if input.answers.get("q5"):
        interests.extend(input.answers["q5"].split(","))
    
    work_style = "Collaborative" if input.answers.get("q4") == "a" else "Independent"
    
    test_obj = BehavioralTest(
        student_id=input.student_id,
        personality_type=personality_type,
        interests=interests,
        work_style=work_style,
        answers=input.answers
    )
    
    doc = test_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    
    await db.behavioral_tests.insert_one(doc)
    return test_obj

@api_router.post("/predict-career/{student_id}")
async def predict_career(student_id: str):
    # Fetch student data
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    aptitude = await db.aptitude_tests.find_one({"student_id": student_id}, {"_id": 0})
    behavioral = await db.behavioral_tests.find_one({"student_id": student_id}, {"_id": 0})
    
    if not aptitude or not behavioral:
        raise HTTPException(status_code=400, detail="Complete all tests first")
    
    try:
        ai_result: Dict[str, object]

        # If the Emergent LLM integration is available, use it. Otherwise fall back.
        if LlmChat is not None and UserMessage is not None and os.environ.get("EMERGENT_LLM_KEY"):
            prompt = f"""
Analyze this student's profile and provide career recommendations:

Student Profile:
- Name: {student.get('name')}
- Grade Level: {student.get('grade_level')}
- GPA: {student.get('gpa')}
- Subject Scores: {student.get('subjects')}

Aptitude Test Results:
- Technical Score: {aptitude.get('technical_score')}/100
- Creative Score: {aptitude.get('creative_score')}/100

Behavioral Assessment:
- Personality Type: {behavioral.get('personality_type')}
- Interests: {', '.join(behavioral.get('interests', []))}
- Work Style: {behavioral.get('work_style')}

Provide:
1. Top 5 career recommendations (mix of traditional and emerging careers)
2. Detailed analysis of their strengths
3. Areas for improvement
4. Brief explanation for each career recommendation

Format your response as JSON with this structure:
{{
  "careers": [
    {{"title": "Career Name", "match_score": "95%", "reason": "Why this career fits"}}
  ],
  "strengths": ["strength1", "strength2"],
  "improvement_areas": ["area1", "area2"],
  "analysis": "Overall analysis text"
}}
"""

            llm_key = os.environ.get("EMERGENT_LLM_KEY")
            chat = (
                LlmChat(
                    api_key=llm_key,
                    session_id=f"career-prediction-{student_id}",
                    system_message="You are an expert career counselor with deep knowledge of traditional and emerging career paths.",
                )
                .with_model("openai", "gpt-5.1")
            )
            response = await chat.send_message(UserMessage(text=prompt))

            import json

            response_text = str(response).strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            ai_result = json.loads(response_text)
        else:
            ai_result = _fallback_career_recommendation(student, aptitude, behavioral)
        
        # Create prediction record
        prediction_obj = CareerPrediction(
            student_id=student_id,
            recommended_careers=ai_result.get("careers", []),
            analysis=ai_result.get("analysis", ""),
            strengths=ai_result.get("strengths", []),
            improvement_areas=ai_result.get("improvement_areas", [])
        )
        
        doc = prediction_obj.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.career_predictions.insert_one(doc)
        return prediction_obj
        
    except Exception as e:
        logging.error(f"Error in career prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating prediction: {str(e)}")

@api_router.get("/prediction/{student_id}", response_model=CareerPrediction)
async def get_prediction(student_id: str):
    prediction = await db.career_predictions.find_one({"student_id": student_id}, {"_id": 0})
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    if isinstance(prediction['created_at'], str):
        prediction['created_at'] = datetime.fromisoformat(prediction['created_at'])
    
    return prediction

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()