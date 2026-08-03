# Solar Analyzer Backend V1

Flow: Upload → Parser → Detector → Normalizer → Calculator → JSON

Run:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs
