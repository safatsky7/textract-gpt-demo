import os, json, boto3, openai
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()

# --- Pydantic Schema ---
class Item(BaseModel):
    name: str
    price: float
    currency: str = "USD"
    confidence: float = Field(ge=0, le=1)

class VendorDoc(BaseModel):
    vendor: str
    items: list[Item]
    flags: list[dict] = []

# --- AWS Textract ---
def textract_pdf(path: str):
    client = boto3.client("textract", region_name=os.getenv("REGION"))
    with open(path, "rb") as f:
        resp = client.analyze_document(
            Document={"Bytes": f.read()},
            FeatureTypes=["TABLES"]
        )
    blocks = {b["Id"]: b for b in resp["Blocks"]}
    tables = [b for b in resp["Blocks"] if b["BlockType"] == "TABLE"]
    if not tables:
        raise ValueError("⚠️ No tables found in PDF")

    all_rows = []
    for t in tables:
        cell_ids = [cid for rel in t.get("Relationships", [])
                    if rel["Type"] == "CHILD"
                    for cid in rel["Ids"]]
        cells = [blocks[cid] for cid in cell_ids if blocks[cid]["BlockType"] == "CELL"]
        row_map = {}
        for c in cells:
            words = []
            for rel in c.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for wid in rel["Ids"]:
                        w = blocks[wid]
                        if w["BlockType"] == "WORD":
                            words.append(w["Text"])
            text = " ".join(words).strip()
            row_map.setdefault(c["RowIndex"], []).append(text)
        all_rows.extend(list(row_map.values()))
    return all_rows

# --- GPT Mapper ---
def map_to_json(rows: list):
    system = """
You are a parser. Convert raw table rows into valid JSON matching this schema:
class Item { name:str, price:float, currency:str='USD', confidence:float }
class VendorDoc { vendor:str, items:list[Item], flags:list[dict] }

Rules:
- If price missing or invalid -> add {"row_id":int, "reason":str} in flags.
- If currency missing -> default to USD but flag it.
- confidence: 0.9 if clear, 0.7 if minor issue, 0.5 if guess.
ALWAYS return valid JSON. Nothing else.
"""
    user = "Rows:\n" + "\n".join(map(str, rows))

    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0
    )

    content = resp.choices[0].message.content.strip()

    # Auto-fix if GPT returns extra text
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        content = content[content.find("{"): content.rfind("}") + 1]
        data = json.loads(content)

    try:
        return VendorDoc(**data).dict()
    except ValidationError as e:
        print("⚠️ Schema validation failed:", e)
        return {"items": [], "flags": [{"reason": "validation_error"}]}

# --- Runner ---
if __name__ == "__main__":
    pdf_path = "sample_menu.pdf"
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Missing {pdf_path}")
    rows = textract_pdf(pdf_path)
    result = map_to_json(rows)
    with open("output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("✅ output.json created")
