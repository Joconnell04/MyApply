# MyLife Experience Graph Schema

## Overview

The MyLife schema is a structured graph representation of professional experience, designed for AI-driven resume and cover letter generation. It captures people, organizations, roles, projects, tasks, skills, tools, datasets, outcomes, metrics, and evidence in a connected format optimized for ranking and content generation.

## Core Principles

1. **Graph-first**: All entities are nodes; relationships are edges
2. **Versioned**: Every object has a version number for conflict resolution
3. **Provenance**: Track how each fact was created (manual, LLM, import)
4. **Privacy-aware**: Mark sensitive data appropriately
5. **Metric-driven**: Quantify outcomes wherever possible

## Node Types

### Person
Represents an individual (typically the graph owner).

**Data:**
- `full_name`: string (required)
- `emails`: list of strings
- `phones`: list of strings
- `location`: string (optional)
- `links`: list of URLs
- `profiles`: dict of platform -> URL (e.g., {"LinkedIn": "...", "GitHub": "..."})

### Organization
A company, institution, or entity.

**Data:**
- `name`: string (required)
- `sector`: string (e.g., "Technology", "Healthcare")
- `size`: enum (`1-10`, `11-50`, `51-200`, `201-1000`, `1001-5000`, `5001+`)
- `locations`: list of strings

### Role
A position held at an organization.

**Data:**
- `title`: string (required)
- `employment_type`: enum (`Full-time`, `Part-time`, `Intern`, `Co-op`, `Contract`, `Volunteer`)
- `start_date`: ISO date (required)
- `end_date`: ISO date (optional, null means current)
- `location_mode`: enum (`Onsite`, `Hybrid`, `Remote`)
- `job_functions`: list of enums (`Analytics`, `Automation`, `Software`, `PM`, `Ops`)

### Project
A scoped initiative or body of work.

**Data:**
- `name`: string (required)
- `summary`: string (required)
- `start_date`: ISO date (required)
- `end_date`: ISO date (optional)
- `status`: enum (`Planned`, `In-Progress`, `Completed`, `On-Hold`)
- `domain`: list of enums (`Flight Ops`, `Airline Analytics`, `Fintech`, `Data Platform`, `Research`, `ETL`, `Automation`, `Web`, `UI/UX`, `Governance`)

### Task
A concrete unit of work within a project.

**Data:**
- `name`: string (required)
- `description`: string (required)
- `start_date`: ISO date (optional)
- `end_date`: ISO date (optional)
- `effort_hours`: float (default 0.0)
- `outcome`: string (optional summary)

### Skill
A technical or domain competency.

**Data:**
- `name`: string (required, e.g., "Python", "SQL", "Machine Learning")
- `category`: enum (`Programming`, `Data`, `ML`, `Cloud`, `PM`, `Design`, `Domain`, `Hardware`)
- `level`: enum (`Novice`, `Intermediate`, `Advanced`, `Expert`)
- `evidence_metric_ids`: list of UUIDs pointing to evidence/metrics

### Tool
A software tool, platform, or service.

**Data:**
- `name`: string (required, e.g., "Tableau", "Docker", "Jira")
- `vendor`: string (optional)
- `category`: enum (`BI`, `ETL`, `DB`, `IDE`, `Automation`, `Cloud`, `VersionControl`, `Other`)

### Dataset
A data source used in a project or task.

**Data:**
- `name`: string (required)
- `schema_desc`: string (description of structure)
- `record_count`: integer (default 0)
- `sensitivity`: enum (`Low`, `Moderate`, `High`)
- `retention_policy`: string (optional)
- `time_range`: object with `start` (ISO date) and optional `end`

### Outcome
A result or deliverable produced by work.

**Data:**
- `title`: string (required)
- `description`: string (required)
- `category`: enum (`Cost`, `Speed`, `Quality`, `Reliability`, `Revenue`, `Adoption`)
- `metric_impacts`: list of UUIDs (metrics that quantify this outcome)
- `artifacts`: list of strings (URLs or references)

