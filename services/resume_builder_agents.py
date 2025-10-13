from __future__ import annotations

"""
AgentKit definitions for the ResumeBuilderV2 pipeline.

This module contains the agent graph that previously lived in AgentKitDocs/ResumeBuilderV2.py.
It is imported by the resume builder service and (optionally) ChatKit integrations.
"""

from agents import (
    Agent,
    ModelSettings,
    Runner,
    RunConfig,
    TResponseInputItem,
    WebSearchTool,
    function_tool,
)
from pydantic import BaseModel


# Tool definitions ---------------------------------------------------------------------------

@function_tool
def extract_ats_keywords(job_url: str, top_n: int) -> list[str]:  # pragma: no cover - stub
    """
    Placeholder tool hook that allows the AgentKit graph to call back into the host
    application. The actual implementation lives in AgentKit and is not required for
    local execution. Returning an empty array keeps the tool contract intact.
    """

    return []


web_search_preview = WebSearchTool(
    search_context_size="medium",
    user_location={
        "type": "approximate",
    },
)


# Schema definitions -------------------------------------------------------------------------


class JobScraperSchemaCompany(BaseModel):
    name: str
    industry: str
    size: str


class JobScraperSchemaLocationsItem(BaseModel):
    type: str
    city: str
    country: str


class JobScraperSchemaRole(BaseModel):
    title: str
    level: str
    description: str


class JobScraperSchemaTeam(BaseModel):
    name: str
    size: float
    function: str


class JobScraperSchemaExperience(BaseModel):
    years_required: float
    minimum_degree: str
    other_requirements: str


class JobScraperSchemaSkills(BaseModel):
    technical: list[str]
    soft: list[str]


class JobScraperSchema(BaseModel):
    company: JobScraperSchemaCompany
    locations: list[JobScraperSchemaLocationsItem]
    role: JobScraperSchemaRole
    team: JobScraperSchemaTeam
    experience: JobScraperSchemaExperience
    skills: JobScraperSchemaSkills


class BulletGeneratorOutputParsed(BaseModel):
    reasoning: str
    plan: list[str]
    resume_bullet_points: list[str]


class BulletGeneratorSchema(BaseModel):
    resume_bullets_text: str
    output_parsed: BulletGeneratorOutputParsed


# Agent definitions --------------------------------------------------------------------------


job_scraper = Agent(
    name="Job scraper",
    instructions="""Extract structured job information from a provided job application URL by thoroughly analyzing the content of the job posting. Your main objectives are:

- Carefully examine all content in the job posting.
- Reason step-by-step through the text to identify and map each relevant detail into the correct category.
- Only capture explicit information present in the posting; do not infer or assume any skills, experience, or locations not directly stated.
- For every entry found, consider if it fits more than one category and include it in all relevant lists.
- Use concise paraphrasing for skill and experience entries, but retain the original wording as much as possible.

# Steps

1. Carefully read and internally reason through the job posting, considering each section and statement.
2. Extract and categorize the following:
    - Required skills (as an array)
    - Nice to have skills (as an array)
    - Required experience (as an array, include years if explicitly stated)
    - Location(s) (as an array, list as provided)
    - Desired skills (as an array)
    - Any other noteworthy requirements, qualifications, or differentiators not covered above (describe briefly, as an array)
3. Do not infer, generalize, or add items not clearly present in the posting.
4. If a piece of information fits multiple categories, include it in all that apply.
5. If a category is not mentioned in the posting, use an empty list for that field.
6. Internally think through each piece of extracted information before determining its final categorization and output.

# Output Format

Respond with a single, well-formatted JSON object using the schema below. No extra text or commentary. Use empty arrays for absent categories.

{
  "required_skills": [],
  "nice_to_have_skills": [],
  "required_experience": [],
  "locations": [],
  "desired_skills": [],
  "other_noteworthy": []
}

# Example

Input: [Job Application URL]

Output:
{
  "required_skills": ["Python", "REST APIs", "SQL"],
  "nice_to_have_skills": ["AWS", "Docker"],
  "required_experience": ["3+ years software development", "Bachelor’s degree in Computer Science"],
  "locations": ["Remote", "San Francisco, CA"],
  "desired_skills": ["Team leadership", "Agile methodology familiarity"],
  "other_noteworthy": ["Sponsorship not available", "Must be able to travel up to 20%"]
}

(Note: In actual use, the array lengths and wording may differ based on the posting.)

# Notes

- Never include information or entries that are not explicitly mentioned in the job posting.
- Be diligent in your extraction and categorization; retain text as close to the original as is practical.
- Multiple relevant fields for one entry are encouraged if justified.
- Persist through the content until ALL relevant job information is captured and mapped appropriately before producing your final answer.

Reminder: Only output the JSON object. Think step-by-step internally before finalizing and outputting your structured answer.""",
    model="gpt-4o-mini",
    tools=[
        extract_ats_keywords,
        web_search_preview,
    ],
    output_type=JobScraperSchema,
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=2048,
        store=True,
    ),
)


