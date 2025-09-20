# Any PDF → JSON Pipeline (Demo)
Drop any PDF → get structured JSON + confidence flags in 30 s.

## Stack
AWS Textract • GPT-4 • Python

## ⚙️ Before You Run
1. Clone or download ZIP.
2. Install deps:  
   `pip install -r requirements.txt`
3. Add **real** AWS + OpenAI keys in `.env` (never commit live keys to public repos).
4. Drop any PDF in folder → rename `sample_menu.pdf` or change filename inside `demo.py`.

## Run: 
`python demo.py` → get `output.json`
