import json
import argparse
import re
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from utils import find_first, find_all, normalize_date_iso, only_digits

def read_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(chunks)

def extract_profile(cv_text: str):
    profile = {}
    profile["full_name"] = find_first(r"Full Name:\s*([^\n]+)", cv_text) or find_first(r"Curriculum Vitae\s*\n\s*([A-Za-z ,.'-]+)", cv_text)
    profile["dob"] = normalize_date_iso(find_first(r"Date of Birth:\s*([A-Za-z0-9/,-]+)", cv_text))
    profile["place_of_birth"] = find_first(r"Place of Birth:\s*([^\n]+)", cv_text)
    profile["citizenship"] = find_first(r"Citizenship:\s*([^\n]+)", cv_text)
    profile["gender"] = find_first(r"Gender:\s*([^\n]+)", cv_text)
    profile["race"] = find_first(r"Race:\s*([^\n]+)", cv_text)
    profile["ethnicity"] = find_first(r"Ethnicity:\s*([^\n]+)", cv_text)
    profile["ssn"] = find_first(r"SSN:\s*([0-9\-() ]+)", cv_text)
    profile["npi"] = only_digits(find_first(r"NPI:\s*([0-9\- ]+)", cv_text) or "")
    profile["ecfmg_number"] = find_first(r"ECFMG Certification #:\s*([^\n]+)", cv_text)
    profile["ecfmg_issue_date"] = normalize_date_iso(find_first(r"ECFMG Issue Date:\s*([^\n]+)", cv_text))
    profile["home_address"] = find_first(r"Home Address:\s*([\s\S]*?)\n(?:Phone|Email):", cv_text)
    profile["phone"] = find_first(r"Phone:\s*([^\n]+)", cv_text)
    profile["email"] = find_first(r"Email:\s*([^\n]+)", cv_text)

    lic_rows = find_all(r"(?i)(Texas|Ohio|North Carolina)\s+([A-Z0-9\-]+)\s+(Active|Expired)\s+([0-9/ -]+)\s+([0-9/ -]+)", cv_text)
    licenses = []
    for st, num, status, issue, exp in lic_rows:
        licenses.append({
            "state": st.title(),
            "license_number": num.strip(),
            "status": status.title(),
            "issue_date": normalize_date_iso(issue.strip()),
            "expiry_date": normalize_date_iso(exp.strip())
        })
    profile["licenses"] = licenses

    dea_line = find_first(r"DEA:\s*([^\n]+)", cv_text)
    if dea_line:
        parts = dea_line.split()
        num = next((p for p in parts if p and p.isalnum() and p[0].isalpha()), "")
        status = "Active" if "Active" in dea_line else ("Expired" if "Expired" in dea_line else "")
        dates = re.findall(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", dea_line)
        issue, expiry = (dates[0] if len(dates)>0 else ""), (dates[1] if len(dates)>1 else "")
        profile["dea"] = {"number": num, "status": status, "issue_date": normalize_date_iso(issue), "expiry_date": normalize_date_iso(expiry)}

    boards = []
    for m in re.findall(r"(?i)(Neurology|Epilepsy)[^#]*#\s*([0-9]+)[^\d]+([0-9/]{8,10}).*?([0-9/]{8,10})", cv_text):
        spec, certno, start, end = m
        boards.append({"board":"ABPN", "specialty": spec.title(), "certificate_number": certno, "valid_from": normalize_date_iso(start), "valid_to": normalize_date_iso(end)})
    profile["board_certifications"] = boards

    profile["medical_school"] = find_first(r"MBBS.+?\n([^\n]+)", cv_text)
    profile["residency"] = find_first(r"Residency\s*–\s*([^\n]+)", cv_text)
    profile["fellowship"] = find_first(r"Fellowship\s*–\s*([^\n]+)", cv_text)

    carrier = find_first(r"Professional Liability Insurances[\s\S]*?\n[^\n]*\n([^\n]+)", cv_text)
    policy_no = find_first(r"Policy Number:\s*([A-Z0-9\-]+)", cv_text)
    dates = re.findall(r"Policy Dates:\s*([0-9/ -]+)-\s*([0-9/ -]+)", cv_text)
    if dates:
        eff, exp = dates[0]
        profile["malpractice"] = {
            "carrier": carrier.strip() if carrier else "",
            "policy_number": policy_no or "",
            "effective": normalize_date_iso(eff.strip()),
            "expiry": normalize_date_iso(exp.strip())
        }

    return profile

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", required=True)
    ap.add_argument("--out", default="out/provider_profile.json")
    args = ap.parse_args()
    text = read_pdf_text(args.cv)
    prof = extract_profile(text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(prof, indent=2))
    print(f"Wrote {args.out}")