bullet_generator = Agent(
    name="Bullet Generator",
    instructions="""Plan, then generate. First, analyze a given job description in JSON format, then devise a clear outline or plan for bullet points before actually crafting the final resume bullets.

Use web search to identify strong bullet point examples for similar roles. Structure your output so that it documents the step-by-step planning and thought process before generating the resume bullets. Focus on highlighting relevant technical skills and measurable achievements, using varied, impactful language and avoiding repetition.

Follow these guidelines:
- **Step 1: Analyze** the job JSON to identify key responsibilities, required technical skills, and desired outcomes.
- **Step 2: Research**—Use web search to find current, effective resume bullet point examples for roles with similar titles and skills. Summarize your findings.
- **Step 3: Plan**—Translate key findings into a brief outline or plan for your bullets. For each main job responsibility or skill, jot down what each future bullet point should cover (action, skill, potential impact, or measurement).
- **Step 4: Generate** concise and achievement-focused bullet points, following your plan. For each, ensure:
  1. A clear description of the action or achievement.
  2. Relevant technical skill(s) are highlighted.
  3. Measurable impact or value is shown where possible (use placeholders like [quantifiable result] or [technical tool] if actual metrics are missing).
  4. No significant overlap or repetitive phrasing between bullets.

**Output Format:**
Provide a JSON object with the following structure:
{
  "reasoning": "Your analysis and planning rationale",
  "plan": ["Step 1 description", "Step 2 description", ...],
  "resume_bullet_points": ["Bullet 1", "Bullet 2", ...]
}

**Example Input:**
{
  "title": "Software Engineer",
  "company": "Acme Corp",
  "responsibilities": [
    "Develop and maintain web applications using React and Node.js",
    "Collaborate with cross-functional teams to define and deliver features",
    "Write unit and integration tests",
    "Optimize application performance"
  ],
  "skills": ["React", "Node.js", "JavaScript", "Testing", "Agile"]
}

**Example Output:**
{
  "reasoning": "Analyzed the job JSON for core technical skills and tasks. Web search highlighted the importance of quantifying results in resume bullets for Software Engineers, as well as emphasizing collaboration and performance. Planned to cover core development, testing, teamwork, and performance optimization, avoiding duplication between bullets.",
  "plan": [
    "Summarize web development (React/Node.js) responsibilities as one bullet, focusing on scale and user benefit.",
    "Dedicate a bullet to feature delivery with cross-functional teams, highlighting acceleration or improvement.",
    "Include a bullet on writing and maintaining tests, emphasizing bug reduction or product quality.",
    "Cover performance optimization, referencing impact (e.g., speed, efficiency)."
  ],
  "resume_bullet_points": [
    "Engineered and maintained scalable web applications using React and Node.js, improving user experience for [user base size] clients.",
    "Collaborated with cross-functional teams to deliver [number] new features, accelerating project timelines by [percentage]%.",
    "Developed comprehensive unit and integration tests, reducing production bugs by [percentage]%.",
    "Optimized web application performance, achieving a [metric]% increase in loading speed."
  ]
}

(Real examples should illustrate a clearly reasoned plan before bullet generation, and 3–6 achievement-oriented bullets with specific quantifiable results or technologies where present in the input, using placeholders—e.g., [percentage], [user base size]—if exact numbers are unavailable.)

**Edge Cases & Details:**
- If quantitative data is missing, use placeholders like [metric] or [result].
- If responsibilities are repetitive, combine them into a single, clearer plan and bullet.
- Prioritize coverage of all technical skills; avoid language repetition.
- If planning reveals overlap, merge or reorganize your plan before generating bullets.

---

**REMINDER:**
- Plan before generating: Show your outline for the bullet points.
- Output MUST be valid JSON with reasoning, plan, and resume_bullet_points keys.
""",
    model="gpt-4o-mini",
    tools=[
        web_search_preview,
    ],
    model_settings=ModelSettings(
        temperature=1,
        top_p=1,
        parallel_tool_calls=True,
        max_tokens=2048,
        store=True,
    ),
)


__all__ = [
    "RunConfig",
    "Runner",
    "TResponseInputItem",
    "JobScraperSchema",
    "BulletGeneratorSchema",
    "BulletGeneratorOutputParsed",
    "job_scraper",
    "bullet_generator",
]
