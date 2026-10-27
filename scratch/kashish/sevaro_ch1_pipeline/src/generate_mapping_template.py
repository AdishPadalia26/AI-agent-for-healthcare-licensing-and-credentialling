
import argparse, json, yaml
from pathlib import Path
from dateutil.parser import isoparse

LOGICAL_FIELDS = [
    ("full_name", ""), ("dob_mmddyyyy", ""), ("place_of_birth", ""), ("gender", ""), ("citizenship", ""),
    ("ssn_digits", ""), ("npi", ""), ("email", ""), ("phone", ""), ("home_address", ""),
    ("tx_license_number", ""), ("tx_license_issue_mmddyyyy", ""), ("tx_license_expiry_mmddyyyy", ""),
    ("dea_number", ""), ("dea_expiry_mmddyyyy", ""),
    ("medical_school", ""), ("residency", ""), ("fellowship", ""),
    ("board1_label", ""), ("board2_label", ""),
    ("mal_carrier", ""), ("mal_policy_number", ""), ("mal_effective_mmddyyyy", ""), ("mal_expiry_mmddyyyy", ""),
]

def mmddyyyy(iso):
    try:
        return isoparse(iso).strftime("%m/%d/%Y") if iso else ""
    except Exception:
        return iso or ""

def build_suggestions(profile: dict):
    sug = {}
    sug["full_name"] = profile.get("full_name","")
    sug["dob_mmddyyyy"] = mmddyyyy(profile.get("dob",""))
    sug["place_of_birth"] = profile.get("place_of_birth","")
    sug["gender"] = profile.get("gender","")
    sug["citizenship"] = profile.get("citizenship","")
    sug["ssn_digits"] = "".join([c for c in (profile.get("ssn","")) if c.isdigit()])
    sug["npi"] = profile.get("npi","")
    sug["email"] = profile.get("email","")
    sug["phone"] = profile.get("phone","")
    sug["home_address"] = (profile.get("home_address") or "").replace("\\n"," ").replace("\n"," ").strip()

    # Licenses
    sug["tx_license_number"] = ""
    sug["tx_license_issue_mmddyyyy"] = ""
    sug["tx_license_expiry_mmddyyyy"] = ""
    for lic in profile.get("licenses",[]):
        if lic.get("state","").lower().startswith("texas"):
            sug["tx_license_number"] = lic.get("license_number","")
            sug["tx_license_issue_mmddyyyy"] = mmddyyyy(lic.get("issue_date",""))
            sug["tx_license_expiry_mmddyyyy"] = mmddyyyy(lic.get("expiry_date",""))
            break

    # DEA
    dea = profile.get("dea",{})
    sug["dea_number"] = dea.get("number","")
    sug["dea_expiry_mmddyyyy"] = mmddyyyy(dea.get("expiry_date",""))

    # Education
    sug["medical_school"] = profile.get("medical_school","")
    sug["residency"] = profile.get("residency","")
    sug["fellowship"] = profile.get("fellowship","")

    # Boards
    boards = profile.get("board_certifications",[])
    if len(boards)>0:
        b1 = boards[0]
        sug["board1_label"] = f"{b1.get('board','')}-{b1.get('specialty','')} #{b1.get('certificate_number','')} ({mmddyyyy(b1.get('valid_from',''))}–{mmddyyyy(b1.get('valid_to',''))})"
    if len(boards)>1:
        b2 = boards[1]
        sug["board2_label"] = f"{b2.get('board','')}-{b2.get('specialty','')} #{b2.get('certificate_number','')} ({mmddyyyy(b2.get('valid_from',''))}–{mmddyyyy(b2.get('valid_to',''))})"

    # Malpractice
    mal = profile.get("malpractice",{})
    sug["mal_carrier"] = mal.get("carrier","")
    sug["mal_policy_number"] = mal.get("policy_number","")
    sug["mal_effective_mmddyyyy"] = mmddyyyy(mal.get("effective",""))
    sug["mal_expiry_mmddyyyy"] = mmddyyyy(mal.get("expiry",""))
    return sug

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--out", default="templates/mapping.yaml")
    args = ap.parse_args()
    prof = json.loads(Path(args.profile).read_text())
    suggestions = build_suggestions(prof)

    mapping = {"form_id": "TX_MultiFacility_App_v1", "fields": []}
    for key, _ in LOGICAL_FIELDS:
        mapping["fields"].append({
            "logical_key": key,
            "field_id": "",
            "value": suggestions.get(key, "")
        })
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml
    Path(args.out).write_text(_yaml.safe_dump(mapping, sort_keys=False))
    print(f"Wrote {args.out}. Fill 'field_id' with ids from out/form_fields.csv.")
