# PodcastGenerator Monorepo

Pipelines:
- Step 1: fetch & select full-text RCT (outputs card)
- Step 2: critical appraisal (CONSORT) from card

## Quickstart (Windows)
```powershell
.\scripts\setup_venv.ps1
Copy-Item .env.example .env
# fill in keys
.\scripts\run_step1.ps1
.\scripts\run_step2.ps1