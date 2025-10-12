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
guardrails_validate_jd_config = {
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
class AgentStructureJdSchema__LocationsItem(BaseModel):
  city: str
  region: str
  country: str
  raw: str
  type: str
  confidence: float


class AgentStructureJdSchema__LocationResolution(BaseModel):
  source: str
  notes: str


class AgentStructureJdSchema__Skills(BaseModel):
  must_have: list[str]
  nice_to_have: list[str]


class AgentStructureJdSchema__Compensation(BaseModel):
  salary_min: float
  salary_max: float
  currency: str
  pay_period: str
  benefits: list[str]


class AgentStructureJdSchema(BaseModel):
  title: str
  company_name: str
  employment_type: str
  seniority: str
  locations: list[AgentStructureJdSchema__LocationsItem]
  location_resolution: AgentStructureJdSchema__LocationResolution
  responsibilities: list[str]
  requirements: list[str]
  qualifications: list[str]
  skills: AgentStructureJdSchema__Skills
  compensation: AgentStructureJdSchema__Compensation
  remote_policy: str
  source_url: str
  page_title: str


class FetchParseJdSchema(BaseModel):
  normalized_jd: str
  source_url: str
  page_title: str
  company_name: str


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


class AgentStructureJdContext:
  def __init__(self, input_safe_text: str, state_normalized_jd: str, state_company_name: str, state_source_url: str, state_page_title: str):
    self.input_safe_text = input_safe_text
    self.state_normalized_jd = state_normalized_jd
    self.state_company_name = state_company_name
    self.state_source_url = state_source_url
    self.state_page_title = state_page_title
def agent_structure_jd_instructions(run_context: RunContextWrapper[AgentStructureJdContext], _agent: Agent[AgentStructureJdContext]):
  input_safe_text = run_context.context.input_safe_text
  state_normalized_jd = run_context.context.state_normalized_jd
  state_company_name = run_context.context.state_company_name
  state_source_url = run_context.context.state_source_url
  state_page_title = run_context.context.state_page_title
  return f"""You are a deterministic extractor for structured job data.
Input:
- Plain-text job description: {{input_safe_text} ||  {state_normalized_jd}}
- Context: company_name={state_company_name}, source_url={state_source_url}, page_title={state_page_title}

Steps:
1. Extract all explicit locations (city, region, country) and “Remote/Hybrid” cues.
2. If no explicit locations, infer or default to the company HQ location (use the company’s well-known headquarters based on your model knowledge).
3. Return both the list of found or defaulted locations and a `location_resolution` object showing the source (`jd` or `company_hq`).
4. Do not invent responsibilities, requirements, or pay info not mentioned.
5. Return JSON only, conforming exactly to the schema below.
"""
agent_structure_jd = Agent(
  name="Agent: Structure JD",
  instructions=agent_structure_jd_instructions,
  model="gpt-5",
  output_type=AgentStructureJdSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


class FetchParseJdContext:
  def __init__(self, workflow_input_as_text: str, state_jd_string: str):
    self.workflow_input_as_text = workflow_input_as_text
    self.state_jd_string = state_jd_string
def fetch_parse_jd_instructions(run_context: RunContextWrapper[FetchParseJdContext], _agent: Agent[FetchParseJdContext]):
  workflow_input_as_text = run_context.context.workflow_input_as_text
  state_jd_string = run_context.context.state_jd_string
  return f"""You are a deterministic extractor for job postings.

Input:
A single URL of a job description will be either in {workflow_input_as_text} or {state_jd_string} 
Steps:
1. Fetch the page content using the Web Search tool.
2. Convert the HTML to readable text (apply html_to_text_cleaner if available).
3. Keep only the job description portion:
   - role title
   - company
   - locations (can be multiple if multiple are listed; use comapny HQ location if no location is explicitly mentioned)
   - responsibilities
   - requirements
   - qualifications
   - salary or benefits if shown
4. Remove headers, navigation bars, application forms, cookie banners, and unrelated sections.

Output exactly one plain-text block of job description content under 12 000 characters.
Do not include metadata, HTML, or commentary.
"""
fetch_parse_jd = Agent(
  name="Fetch+Parse JD",
  instructions=fetch_parse_jd_instructions,
  model="gpt-4o-mini",
  tools=[
    web_search_preview
  ],
  output_type=FetchParseJdSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=10000,
    store=True
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  state = {
    "user_id": None,
    "source_url": None,
    "page_title": None,
    "company_name": None,
    "jd_locations": [

    ],
    "normalized_jd": None,
    "ingested_at": None,
    "hash": None
  }
  workflow = workflow_input.model_dump()
  conversation_history: list[TResponseInputItem] = [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": workflow["input_as_text"]
        }
      ]
    }
  ]
  fetch_parse_jd_result_temp = await Runner.run(
    fetch_parse_jd,
    input=[
      *conversation_history
    ],
    run_config=RunConfig(trace_metadata={
      "__trace_source__": "agent-builder",
      "workflow_id": "wf_68e80e14fad48190a83d85460325ba7f072fbeb74efb9546"
    }),
    context=FetchParseJdContext(workflow_input_as_text=workflow["input_as_text"], state_jd_string=state["jd_string"])
  )

  conversation_history.extend([item.to_input_item() for item in fetch_parse_jd_result_temp.new_items])

  fetch_parse_jd_result = {
    "output_text": fetch_parse_jd_result_temp.final_output.json(),
    "output_parsed": fetch_parse_jd_result_temp.final_output.model_dump()
  }
  transform_result = {}
  state["source_url"] = transform_result["result"]
  state["normalized_jd"] = transform_result["result"]
  state["user_id"] = state["user_id"]
  state["hash"] = state["hash"]
  state["ingested_at"] = state["ingested_at"]
  state["page_title"] = state["page_title"]
  state["company_name"] = state["company_name"]
  guardrails_inputtext = state["normalized_jd"]
  guardrails_result = await run_guardrails(ctx, guardrails_inputtext, "text/plain", instantiate_guardrails(load_config_bundle(guardrails_validate_jd_config)), suppress_tripwire=True)
  guardrails_hastripwire = guardrails_has_tripwire(guardrails_result)
  guardrails_anonymizedtext = get_guardrail_checked_text(guardrails_result, guardrails_inputtext)
  guardrails_output = (guardrails_hastripwire and build_guardrail_fail_output(guardrails_result or [])) or (guardrails_anonymizedtext or guardrails_inputtext)
  if guardrails_hastripwire:
    return guardrails_output
  else:
    agent_structure_jd_result_temp = await Runner.run(
      agent_structure_jd,
      input=[
        {
          "role": "user",
          "content": [
            {
              "type": "input_text",
              "text": f"""You receive a cleaned job description and limited context.
            Extract the fields described in the JSON schema.
            If the text lists no location, infer or default to the company’s headquarters based on the company name.
            Mark location_resolution.source as \"company_hq\" in that case.
            If multiple locations are listed, include all of them.
            Return JSON only.
            Input text:
            {{guardrails_output["safe_text"]} ||  {state["normalized_jd"]}}
            Context:
            company_name: {state["company_name"]}
            source_url: {state["source_url"]}
            page_title: {state["page_title"]}"""
            }
          ]
        }
      ],
      run_config=RunConfig(trace_metadata={
        "__trace_source__": "agent-builder",
        "workflow_id": "wf_68e80e14fad48190a83d85460325ba7f072fbeb74efb9546"
      }),
      context=AgentStructureJdContext(input_safe_text=guardrails_output["safe_text"], state_normalized_jd=state["normalized_jd"], state_company_name=state["company_name"], state_source_url=state["source_url"], state_page_title=state["page_title"])
    )

    conversation_history.extend([item.to_input_item() for item in agent_structure_jd_result_temp.new_items])

    agent_structure_jd_result = {
      "output_text": agent_structure_jd_result_temp.final_output.json(),
      "output_parsed": agent_structure_jd_result_temp.final_output.model_dump()
    }
    transform_result1 = {
      "ready_signal": "{{ready}}",
      "final_payload": {
        "user_id": "",
        "ingested_at": "",
        "hash": "",
        "data": {
          "title": "",
          "company_name": "",
          "employment_type": "",
          "seniority": "",
          "locations": [

          ],
          "location_resolution": {
            "source": "unknown",
            "notes": ""
          },
          "responsibilities": [

          ],
          "requirements": [

          ],
          "qualifications": [

          ],
          "skills": {
            "must_have": [

            ],
            "nice_to_have": [

            ]
          },
          "compensation": {
            "salary_min": None,
            "salary_max": None,
            "currency": "",
            "pay_period": "",
            "benefits": [

            ]
          },
          "remote_policy": "",
          "source_url": "",
          "page_title": ""
        }
      }
    }
    end_result = {
      "ready_signal": "{{ready}}",
      "final_payload": {
        "user_id": "",
        "ingested_at": "",
        "hash": "",
        "data": {
          "title": "",
          "company_name": "",
          "employment_type": "",
          "seniority": "",
          "locations": [

          ],
          "location_resolution": {
            "source": "unknown",
            "notes": ""
          },
          "responsibilities": [

          ],
          "requirements": [

          ],
          "qualifications": [

          ],
          "skills": {
            "must_have": [

            ],
            "nice_to_have": [

            ]
          },
          "compensation": {
            "salary_min": 0,
            "salary_max": 0,
            "currency": "",
            "pay_period": "",
            "benefits": [

            ]
          },
          "remote_policy": "",
          "source_url": "",
          "page_title": ""
        }
      }
    }
    return end_result