### Metric
A quantifiable measurement of impact.

**Data:**
- `name`: string (required, e.g., "Query latency", "Cost savings")
- `unit`: enum (`hours`, `$`, `%`, `count`)
- `baseline_value`: float (starting value)
- `baseline_date`: ISO date (optional)
- `final_value`: float (ending value)
- `final_date`: ISO date (optional)
- `direction`: enum (`HigherIsBetter`, `LowerIsBetter`, `Target`)
- `calculation_notes`: string (optional methodology)

### Evidence
Documentation or proof of work.

**Data:**
- `kind`: enum (`Doc`, `PR`, `Screenshot`, `Email`, `Ticket`, `Presentation`, `Dataset`, `Paper`)
- `title`: string (required)
- `uri`: string (required, URL or reference)
- `access`: enum (`public`, `restricted`, `private`)

### Credential
Certification, license, or formal recognition.

**Data:**
- `name`: string (required)
- `issuer`: string (required)
- `issue_date`: ISO date (required)
- `expire_date`: ISO date (optional)
- `credential_id`: string (optional)
- `link`: string (optional URL)

### Publication
Published work (blog, paper, talk).

**Data:**
- `title`: string (required)
- `venue`: enum (`Blog`, `Journal`, `Conference`, `Internal`)
- `date`: ISO date (required)
- `url`: string (optional)

### Event
A notable occurrence (interview, release, demo).

**Data:**
- `name`: string (required)
- `date`: ISO date (required)
- `kind`: enum (`Interview`, `Release`, `Demo`, `Talk`, `Meeting`)
- `notes`: string (optional)

### Decision
A significant choice made during work.

**Data:**
- `statement`: string (required, the decision)
- `date`: ISO date (required)
- `options_considered`: list of strings
- `rationale`: string (required)

### Issue
A problem or blocker encountered.

**Data:**
- `title`: string (required)
- `severity`: enum (`Low`, `Medium`, `High`, `Critical`)
- `opened`: ISO date (required)
- `closed`: ISO date (optional)
- `summary`: string (required)

### SourceText
Raw text ingested for later extraction.

**Data:**
- `text`: string (required)
- `lang`: string (default "en")
- `source_ref`: string (optional reference)

## Edge Types

### HAS_MEMBER
Organization -> Person (membership relationship)

### HELD_ROLE_AT
Person -> Role (person held a role)

### ROLE_AT_ORG
Role -> Organization (role is at an organization)

### WORKED_ON
Person or Role -> Project (contributed to project)

### CONTAINS_TASK
Project -> Task (task is part of project)

### USED_TOOL
Project or Task -> Tool (used a tool)

### USED_DATASET
Project or Task -> Dataset (used a dataset)

### APPLIED_SKILL
Task -> Skill (skill was applied in task)

### PRODUCED_OUTCOME
Project or Task -> Outcome (produced an outcome)

### MEASURED_BY
Outcome -> Metric (outcome quantified by metric)

### SUPPORTED_BY
Outcome or Metric -> Evidence (backed by evidence)

### EARNED
Person -> Credential (person earned credential)

### PUBLISHED
Person -> Publication (person published work)

### ATTENDED
Person -> Event (person attended event)

### MADE_DECISION
Project or Task -> Decision (decision made during work)

### RAISED_ISSUE
Project or Task -> Issue (issue encountered)

### RESOLVED_BY
Issue -> Task (issue resolved by task)

### TRACE_TO_TEXT
Any node -> SourceText (node extracted from source text)

## Common Fields (All Nodes and Edges)

