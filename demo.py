import json, os, boto3, openai
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class Item(BaseModel):
    name        : str
    price       : float
    currency    : str = "USD"
    confidence  : float = Field(ge=0, le=1)

class VendorDoc(BaseModel):
    vendor : str
    items  : list[Item]
    flags  : list[dict] = []

# ---- AWS Textract ----
def textract_pdf(path: str):
    client = boto3.client("textract", region_name=os.getenv("REGION"))
    with open(path, "rb") as f:
        resp = client.analyze_document(Document={"Bytes": f.read()}, FeatureTypes=["TABLES"])
    blocks = resp["Blocks"]
    # crude table grab (first table found)
    table = [b for b in blocks if b["BlockType"] == "TABLE"][0]
    cells = [b for b in blocks if b["BlockType"] == "CELL" and b["Id"] in table["Relationships"][0]["Ids"]]
    rows = {}
    for c in cells:
        row = c["RowIndex"]
        text = " ".join([blocks[i]["Text"] for i in c["Relationships"][0]["Ids"] if blocks[i]["BlockType"] == "WORD"])
        rows.setdefault(row, []).append(text)
    return list(rows.values())   # list of row strings

# ---- GPT mapper ----
def map_to_json(rows: list):
    system = """
You convert raw table rows into strict JSON matching this Pydantic schema:
class Item(BaseModel):
    name: str
    price: float
    currency: str = "USD"
    confidence: float   # 0-1
class VendorDoc(BaseModel):
    vendor: str
    items: list[Item]
    flags: list[dict]   # [{"row_id":int, "reason":str}]
Rules:
- If price missing or unreadable → skip row OR set flag.
- If currency missing → flag.
- confidence = 0.9 if perfect, 0.7 if small issue, 0.5 if guessed.
Return only JSON, no commentary.
"""
    user = "Table rows:\n" + "\n".join(map(str, rows))
    resp = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0
    )
    return json.loads(resp.choices[0].message.content)

# ---- runner ----
if __name__ == "__main__":
    rows = textract_pdf("sample_menu.pdf")      # drop any PDF in folder
    result = map_to_json(rows)
    with open("output.json", "w") as f:
        json.dump(result, f, indent=2)
    print("✅ output.json created")
