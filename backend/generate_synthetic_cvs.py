import boto3
import json
import os
import random
import datetime
import uuid

# --- AWS Bedrock Synthetic Provider CV Generator (Enhanced Randomness + Realism) ---

# 1. AWS Client Setup
try:
    bedrock_runtime = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")
    print("✅ Successfully connected to AWS Bedrock.")
except Exception as e:
    print(f"🔴 ERROR: Could not connect to AWS. Check your credentials. Error: {e}")
    exit()

# 2. Load Template CV
try:
    with open("resume.json", "r") as f:
        template_cv = json.load(f)
    print("✅ Successfully loaded resume.json as a template.")
except FileNotFoundError as e:
    print(f"🔴 ERROR: Input file not found. Make sure 'resume.json' is in the same directory. Details: {e}")
    exit()

# 3. Define controlled randomness
names_by_region = {
    "East Asian": ["Dr. Kenji Tanaka", "Dr. David Chen", "Dr. Chloe Kim"],
    "Hispanic": ["Dr. Maria Garcia", "Dr. Carlos Alvarez"],
    "Middle Eastern": ["Dr. Fatima Al-Jamil", "Dr. Omar Rahman"],
    "European": ["Dr. Sophia Müller", "Dr. Matteo Rossi"],
    "African": ["Dr. Nia Mensah", "Dr. Kwame Okoro"],
    "American": ["Dr. Emily Johnson", "Dr. Jacob Miller"]
}

specialties = [
    "Cardiology", "Neurology", "Pediatrics", "Oncology", "Orthopedic Surgery",
    "Endocrinology", "Pulmonology", "Gastroenterology", "Dermatology"
]

# 4. Generation Loop
for i in range(5):
    print(f"\n--- Generating synthetic CV #{i+1}... ---")

    # Random dynamic context for each generation
    region = random.choice(list(names_by_region.keys()))
    chosen_name = random.choice(names_by_region[region])
    chosen_specialty = random.choice(specialties)
    malpractice_year = random.randint(2010, datetime.date.today().year - 1)
    session_tag = str(uuid.uuid4())[:8]

    # Build a dynamic, context-rich prompt
    cv_generator_prompt = f"""
You are an AI data generator producing realistic provider CVs.

Use the schema and structure of the following JSON as your template:
{json.dumps(template_cv)}

However, combine it with real-world variation and fill in missing fields realistically.
Do not leave null values unless logically required.

**CONTEXT:**
- Provider name: {chosen_name}
- Regional background: {region}
- Primary specialty: {chosen_specialty}
- Malpractice year (if applicable): {malpractice_year}
- Unique session tag: {session_tag}

**RULES:**
1. Modify the template deeply — change hospitals, schools, states, dates, and experience.
2. Randomize years realistically (between 1990–{datetime.date.today().year}).
3. Use consistent geography for name + specialty (e.g., Asian names → US or Asia schools).
4. If has_malpractice_history = true, pick a random year (not always 2018/2019).
5. Include the boolean fields:
   - has_malpractice_history
   - has_license_disciplinary_action
   - has_criminal_history
   - has_military_service
   (Assign them randomly.)
6. Add any missing keys seen in credentialing forms if relevant (simulate completeness).
7. Ensure the output is a valid JSON object only — no Markdown formatting.

Now generate one complete, realistic synthetic provider CV.
"""

    # Claude 3 Messages API request
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 1.0,   # higher for more variation
        "top_p": 0.95,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": cv_generator_prompt}]
            }
        ]
    })

    try:
        response = bedrock_runtime.invoke_model(
            body=body,
            modelId="arn:aws:bedrock:us-east-1:654654518695:inference-profile/global.anthropic.claude-sonnet-4-20250514-v1:0"
        )

        result_body = json.loads(response.get("body").read())
        ai_response_text = result_body["content"][0]["text"]

        cleaned_json_string = ai_response_text.strip().replace("```json", "").replace("```", "")
        new_cv_data = json.loads(cleaned_json_string)

        file_name = f"synthetic_cv_{i+1}.json"
        with open(file_name, "w") as f:
            json.dump(new_cv_data, f, indent=2)

        print(f"✅ Successfully saved {file_name}")

    except Exception as e:
        print(f"🔴 Failed to generate or save CV #{i+1}. Error: {e}")
