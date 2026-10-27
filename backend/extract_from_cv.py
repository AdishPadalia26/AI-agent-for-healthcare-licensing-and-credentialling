import time, re, json, os
from collections import defaultdict
import boto3
from dotenv import load_dotenv

# ---------- Load env (AWS + Gemini) ----------
dotenv_path = os.path.abspath(os.path.join('config', '.env'))
load_dotenv(dotenv_path=dotenv_path)

aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_session_token = os.getenv('AWS_SESSION_TOKEN')  
region_name = os.getenv('AWS_DEFAULT_REGION')

# ---------- Regex ----------
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
NPI_RE   = re.compile(r"\bNPI[:\s#]*([0-9]{8,15})\b", re.I)
DOB_RE   = re.compile(r"(?:Date of Birth|DOB)[:\s]*([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I)

# ---------- Textract ----------
def tex_analyze_bytes(session, file_bytes: bytes):
    cli = session.client("textract")
    return cli.analyze_document(
        Document={"Bytes": file_bytes},
        FeatureTypes=["FORMS", "TABLES"],
    )

def build_block_map(resp):
    return {b["Id"]: b for b in resp.get("Blocks", [])}

def get_text_for_block(block, block_map):
    txt=[]
    for rel in block.get("Relationships", []):
        if rel["Type"] == "CHILD":
            for cid in rel["Ids"]:
                w = block_map[cid]
                if w["BlockType"] == "WORD":
                    txt.append(w.get("Text",""))
                elif w["BlockType"]=="SELECTION_ELEMENT" and w.get("SelectionStatus")=="SELECTED":
                    txt.append("☑")
    return " ".join(txt).strip()

def extract_lines(resp, block_map):
    return [b.get("Text","").strip()
            for b in resp.get("Blocks", [])
            if b["BlockType"]=="LINE" and b.get("Text","").strip()]

def extract_kv(block_map):
    key_map, val_map = {}, {}
    for b in block_map.values():
        if b["BlockType"]=="KEY_VALUE_SET":
            ets = b.get("EntityTypes",[])
            if "KEY" in ets:   key_map[b["Id"]] = b
            if "VALUE" in ets: val_map[b["Id"]] = b
    pairs={}
    for kb in key_map.values():
        k = get_text_for_block(kb, block_map)
        v = ""
        for rel in kb.get("Relationships", []):
            if rel["Type"]=="VALUE":
                vb = block_map.get(rel["Ids"][0])
                v = get_text_for_block(vb, block_map) if vb else ""
        if k: pairs[k]=v
    return pairs

def extract_tables(resp, block_map):
    tables=[]
    for b in resp.get("Blocks", []):
        if b["BlockType"]=="TABLE":
            grid=defaultdict(dict)
            for rel in b.get("Relationships", []):
                if rel["Type"]=="CHILD":
                    for cid in rel["Ids"]:
                        cell = block_map[cid]
                        if cell["BlockType"]=="CELL":
                            r,c = cell["RowIndex"], cell["ColumnIndex"]
                            grid[r][c] = get_text_for_block(cell, block_map)
            max_r = max(grid.keys()) if grid else 0
            max_c = max((max(row.keys()) for row in grid.values()), default=0)
            rows = [[grid[r].get(c,"") for c in range(1,max_c+1)] for r in range(1,max_r+1)]
            tables.append(rows)
    return tables

# ---------- LLM (Gemini) ----------
def safe_json(text: str):
    try: return json.loads(text)
    except: pass
    t = text.strip().replace("```json","").replace("```","").strip()
    return json.loads(t)

def run_gemini(full_text: str, model_name="gemini-2.5-pro"):
    load_dotenv(os.path.join("config",".env"))
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in config/.env")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""
    You are an expert information extractor for physician CVs.
    Read the following CV text and return structured data as valid JSON.
    
    Include fields if available:
    full_name, date_of_birth, place_of_birth, citizenship, gender, race, ethnicity,
    ssn, marital_status, npi, ecfmg_certification_number, ecfmg_issue_date,
    contact_information (address, phone, email),
    address_history, education, postgraduate_training,
    licensure, board_certifications, employment_history,
    hospital_privileges, languages_spoken, clinical_interests,
    peer_review_notes, peer_references, professional_liability_insurance,
    and professional_concerns.

    Return ONLY valid JSON. No text, no explanations.
    CV TEXT:
    {full_text}
    """
    resp = model.generate_content(prompt)
    return safe_json(resp.text or "")

# ---------- Reconciliation ----------
def pick_best(llm_val, fallback_val, validator=None):
    def ok(v):
        if v is None: return False
        if isinstance(v, str) and not v.strip(): return False
        return validator(v) if validator else True

    if ok(llm_val):
        return llm_val, {"source":"llm","confidence":0.9}
    if ok(fallback_val):
        return fallback_val, {"source":"textract","confidence":0.7}
    return llm_val or fallback_val, {"source":"unknown","confidence":0.4}

def first_match(rx, text):
    m = rx.search(text)
    if m: return (m.group(1) if m.groups() else m.group(0))
    return None

def is_email(v): return bool(EMAIL_RE.fullmatch(v or ""))
def is_phone(v): return bool(PHONE_RE.fullmatch(v or ""))
def is_npi(v):   return bool(re.fullmatch(r"\d{8,15}", (v or "").strip()))
def is_dob(v):   return bool(re.fullmatch(r"[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", (v or ""), re.I))

# ---------- Public function ----------
def extract(file_bytes: bytes, *, region: str = None, profile: str = None, gemini_model: str = "gemini-2.5-pro") -> str:
    """
    Extract structured physician CV data from uploaded file bytes.
    Returns: JSON string.
    """
    session = boto3.Session(profile_name=profile, region_name=region or region_name)

    # 1) Textract OCR
    resp = tex_analyze_bytes(session, file_bytes)
    block_map = build_block_map(resp)
    kv = extract_kv(block_map)
    lines = extract_lines(resp, block_map)
    tables = extract_tables(resp, block_map)
    full_text = "\n".join(lines)

    # 2) LLM extraction
    llm = run_gemini(full_text, model_name=gemini_model) or {}

    # 3) Validation and reconciliation
    kv_norm = {re.sub(r"[^a-z0-9]+"," ", k.lower()).strip(): v for k,v in kv.items()}
    def kv_get(*aliases):
        for a in aliases:
            if a in kv_norm: return kv_norm[a]
        return None

    tx_email = kv_get("email","e mail","email address") or first_match(EMAIL_RE, full_text)
    tx_phone = kv_get("phone","telephone","mobile") or first_match(PHONE_RE, full_text)
    tx_npi   = kv_get("npi","npi number") or first_match(NPI_RE, full_text)
    tx_dob   = kv_get("date of birth","dob") or first_match(DOB_RE, full_text)

    llm_contact = llm.get("contact_information") or {}

    full_name, prov_name = pick_best(llm.get("full_name"), kv_get("full name","name","provider name","applicant name"))
    dob, prov_dob        = pick_best(llm.get("date_of_birth"), tx_dob, is_dob)
    npi, prov_npi        = pick_best(llm.get("npi"), tx_npi, is_npi)
    email, prov_email    = pick_best(llm_contact.get("email"), tx_email, is_email)
    phone, prov_phone    = pick_best(llm_contact.get("phone"), tx_phone, is_phone)
    address, prov_addr   = pick_best(llm_contact.get("address"), kv_get("address","home address","mailing address"))

    out = {
        "full_name": full_name,
        "date_of_birth": dob,
        "place_of_birth": llm.get("place_of_birth"),
        "citizenship": llm.get("citizenship"),
        "gender": llm.get("gender"),
        "race": llm.get("race"),
        "ethnicity": llm.get("ethnicity"),
        "ssn": llm.get("ssn"),
        "marital_status": llm.get("marital_status"),
        "npi": npi,
        "ecfmg_certification_number": llm.get("ecfmg_certification_number"),
        "ecfmg_issue_date": llm.get("ecfmg_issue_date"),
        "contact_information": {
            "address": address,
            "phone": phone,
            "email": email
        },
        "address_history": llm.get("address_history"),
        "education": llm.get("education"),
        "postgraduate_training": llm.get("postgraduate_training"),
        "licensure": llm.get("licensure"),
        "board_certifications": llm.get("board_certifications"),
        "employment_history": llm.get("employment_history"),
        "hospital_privileges": llm.get("hospital_privileges"),
        "languages_spoken": llm.get("languages_spoken"),
        "clinical_interests": llm.get("clinical_interests"),
        "peer_review_notes": llm.get("peer_review_notes"),
        "peer_references": llm.get("peer_references"),
        "professional_liability_insurance": llm.get("professional_liability_insurance"),
        "professional_concerns": llm.get("professional_concerns"),
        "_provenance": {
            "full_name": prov_name,
            "date_of_birth": prov_dob,
            "npi": prov_npi,
            "contact_information.email": prov_email,
            "contact_information.phone": prov_phone,
            "contact_information.address": prov_addr,
            "llm_model": gemini_model
        },
        "kv_raw": kv,
        "full_text": full_text,
        "tables": tables
    }

    # Return JSON string
    return json.dumps(out, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit("This module is for import only. Use extract(file_bytes) from app.py.")
