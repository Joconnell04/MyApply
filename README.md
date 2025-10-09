# 🧠 MyApply

**AI-driven resume and cover letter composer built with FastAPI, TailwindCSS, and OpenAI AgentKit.**  
*Built for learning, experimentation, and simplifying the job application workflow.*

---

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/framework-FastAPI-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20AgentKit-412991.svg" alt="OpenAI AgentKit">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
</p>

---

## 🎯 Purpose

**MyApply** helps users quickly tailor resumes and cover letters for specific job applications using AI reasoning over structured experience data.

Instead of rewriting your resume for every job, you maintain a personal **experience graph** — a JSON model of your work, projects, and skills.  
When you paste a job description, MyApply analyzes it, extracts ATS keywords, and suggests concise, relevant content that best fits that role.

> Think of it as *"Notion for your professional experience"* + *"an Agent that writes your best story for each job."*

---

## 🧩 Key Features

| Feature | Description |
|----------|-------------|
| 🧑‍💻 **Account System** | Secure login using `fastapi-users` with JWT cookies. |
| 🧱 **Experience Graph Editor** | Visual + text-based JSON editor for your professional history. |
| 📄 **JD Composer** | Paste or link a job description; add your vibe prompt. |
| ⚙️ **AgentKit AI Engine** | Generates ranked resume bullet points and a passionate cover letter draft. |
| 🎯 **ATS Keyword Analysis** | Detects must-have terms from job listings and ensures they're reflected in results. |
| 💾 **Runs History** | Automatically stores your previous generations and JD context. |
| 💡 **Lightweight and Local** | Entirely Python-native—no external dependencies beyond OpenAI’s API. |

---

## 🧠 Stack Overview

| Layer | Tool | Role |
|-------|------|------|
| Backend | **FastAPI** | Core API + routing |
| Database | **SQLite + SQLModel** | Store users, experience graphs, and runs |
| Auth | **fastapi-users** | Handles registration, login, and sessions |
| Frontend | **Jinja2 + HTMX + TailwindCSS (DaisyUI)** | Clean UI with minimal JS |
| AI Layer | **OpenAI Python SDK + AgentKit** | LLM-based extraction, ranking, and generation |
| JSON Editing | **JSONEditor (embedded)** | Experience graph manipulation |

---

## 🏗️ Architecture

```

```
    ┌───────────────────────────────┐
    │          Frontend             │
    │  Jinja2 + HTMX + TailwindCSS  │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │          FastAPI              │
    │  Routes: /auth /graph /compose│
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │         SQLModel ORM          │
    │   SQLite DB (User, Graph, Run)│
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌───────────────────────────────┐
    │      AgentKit / OpenAI API    │
    │  - JD Factor Extraction       │
    │  - Fact Ranking               │
    │  - Resume + Letter Generation │
    └───────────────────────────────┘
```

````

---

## 🧰 Quick Start

### 1️⃣ Clone and Install
```bash
git clone https://github.com/<your-username>/MyApply.git
cd MyApply
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
````

### 2️⃣ Environment Variables

Create a `.env` file in the root directory:

```bash
OPENAI_API_KEY=sk-your-key
AGENTKIT_API_URL=https://api.openai.com/v1/agentkit
SECRET_KEY="your_secret_key"
DATABASE_URL="sqlite:///./myapply.db"
```

### 3️⃣ Run Database Setup

```bash
python -m app.init_db
```

### 4️⃣ Start the Server

```bash
uvicorn app:app --reload
```

Visit **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

---

## 🖥️ Core Pages

| Page             | Purpose                                      |
| ---------------- | -------------------------------------------- |
| `/auth/register` | Create an account                            |
| `/graph`         | View and edit your experience graph          |
| `/compose`       | Paste a job description and generate content |
| `/runs`          | View history of past generations             |

---

## 🧩 Experience Graph Example

```json
{
  "meta": {
    "schema_version": "1.0",
    "person_id": "person:boss",
    "last_updated": "2025-10-09"
  },
  "nodes": [
    {"id": "org:delta", "t": "Org", "n": "Delta Air Lines"},
    {"id": "role:coop", "t": "Role", "n": "Operations Support Co-op", "org": "org:delta"}
  ],
  "facts": [
    {
      "id": "ach:automation",
      "t": "Achievement",
      "role": "role:coop",
      "action": "Automated pilot work reporting",
      "result": {"metric": "time", "delta": -0.6},
      "tags": ["Smartsheet", "Automation"]
    }
  ]
}
```

---

## ⚙️ Development Workflow

1. **Edit Graph**

   * Manage your data in `/graph`
   * Validate JSON schema in-browser
2. **Compose Content**

   * Paste JD or URL, add optional vibe prompt
   * Choose Resume / Cover Letter generation
3. **LLM Pipeline**

   * AgentKit extracts company, role, level, keywords
   * Ranks your experiences from graph
   * Returns plain-text content (no formatting)
4. **Review + Copy**

   * Outputs are fully editable before export

---

## 📦 Folder Structure

```
myapply/
├── app.py              # FastAPI app entry
├── auth.py             # User management
├── models.py           # SQLModel tables
├── llm.py              # OpenAI / AgentKit integration
├── templates/          # Jinja2 HTML templates
│   ├── base.html
│   ├── graph.html
│   ├── compose.html
│   └── login.html
├── static/
│   ├── css/
│   └── js/
└── README.md
```

---

## 🧑‍💻 For Developers

### Tech Highlights

* Pure Python stack — no React or heavy JS required
* Hot reload with `uvicorn --reload`
* SQLite + SQLModel = zero setup
* Works offline except for LLM API calls

### Future Enhancements

* PDF export using WeasyPrint
* Multi-user dashboard
* Model-driven ATS scoring
* Optional vector memory for career data search

---

## 🌐 Deployment

Deploy easily with [Render](https://render.com/), [Railway](https://railway.app/), or [Fly.io](https://fly.io/).

Example Fly.io setup:

```bash
fly launch
fly deploy
```

---

## 📸 UI Preview (Concept)

```
╭─────────────────────────────────────────────╮
│ MyApply                                     │
│---------------------------------------------│
│ Paste Job Description  [ Text Area ]        │
│ Vibe / Story Prompt   [ Optional Text ]     │
│ [✔] Tailored Resume   [✔] Tailored Cover    │
│                                             │
│ [Generate]                                  │
│---------------------------------------------│
│ 🔹 Resume Bullets                           │
│  - Automated pilot work reporting...        │
│  - Built Smartsheet archival system...      │
│                                             │
│ 🔹 Cover Letter                             │
│  Dear Hiring Team,                          │
│  I’m passionate about leveraging analytics… │
│                                             │
╰─────────────────────────────────────────────╯
```

---

## 💡 Why Build This

To explore:

* LLMs as intelligent assistants for structured data
* AI-assisted storytelling in career materials
* Integrating OpenAI AgentKit into a real product workflow

MyApply serves as both a **learning sandbox** and a **personal automation tool** for anyone refining their professional narrative.

---

## 🧾 License

Released under the **MIT License**.
Feel free to fork, study, or modify for personal and educational use.

---

<p align="center">
  <b>Built with ❤️ in Python for learners, builders, and job seekers.</b><br>
  <i>FastAPI • Tailwind • AgentKit • OpenAI</i>
</p>