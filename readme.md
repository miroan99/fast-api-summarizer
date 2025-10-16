# Fast API summarizer


# 🧠 FastAPI Summarizer

A secure, rate-limited REST API that summarizes text using OpenAI (or a local LLM via LM Studio).  
Built with **FastAPI**, **Uvicorn**, and the **OpenAI SDK v1**.

---

## 🚀 Features

- `/summarize` — Summarizes text in English or Danish  
- `/health` — Simple health-check endpoint  
- ✅ API-key authentication (`X-API-Key`)  
- 🔒 CORS allow-list (configurable in `.env`)  
- ⏱️ Rate limiting (per IP via SlowAPI)  
- 🧩 Easy model switching: OpenAI or LM Studio  
- 📜 Secure `.env` configuration  
- 🧹 Code formatted with `black`, type-checked with `mypy`

---

## 🧰 Tech Stack

| Layer | Tool |
|-------|------|
| Framework | [FastAPI](https://fastapi.tiangolo.com) |
| Server | [Uvicorn](https://www.uvicorn.org) |
| AI SDK | [OpenAI Python SDK v1](https://github.com/openai/openai-python) |
| Rate Limiting | [SlowAPI](https://github.com/laurentS/slowapi) |
| Config | python-dotenv |
| Language | Python 3.12 (on Windows) |

---

## ⚙️ Installation

### 1️⃣ Clone & set up
```powershell
git clone https://github.com/<your-username>/fast-api-summarizer.git
cd fast-api-summarizer
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt


===========================================
 FASTAPI SUMMARIZER — RUN INSTRUCTIONS
===========================================

1)  Open PowerShell in your project folder:
    C:\Users\micha\PythonProjects\fast-api-summarizer

2)  Create and activate a virtual environment:
        py -m venv .venv
        .venv\Scripts\Activate.ps1

3)  Install required packages:
        pip install -r requirements.txt

4)  Configure environment variables:
    Copy the example file and edit it:
        copy .env.example .env
    Then open ".env" and set:
        OPENAI_API_KEY=sk-your-openai-key
        OPENAI_MODEL=gpt-4o-mini
        API_KEY=dev-local-please-change-me

    (If using LM Studio locally:)
        OPENAI_BASE_URL=http://127.0.0.1:1234/v1
        OPENAI_API_KEY=lm-studio
        OPENAI_MODEL=your-local-model-name

5)  Start the API server (in PowerShell):
        uvicorn main:app --reload

    Wait until you see:
        INFO:     Uvicorn running on http://127.0.0.1:8000
        INFO:     Application startup complete.

6)  Open a new PowerShell window and test the API:

    Health check:
        curl.exe -H "X-API-Key: dev-local-please-change-me" http://127.0.0.1:8000/health

    Summarizer test:
        curl.exe -X POST http://127.0.0.1:8000/summarize ^
         -H "Content-Type: application/json" ^
         -H "X-API-Key: dev-local-please-change-me" ^
         -d "{ \"text\": \"FastAPI makes it easy to build APIs.\", \"language\": \"en\", \"max_words\": 20 }"

7)  Expected result:
        {"summary": "FastAPI is a fast Python web framework for APIs.", "words": 11, "model": "gpt-4o-mini"}

8)  Stop the server:
        Press CTRL + C in the window where the server is running.


-------------------------------------------
 RUNNING FASTAPI INSIDE PYCHARM (OPTIONAL)
-------------------------------------------

1) Open your project in PyCharm.

2) Go to:
       Run → Edit Configurations → + → Python

3) Set:
       Script path:  C:\Users\micha\PythonProjects\fast-api-summarizer\.venv\Scripts\uvicorn.exe
       Parameters:   main:app --reload
       Working dir:  C:\Users\micha\PythonProjects\fast-api-summarizer
       Python:       Select your project interpreter (.venv)

4) Click "OK" and then press the green ▶ Run button.

   PyCharm will start the Uvicorn server in its console window.

5) You can now access your API at:
       http://127.0.0.1:8000/docs

6) Stop the server in PyCharm by pressing the red ■ Stop button.

===========================================
