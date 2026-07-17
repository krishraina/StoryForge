"""
core/constants.py
"""

# ── Story formats ────────────────────────────────────────────────────
STORY_FORMATS = {
    "linkedin": {
        "label": "LinkedIn Post",
        "icon": "💼",
        "word_range": (150, 300),
        "description": "Professional network post highlighting impact and growth",
    },
    "narrative": {
        "label": "Long-Form Narrative",
        "icon": "📖",
        "word_range": (400, 700),
        "description": "Editorial story with context, journey, and transformation arc",
    },
    "testimonial": {
        "label": "Testimonial Snippet",
        "icon": "💬",
        "word_range": (80, 150),
        "description": "First-person voice, concise and emotionally resonant",
    },
    "case_study": {
        "label": "Case Study",
        "icon": "📊",
        "word_range": (500, 900),
        "description": "Structured impact case study with measurable outcomes",
    },
}

# ── Workflow statuses ────────────────────────────────────────────────
STORY_STATUSES = {
    "draft":     {"label": "Draft",     "color": "#94a3b8"},
    "in_review": {"label": "In Review", "color": "#f59e0b"},
    "approved":  {"label": "Approved",  "color": "#10b981"},
    "rejected":  {"label": "Rejected",  "color": "#ef4444"},
    "published": {"label": "Published", "color": "#6366f1"},
}

# ── Consent ──────────────────────────────────────────────────────────
CONSENT_LEVELS = {
    "full":       "Full consent — story, name, and photo may be published",
    "anonymized": "Anonymized — story may be published without identifying details",
    "internal":   "Internal only — story for internal records, not public",
    "none":       "No consent — do not generate or publish",
}

# ── Programs ─────────────────────────────────────────────────────────
PROGRAMS = [
    "Global Professional Internship (GPI)",
]

DOMAINS = [
    "Web Development",
    "Data Science & Analytics",
    "Artificial Intelligence & Machine Learning",
    "Digital Marketing",
    "Business Development & Sales",
    "Human Resource Management",
    "Finance & Accounting",
    "Graphic Design & UI/UX",
    "Content Writing & Copywriting",
    "Cybersecurity",
    "Cloud Computing",
    "Mobile App Development",
    "Python Programming",
    "Java Development",
    "Project Management",
    "Social Media Management",
    "Video Editing & Production",
    "Research & Development",
    "Operations Management",
    "Customer Relationship Management",
]

# ── AI Disclosure ─────────────────────────────────────────────────────
AI_DISCLOSURE = (
    "This story was generated with AI assistance (Google Gemini) "
    "using participant-provided data. It has been reviewed and edited "
    "by the IAC editorial team before publication."
)