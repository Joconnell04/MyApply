# MyApply
<h1 align="center">🧠 MyApply</h1>
<p align="center">
  <b>AI-driven resume and cover letter composer built with FastAPI, TailwindCSS, and OpenAI AgentKit.</b><br>
  <i>Built for learning, experimentation, and simplifying the job application workflow.</i>
</p>

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

> Think of it as *"Notion for your professional experience" + "Agent that writes your best story for each job."*

---

## 🧩 Key Features

| Feature | Description |
|----------|--------------|
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

