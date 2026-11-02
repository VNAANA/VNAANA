# Ask Nova Thursday demo quick start

This separate testing branch is for Thursday's demo and team review; do not merge it into `dev` yet.

## Clone

```powershell
git clone --single-branch --branch demo/ask-nova-thursday `
  https://github.com/RikH2023/VNAANA.git D:\VNAANA-Thursday-Demo
Set-Location D:\VNAANA-Thursday-Demo
```

## Prerequisites and configuration

- Python 3.12, Node.js 22+, and Ollama for Windows.
- Get Hanh's latest configuration files from Discord.
- Put the backend configuration in `Backend/.env` and the frontend configuration in `Frontend/.env.local`.
- Frontend and backend variable names may differ, so keep each setting in its intended file.
- Ensure `Frontend/.env.local` contains `VITE_API_BASE_URL=http://localhost:8000`.
- Never commit, share, or paste actual credentials into logs or screenshots.

## Install dependencies and model

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
Set-Location .\Frontend
npm ci
Set-Location ..
ollama pull llama3.2
```

## Start the demo in separate PowerShell terminals

```powershell
# Terminal 1 — only if Ollama is not already running
ollama serve
# Terminal 2 — from the repository root
.\.venv\Scripts\python.exe -m uvicorn Backend.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 3
Set-Location D:\VNAANA-Thursday-Demo\Frontend
npm run dev
```

Open <http://localhost:5173>. Confirm the feed loads, Ask Nova answers a supported question, English and Dutch can be selected, and a preview-only article shows its limited-context notice. The Azure backend is not compatible with this local-Ollama demo; responses may be slow on weaker laptops, and no database migrations should be run independently.
