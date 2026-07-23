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


# ══════════════════════════════════════════════════════════════════════
# DATA SOURCES — Evidence extraction prompt
# ══════════════════════════════════════════════════════════════════════

def build_extraction_prompt(evidence_type: str, raw_text: str) -> str:
    """
    Builds a JSON-only extraction prompt. Sibling to build_prompt() —
    used by the Data Sources page to turn pasted, unstructured text
    (LinkedIn post, review, etc.) into a participant profile.

    This is an EDITORIAL extraction, not a summarization. The output
    feeds StoryForge's existing story-generation pipeline, so each
    field must read like profile content an editor wrote — not text
    copied or lightly reworded from the source.
    """
    evidence_labels = {
        "linkedin_post":      "LinkedIn Post",
        "internship_review":  "Internship Review",
        "training_review":    "Training / Certification Review",
    }
    evidence_label = evidence_labels.get(evidence_type, evidence_type)

    return f"""
You are an editorial assistant for Cloud Counselage / IAC's StoryForge platform.
Your job is to read raw, informal text from a {evidence_label} and produce a
structured PARTICIPANT PROFILE from it — not a summary of the post.

This profile will later be used as input to an AI story generator, so every
field must read as clean, reusable, professional profile content, written in
your own words. It must NOT read like a paraphrased or copied social media post.

SOURCE TEXT ({evidence_label}):
\"\"\"
{raw_text.strip()}
\"\"\"

IMPORTANT — WHAT TO IGNORE:
- Hashtags (e.g. #Grateful #Blessed) — ignore entirely, never include them.
- Emojis — strip them out completely.
- Congratulatory / celebratory language ("So excited to share...", "Thrilled to
  announce...", "Grateful for this opportunity...") — this is social framing,
  not participant information. Discard it.
- Repetitive marketing or program-promotion language (e.g. boilerplate praise
  of the organization) — discard it.
- Generic closing statements ("Looking forward to what's next!", "Excited for
  this new chapter!") — discard them.
- Tagged names of other people, companies, or organizations that are not the
  participant themselves — do not include them as achievements.

WHAT TO DO INSTEAD:
- Identify the real signal buried in the post: what program/training did the
  participant complete, what skill or capability did they demonstrate, what
  changed for them professionally.
- REWRITE that signal as concise, third-person(ish) editorial profile content
  — the way a program coordinator would describe the participant in an
  internal record, not the way the participant described themselves on
  social media.
- Prefer general, reusable phrasing over restating specific post wording.

  Example — NOT this (copied/paraphrased from the post):
    "Completed the IAC Employability Pledge."

  Example — INSTEAD, something like this (editorial profile language):
    "Demonstrated commitment to professional development by completing
    employability training focused on career readiness and workplace ethics."

- If a field cannot be reasonably inferred from the text, leave it as an
  empty string "" — do NOT invent facts, and do NOT pad a field with
  restated post content just to fill it in.
- The "name" field is OPTIONAL. LinkedIn post text very often does not
  include the author's name (it's shown separately by LinkedIn's UI, not in
  the post body). If no name is clearly stated in the text, leave "name" as
  "" — this is expected and NOT an error. Do not guess a name from a tagged
  organization or program name.

Return ONLY a valid JSON object, with no markdown fences, no commentary,
and no text before or after it, in exactly this shape:

{{
  "name": "",
  "email": "",
  "program": "",
  "domain": "",
  "background": "",
  "achievements": "",
  "challenges": "",
  "outcomes": "",
  "linkedin_url": ""
}}

Field guidance (all values, where present, must be editorial profile
language per the instructions above — never copied/paraphrased post text):
- name: the participant's full name, ONLY if explicitly stated in the text. Usually "".
- email: only include if explicitly present in the text; otherwise "".
- program: the internship/training program name if mentioned, else "".
- domain: the technical/professional domain (e.g. Web Development, Data Science), else "".
- background: 1-2 sentences of editorial framing for the participant's starting point or context, if inferable.
- achievements: 1-2 sentences rewriting what they accomplished as profile-worthy editorial content.
- challenges: 1-2 sentences on obstacles overcome, only if genuinely present — do not invent.
- outcomes: 1-2 sentences on measurable results or professional impact, rewritten editorially.
- linkedin_url: only include if an actual LinkedIn URL is present in the text.

Output the JSON object now:
""".strip()