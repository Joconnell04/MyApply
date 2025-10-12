
# # End Node Schema:

{
  "type": "object",
  "properties": {
    "job_id": { "type": ["string", "null"] },
    "title": { "type": ["string", "null"] },
    "company": { "type": ["string", "null"] },
    "location": { "type": ["string", "null"] },
    "seniority": { "type": "string" },
    "req_skills": { "type": "array", "items": { "type": "string" } },
    "nice_to_haves": { "type": "array", "items": { "type": "string" } },
    "responsibilities": { "type": "array", "items": { "type": "string" } },
    "keywords": { "type": "array", "items": { "type": "string" } },
    "ats_terms": { "type": "array", "items": { "type": "string" } },
    "salary_range": {
      "type": "object",
      "properties": {
        "min": { "type": ["number", "null"] },
        "max": { "type": ["number", "null"] },
        "currency": { "type": ["string", "null"] }
      },
      "required": ["min", "max", "currency"]
    },
    "_meta": {
      "type": "object",
      "properties": {
        "source": { "type": "string" },
        "user_id": { "type": "string" },
        "workflow": { "type": "string" },
        "version": { "type": "string" }
      },
      "required": ["source", "user_id", "workflow", "version"]
    }
  },
  "required": [
    "title",
    "company",
    "req_skills",
    "responsibilities",
    "_meta"
  ],
  "additionalProperties": false
}
