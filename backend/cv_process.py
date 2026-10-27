import pdfplumber
import google.generativeai as genai
import json
import os

# ---------- SETUP ----------
# Set your Gemini API key
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key= os.getenv("GOOGLE_API_KEY"))

# ---------- STEP 1: Extract text from PDF ----------
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

# ---------- STEP 2: Send the CV text to Gemini ----------
def extract_fields_with_gemini(cv_text):
    model = genai.GenerativeModel("gemini-2.5-pro")

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
    {cv_text}
    """

    response = model.generate_content(prompt)
    return response.text.strip()

# ---------- STEP 3: Parse and Save JSON ----------
def parse_json_output(raw_output):
    try:
        return json.loads(raw_output)
    except:
        cleaned = raw_output.strip()
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except Exception as e:
            print("⚠️ Could not fully parse JSON, returning raw text instead.")
            return {"raw_output": raw_output}

# ---------- STEP 4: Full Pipeline ----------
def cv_to_json(pdf_path, output_json="cv_output.json"):
    print("Extracting text from PDF...")
    text = extract_text_from_pdf(pdf_path)

    print("Sending to Gemini for field extraction...")
    raw_json = extract_fields_with_gemini(text)

    print("Parsing AI output...")
    data = parse_json_output(raw_json)

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Saved structured JSON to: {output_json}")
    return data

# ---------- RUN ----------
if __name__ == "__main__":
    pdf_path = "Generated_CV_Reordered_V2.pdf"  
    result = cv_to_json(pdf_path)
    print(json.dumps(result, indent=2))
