# Multi‑Agent Interview Coach

This repository contains a proof‑of‑concept implementation of a **multi‑agent technical interview system** compliant with an extended agentic workflow specification.  
The system simulates a realistic technical interview with two cooperating AI agents – an interviewer and an observer.  
It relies on a Large Language Model (LLM) not only to analyse answers and produce feedback but also to **generate new interview questions on the fly**. The observer provides context to the LLM (topics, difficulty, previous performance) and parses the returned JSON describing the question and its expected answer. The LLM is mandatory.

## Architecture

The design follows the principles of agentic workflows: there are at least two specialised agents that cooperate to run the interview.  
Each agent maintains its own role and interacts with the conversation history through a shared context.  

* **InterviewerAgent** – responsible for conducting the dialogue.  It asks questions, responds to off‑topic queries and adjusts the wording of its questions based on guidance from the observer.  It does **not** assess the correctness of answers.
* **ObserverAgent** – evaluates candidate responses behind the scenes.  It classifies each answer as `correct`, `incorrect`, `off_topic` or `hallucination`, keeps track of the candidate’s performance and recommends the next question and its difficulty.  It also records internal remarks for hidden reflection.
* **InterviewSession** – orchestrates the interaction between the agents and the human candidate.  It maintains conversation history, adapts difficulty based on performance and writes detailed logs.  When the candidate ends the interview, it asks the LLM to generate a structured final feedback report.

The session stores the latest turns of conversation in memory and supplies them to the agents to preserve context and avoid repeating questions. The observer adapts question difficulty based on the candidate’s recent performance.

## Installation

The code targets Python 3.8+ and depends on the following third‑party packages:

* `mistralai` – official Python SDK for Mistral. It provides a client to call Mistral chat models and is used to generate questions, grade answers, handle role-reversal, and generate the final report.
* `python-dotenv` (optional) – for managing environment variables in a `.env` file.

These packages are **not** included in this archive because the competition environment cannot install external dependencies.  Before running the script on your machine you will need to install them:

```bash
pip install mistralai python-dotenv
```

## Usage

1. **Set your API credentials**:  
   Create a `.env` file in the project root containing your API key and the model name for Mistral.  The main script looks for `MISTRAL_API_KEY` and optionally `MISTRAL_MODEL` (if you want to override the default model).  For example:

   ```env
   MISTRAL_API_KEY=sk-...your-mistral-key...
   MISTRAL_MODEL=mistral-medium-latest
   ```

   Alternatively you can export these variables in your shell.  If you omit `MISTRAL_MODEL`, it defaults to `mistral-medium-latest`.  Consult the Mistral documentation for available model names.


2. **Run an interactive interview**:

   Run the module using Python’s ``-m`` flag so that relative imports resolve correctly.  For example:

   ```bash
   python -m multi_agent_interview_coach.main
   ```

   The script will ask you for the candidate’s name, target position, grade and experience, then start the interview.  The observer agent instructs the LLM to **generate a question** appropriate to the topic and difficulty.  The interviewer poses the question and handles off‑topic, hallucinated or role‑reversal replies.  Type your answers to the interviewer’s questions.  To stop the interview and request feedback, type `Стоп интервью` (or `Stop interview`) as your response.

3. **Review the log**:

   After the interview ends, a structured log is written to `interview_log.json`.  This file contains each turn’s visible message, the candidate’s response and the hidden internal thoughts exchanged between the agents.  The final feedback report is included at the end.

## Dynamic question generation (no hard-coded questions)

Вопросы **не хранятся в коде** и **не берутся из статического списка**. На каждом ходу Observer формирует контекст и просит LLM сгенерировать *новый* вопрос в JSON формате (`topic`, `difficulty`, `question`, `answer`) с учётом позиции, грейда, опыта, последних 3+ ответов и уже заданных вопросов (чтобы не повторяться).

## Limitations

This prototype is intended for demonstration purposes and does not represent a production‑ready interviewer.  In particular:

* The quality of generated questions depends on the LLM and the prompts used. The LLM is mandatory; if the API key is missing, the program will stop with a clear error.
* Off‑topic, hallucination and role‑reversal detection is based on simple heuristics and may miss subtle cases.  A production system should integrate fact‑checking and question‑intent analysis.

Nevertheless, the system satisfies the core requirements of **role specialisation**, **hidden reflection**, **context awareness**, **adaptability** and **robustness**.  These features showcase how multi‑agent coordination and dynamic question generation can enhance LLM‑driven interviews.