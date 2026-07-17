from core.constants import STORY_FORMATS, AI_DISCLOSURE


def build_prompt(participant: dict, fmt: str) -> str:
    spec = STORY_FORMATS.get(fmt, {})
    word_min, word_max = spec.get("word_range", (150, 400))
    fmt_label = spec.get("label", fmt)
    fmt_desc  = spec.get("description", "")

    name         = (participant.get("name") or "the participant")
    program      = (participant.get("program") or "the program")
    cohort       = (participant.get("cohort") or "")
    background   = (participant.get("background") or "").strip()
    achievements = (participant.get("achievements") or "").strip()
    challenges   = (participant.get("challenges") or "").strip()
    outcomes     = (participant.get("outcomes") or "").strip()

    cohort_str = f"(Cohort: {cohort})" if cohort else ""

    base = f"""
You are an expert impact storyteller working for an organization called Cloud Counselage / IAC.
Your task is to write a compelling, human, and authentic {fmt_label} for a program participant.Write the complete full-length content. Do not stop mid-sentence. Do not truncate.

PARTICIPANT:
Name: {name}
Program: {program} {cohort_str}

BACKGROUND:
{background or "Not provided."}

KEY ACHIEVEMENTS:
{achievements or "Not provided."}

CHALLENGES OVERCOME:
{challenges or "Not provided."}

OUTCOMES & IMPACT:
{outcomes or "Not provided."}

FORMAT: {fmt_label}
DESCRIPTION: {fmt_desc}
WORD COUNT: {word_min}–{word_max} words

WRITING INSTRUCTIONS:
- Write in a warm, professional editorial voice
- Focus on transformation and real human impact
- Be specific — use the details provided, do not invent facts
- Avoid generic platitudes and AI-sounding filler phrases
- Do NOT include AI disclosure text — that is added separately
- Do NOT add a title or heading — output the story body only
- Write the complete full-length content. Do not stop mid-sentence. Do not truncate.
- Match the format: {fmt_label}
{_format_specific_instructions(fmt)}

Output the story now:
""".strip()

    return base


def _format_specific_instructions(fmt: str) -> str:
    instructions = {
        "linkedin": (
            "- Start with a hook — a bold or emotional opening line\n"
            "- Use short paragraphs (2–3 sentences max)\n"
            "- End with a forward-looking or inspiring close\n"
            "- Appropriate for a professional network audience"
        ),
        "narrative": (
            "- Use a narrative arc: context → challenge → turning point → outcome\n"
            "- Include at least one vivid, specific detail or moment\n"
            "- Write in third person editorial voice\n"
            "- Paragraph structure should feel like a magazine feature"
        ),
        "testimonial": (
            "- Write in first person (participant's voice)\n"
            "- Sound authentic and personal, not corporate\n"
            "- One clear, memorable insight or moment\n"
            "- End with a statement of impact or gratitude"
        ),
        "case_study": (
            "- Use a structured format: Background → Challenge → Approach → Results\n"
            "- Emphasize measurable outcomes where data is available\n"
            "- Maintain a professional, analytical tone\n"
            "- Suitable for organizational reports and grant applications"
        ),
    }
    return instructions.get(fmt, "")