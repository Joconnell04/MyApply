from agents import WebSearchTool, Agent, ModelSettings, RunContextWrapper, TResponseInputItem, Runner, RunConfig
from openai import AsyncOpenAI
from types import SimpleNamespace
from guardrails.runtime import load_config_bundle, instantiate_guardrails, run_guardrails
from pydantic import BaseModel
from openai.types.shared.reasoning import Reasoning

# Tool definitions
web_search_preview = WebSearchTool(
  search_context_size="medium",
  user_location={
    "type": "approximate"
  }
)
# Shared client for guardrails and file search
client = AsyncOpenAI()
ctx = SimpleNamespace(guardrail_llm=client)
# Guardrails definitions
guardrails_config = {
  "guardrails": [

  ]
}
guardrails_validate_resume_config = {
  "guardrails": [

  ]
}
# Guardrails utils

def guardrails_has_tripwire(results):
    return any(getattr(r, "tripwire_triggered", False) is True for r in (results or []))

def get_guardrail_checked_text(results, fallback_text):
    for r in (results or []):
        info = getattr(r, "info", None) or {}
        if isinstance(info, dict) and ("checked_text" in info):
            return info.get("checked_text") or fallback_text
    return fallback_text

def build_guardrail_fail_output(results):
    failures = []
    for r in (results or []):
        if getattr(r, "tripwire_triggered", False):
            info = getattr(r, "info", None) or {}
            failure = {
                "guardrail_name": info.get("guardrail_name"),
            }
            for key in ("flagged", "confidence", "threshold", "hallucination_type", "hallucinated_statements", "verified_statements"):
                if key in (info or {}):
                    failure[key] = info.get(key)
            failures.append(failure)
    return {"failed": len(failures) > 0, "failures": failures}


class AgentBuildResumeSchema__ExperienceItem(BaseModel):
  company: str
  title: str
  start_date: str
  end_date: str
  location: str
  accomplishments: list[str]
  skills_used: list[str]


class AgentBuildResumeSchema__EducationItem(BaseModel):
  institution: str
  degree: str
  field_of_study: str
  graduation_date: str
  gpa: str
  honors: list[str]


class AgentBuildResumeSchema__ProjectItem(BaseModel):
  name: str
  description: str
  technologies: list[str]
  url: str
  accomplishments: list[str]


class AgentBuildResumeSchema__ContactInfo(BaseModel):
  full_name: str
  email: str
  phone: str
  location: str
  linkedin_url: str
  github_url: str
  portfolio_url: str


class AgentBuildResumeSchema(BaseModel):
  contact_info: AgentBuildResumeSchema__ContactInfo
  professional_summary: str
  target_role: str
  experience: list[AgentBuildResumeSchema__ExperienceItem]
  education: list[AgentBuildResumeSchema__EducationItem]
  skills: list[str]
  projects: list[AgentBuildResumeSchema__ProjectItem]
  certifications: list[str]
  languages: list[str]


class ParseResumeInputSchema(BaseModel):
  resume_text: str
  target_jd: str


agent = Agent(
  name="Agent",
  instructions="",
  model="gpt-5",
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="low"
    )
  )
)


class AgentBuildResumeContext:
  def __init__(self, input_safe_resume_text: str, input_target_jd: str, state_parsed_resume: str, state_target_role: str):
    self.input_safe_resume_text = input_safe_resume_text
    self.input_target_jd = input_target_jd
    self.state_parsed_resume = state_parsed_resume
    self.state_target_role = state_target_role


def agent_build_resume_instructions(run_context: RunContextWrapper[AgentBuildResumeContext], _agent: Agent[AgentBuildResumeContext]):
  input_safe_resume_text = run_context.context.input_safe_resume_text
  input_target_jd = run_context.context.input_target_jd
  state_parsed_resume = run_context.context.state_parsed_resume
  state_target_role = run_context.context.state_target_role
  return f"""You are a professional resume optimization agent designed to tailor resumes for specific job descriptions.

Input:
- Resume text: {{input_safe_resume_text} || {state_parsed_resume}}
- Target job description: {input_target_jd}
- Target role: {state_target_role}

Steps:
1. Extract all relevant information from the provided resume including contact info, experience, education, skills, projects, certifications, and languages.
2. Analyze the target job description to identify key requirements, desired skills, and responsibilities.
3. Optimize the resume by:
   - Rewriting the professional summary to align with the target role
   - Reordering and emphasizing experience that matches job requirements
   - Highlighting accomplishments using action verbs and quantifiable results
   - Ensuring relevant skills from the JD are prominently featured
   - Tailoring project descriptions to showcase relevant technical abilities
4. Maintain truthfulness - do not fabricate experience, skills, or accomplishments.
5. Use ATS-friendly formatting and keywords from the job description.
6. Return JSON only, conforming exactly to the schema below.
"""


agent_build_resume = Agent(
  name="Agent: Build Resume",
  instructions=agent_build_resume_instructions,
  model="gpt-5",
  output_type=AgentBuildResumeSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="high"
    )
  )
)


class ParseResumeContext:
  def __init__(self, workflow_input_resume_text: str, workflow_input_target_jd: str):
    self.workflow_input_resume_text = workflow_input_resume_text
    self.workflow_input_target_jd = workflow_input_target_jd