- `id`: UUID4 (required, unique identifier)
- `type`: literal "node" or "edge"
- `version`: positive integer (default 1, for optimistic locking)
- `created_at`: ISO datetime with timezone (auto-generated)
- `updated_at`: ISO datetime with timezone (auto-generated)
- `confidence`: float 0.0-1.0 (default 0.8, for LLM-extracted facts)
- `privacy`: enum (`private`, `internal`, `public`) - default varies by type
- `labels`: list of strings (tags for filtering/search)
- `provenance`: object with:
  - `ingested_from`: enum (`LLM`, `manual`, `import`, `catalog`)
  - `source_doc_id`: string (optional)
  - `source_span`: string (e.g., "line 10-15" or "N/A")
  - `curator`: string (username or "system")

## Edge-Specific Fields

- `from_id`: UUID4 (source node)
- `to_id`: UUID4 (target node)
- `since`: ISO date (optional, when relationship started)
- `until`: ISO date (optional, when relationship ended)

## Serialization Format

### JSONL (Newline-Delimited JSON)

Each line is a complete JSON object representing a single node or edge.

**Example:**
```jsonl
{"type":"node","node_type":"Organization","id":"11111111-1111-1111-1111-111111111111","version":1,"created_at":"2025-10-09T14:00:00Z","updated_at":"2025-10-09T14:00:00Z","confidence":1.0,"privacy":"internal","labels":["Airline"],"provenance":{"ingested_from":"manual","source_doc_id":null,"source_span":"N/A","curator":"user"},"data":{"name":"Delta Air Lines","sector":"Airline","size":"5001+","locations":["Atlanta, GA, USA"]}}
{"type":"node","node_type":"Role","id":"22222222-2222-2222-2222-222222222222","version":1,"created_at":"2025-10-09T14:00:00Z","updated_at":"2025-10-09T14:00:00Z","confidence":0.95,"privacy":"internal","labels":["Flight Ops"],"provenance":{"ingested_from":"LLM","source_doc_id":"src-ppw","source_span":"0:500","curator":"user"},"data":{"title":"Operations Support Technology & Business Strategy Co-op","employment_type":"Co-op","start_date":"2024-01-08","end_date":"2025-08-15","location_mode":"Onsite","job_functions":["Analytics","Automation","Ops"]}}
{"type":"edge","edge_type":"ROLE_AT_ORG","id":"44444444-4444-4444-4444-444444444444","from_id":"22222222-2222-2222-2222-222222222222","to_id":"11111111-1111-1111-1111-111111111111","since":"2024-01-08","until":"2025-08-15","version":1,"created_at":"2025-10-09T14:00:00Z","updated_at":"2025-10-09T14:00:00Z","confidence":0.95,"privacy":"internal","labels":[],"provenance":{"ingested_from":"LLM","source_doc_id":"src-ppw","source_span":"0:100","curator":"user"}}
```

### Structured JSON

Can also be represented as an object with `nodes` and `edges` arrays:

```json
{
  "nodes": [
    {
      "type": "node",
      "node_type": "Organization",
      "id": "11111111-1111-1111-1111-111111111111",
      ...
    }
  ],
  "edges": [
    {
      "type": "edge",
      "edge_type": "ROLE_AT_ORG",
      ...
    }
  ]
}
```

## Usage in MyApply

1. **Graph Editor** (`/graph`): Users build and edit their graph via JSONEditor
2. **Validation** (`/api/graph/validate`): Dry-run validation before save
3. **Persistence** (`/api/graph/save`): Save to database with user ownership
4. **Ranking** (`rank_facts`): Score task nodes against job description factors
5. **Generation** (LLM pipeline): Use top-ranked facts to create resume bullets and cover letters

## Best Practices

- Use specific, quantified task descriptions (avoid vague language)
- Connect tasks to skills, tools, and outcomes
- Always include metrics for outcomes when possible
- Use recency appropriately (recent work is weighted higher)
- Tag with relevant ATS keywords in labels
- Maintain accurate date ranges for proper timeline reconstruction
- Use `confidence` < 1.0 for LLM-extracted or uncertain facts