def parse_resume_instructions(run_context: RunContextWrapper[ParseResumeContext], _agent: Agent[ParseResumeContext]):
  workflow_input_resume_text = run_context.context.workflow_input_resume_text
  workflow_input_target_jd = run_context.context.workflow_input_target_jd
  return f"""You are a deterministic parser for resume documents.

Input:
- Resume text (may be from PDF, DOCX, or plain text): {workflow_input_resume_text}
- Target job description: {workflow_input_target_jd}

Steps:
1. Parse the resume text and extract all sections including:
   - Contact information
   - Professional summary/objective
   - Work experience (company, title, dates, location, accomplishments)
   - Education (institution, degree, dates, GPA if provided)
   - Skills (technical and soft skills)
   - Projects (if any)
   - Certifications (if any)
   - Languages (if any)
2. Clean and normalize the text, removing formatting artifacts.
3. Preserve all original content without embellishment.
4. Extract the target role from the job description.

Output exactly one structured representation of the resume content.
Do not include metadata, formatting, or commentary.
"""


parse_resume = Agent(
  name="Parse Resume",
  instructions=parse_resume_instructions,
  model="gpt-4o-mini",
  output_type=ParseResumeInputSchema,
  model_settings=ModelSettings(
    temperature=0.3,
    top_p=1,
    max_tokens=8000,
    store=True
  )
)


class WorkflowInput(BaseModel):
  resume_text: str
  target_jd: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  state = {
    "user_id": None,
    "parsed_resume": None,
    "target_role": None,
    "optimized_resume": None,
    "created_at": None,
    "version": "v1"
  }
  workflow = workflow_input.model_dump()
  conversation_history: list[TResponseInputItem] = [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": f"Resume:\n{workflow['resume_text']}\n\nTarget Job Description:\n{workflow['target_jd']}"
        }
      ]
    }
  ]
  parse_resume_result_temp = await Runner.run(
    parse_resume,
    input=[
      *conversation_history
    ],
    run_config=RunConfig(trace_metadata={
      "__trace_source__": "agent-builder",
      "workflow_id": "wf_resume_builder_v1"
    }),
    context=ParseResumeContext(workflow_input_resume_text=workflow["resume_text"], workflow_input_target_jd=workflow["target_jd"])
  )

  conversation_history.extend([item.to_input_item() for item in parse_resume_result_temp.new_items])

  parse_resume_result = {
    "output_text": parse_resume_result_temp.final_output.json(),
    "output_parsed": parse_resume_result_temp.final_output.model_dump()
  }

  state["parsed_resume"] = parse_resume_result["output_parsed"]["resume_text"]
  state["target_role"] = parse_resume_result["output_parsed"]["target_jd"]

  guardrails_inputtext = state["parsed_resume"]
  guardrails_result = await run_guardrails(ctx, guardrails_inputtext, "text/plain", instantiate_guardrails(load_config_bundle(guardrails_validate_resume_config)), suppress_tripwire=True)
  guardrails_hastripwire = guardrails_has_tripwire(guardrails_result)
  guardrails_anonymizedtext = get_guardrail_checked_text(guardrails_result, guardrails_inputtext)
  guardrails_output = (guardrails_hastripwire and build_guardrail_fail_output(guardrails_result or [])) or (guardrails_anonymizedtext or guardrails_inputtext)

  if guardrails_hastripwire:
    return guardrails_output
  else:
    agent_build_resume_result_temp = await Runner.run(
      agent_build_resume,
      input=[
        {
          "role": "user",
          "content": [
            {
              "type": "input_text",
              "text": f"""You receive a parsed resume and a target job description.
            Optimize the resume to align with the job requirements while maintaining truthfulness.
            Emphasize relevant experience, skills, and accomplishments.
            Return JSON only.

            Resume:
            {guardrails_output if isinstance(guardrails_output, str) else state["parsed_resume"]}

            Target Job Description:
            {workflow["target_jd"]}

            Target Role:
            {state["target_role"]}"""
            }
          ]
        }
      ],
      run_config=RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": "wf_resume_builder_v1"
      }),
      context=AgentBuildResumeContext(
        input_safe_resume_text=guardrails_output if isinstance(guardrails_output, str) else state["parsed_resume"],
        input_target_jd=workflow["target_jd"],
        state_parsed_resume=state["parsed_resume"],
        state_target_role=state["target_role"]
      )
    )

    conversation_history.extend([item.to_input_item() for item in agent_build_resume_result_temp.new_items])

    agent_build_resume_result = {
      "output_text": agent_build_resume_result_temp.final_output.json(),
      "output_parsed": agent_build_resume_result_temp.final_output.model_dump()
    }

    state["optimized_resume"] = agent_build_resume_result["output_parsed"]

    end_result = {
      "ready_signal": "{{ready}}",
      "final_payload": {
        "user_id": state["user_id"],
        "created_at": state["created_at"],
        "version": state["version"],
        "data": {
          "contact_info": {
            "full_name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin_url": "",
            "github_url": "",
            "portfolio_url": ""
          },
          "professional_summary": "",
          "target_role": state["target_role"],
          "experience": [],
          "education": [],
          "skills": [],
          "projects": [],
          "certifications": [],
          "languages": []
        }
      }
    }
    return end_result
