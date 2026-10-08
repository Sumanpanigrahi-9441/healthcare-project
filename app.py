from flask import Flask, render_template, request
from google import genai
from google.genai import types
import sqlite3
import base64

app = Flask(__name__)


def create_database():
    conn = sqlite3.connect("healthcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            symptoms TEXT,
            triage_level TEXT,
            zone TEXT,
            department TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            location TEXT,
            department TEXT,
            beds INTEGER,
            emergency TEXT,
            contact TEXT,
            verified TEXT DEFAULT 'No',
            source TEXT
        )
    """)

    conn.commit()
    conn.close()


create_database()


def update_hospital_table():

    conn = sqlite3.connect("healthcare.db")
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(hospitals)")
    columns = [column[1] for column in cursor.fetchall()]

    if "verified" not in columns:
        cursor.execute(
            "ALTER TABLE hospitals ADD COLUMN verified TEXT DEFAULT 'No'"
        )

    if "source" not in columns:
        cursor.execute(
            "ALTER TABLE hospitals ADD COLUMN source TEXT"
        )

    conn.commit()
    conn.close()


update_hospital_table()


API_KEY = "AQ.Ab8RN6K7_EFFPJHC_jbxVbHq-BR8_Ojxl_9czzsRSjtw2fXgFg"

client = genai.Client(api_key=API_KEY)


@app.route('/', methods=['GET', 'POST'])
def index():

    result = None
    recommended_hospital = None

    if request.method == 'POST':

        patient_name = request.form.get('name')
        age = request.form.get('age')
        gender = request.form.get('gender')
        symptoms = request.form.get('symptoms')
        voice_language = request.form.get('voice_language')

        medical_scan = request.files.get('medical_scan')

        if voice_language == "or-IN":
            selected_language = "Odia"
        elif voice_language == "hi-IN":
            selected_language = "Hindi"
        else:
            selected_language = "English"

        prompt = f"""
You are a medical triage assistant.

Patient Details:
Name: {patient_name}
Age: {age}
Gender: {gender}
Symptoms: {symptoms}

The user selected language: {selected_language}

Give the complete answer in {selected_language}.

Give the answer in this format:

1. Triage Level:

2. Recommended Department:Give only the department name on the same line.

3. Initial Action/First Aid:

4. Possible Medicines:
- Mention only safe general or OTC supportive options if appropriate.
- Do not prescribe prescription medicines.
- Do not give unsafe medicine recommendations.
- If a doctor should be consulted, clearly say so.

5. Recommended Doctor/Hospital:
- Doctor name, if verified information is available
- Hospital/Clinic name
- Contact number
- Address

6. Recommended Hospital:
- Hospital name
- Contact number
- Full address

7. Scan/Medical Report Summary:
- Explain important information in simple language.
- Do not give a final diagnosis from the scan.
- Clearly say if a doctor should be consulted.

8. Reason:

Use simple and clear language.

Important:
This is only a triage-support tool, not a medical diagnosis.

Safety and Privacy:
- Do not make a final medical diagnosis.
- Do not prescribe prescription medicines or treatments.
- Give guidance only for triage and healthcare navigation.
- Do not expose unnecessary personal information.
- Do not invent doctor names, hospital names, phone numbers or addresses.
- Use only verified hospital information when available.
- The prototype uses simulated or representative patient and hospital data.
- Do not claim that simulated data is real hospital data.
- If symptoms appear serious or life-threatening, recommend immediate emergency medical care.
- Do not give false assurance that the patient is safe.

If reliable hospital or doctor information is not available,
clearly say that the user should check an official hospital
website or Google Maps instead of making up information.
"""



        if medical_scan and medical_scan.filename:

            scan_data = medical_scan.read()

            scan_part = types.Part.from_bytes(
                data=scan_data,
                mime_type=medical_scan.mimetype
            )

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[
                    prompt,
                    scan_part
                ]
            )

        else:

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )

        result = response.text

        if "Emergency" in result:
            triage_level = "Emergency"
            zone = "Red"

        elif "Urgent" in result:
            triage_level = "Urgent"
            zone = "Yellow"

        else:
            triage_level = "Normal"
            zone = "Green"

        department = "Not specified"

        for line in result.splitlines():

            if "Recommended Department:" in line:
                department = line.split(":", 1)[1].strip()
                break

        conn = sqlite3.connect("healthcare.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, location, department, beds, emergency, contact, verified, source
            FROM hospitals
            WHERE verified = 'Yes'
        """)

        hospitals = cursor.fetchall()

        conn.close()

        for hospital in hospitals:

            hospital_departments = hospital[2].lower()
            recommended_department = department.lower()

            if recommended_department in hospital_departments:
                recommended_hospital = hospital
                break

        conn = sqlite3.connect("healthcare.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients
            (name, age, gender, symptoms, triage_level, zone, department)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            patient_name,
            age,
            gender,
            symptoms,
            triage_level,
            zone,
            department
        ))

        conn.commit()
        conn.close()

    return render_template(
        'index.html',
        result=result,
        recommended_hospital=recommended_hospital
    )


@app.route('/priority')
def priority():

    conn = sqlite3.connect("healthcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, age, gender, symptoms, triage_level, zone, department
        FROM patients
        ORDER BY CASE zone
            WHEN 'Red' THEN 1
            WHEN 'Yellow' THEN 2
            WHEN 'Green' THEN 3
        END, id DESC
    """)

    patients = cursor.fetchall()

    conn.close()

    return render_template(
        'priority.html',
        patients=patients
    )


@app.route('/hospitals')
def hospitals():

    conn = sqlite3.connect("healthcare.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, name, location, department, beds, emergency, contact, verified, source
        FROM hospitals
        ORDER BY name
    """)

    hospital_list = cursor.fetchall()

    conn.close()

    return render_template(
        'hospitals.html',
        hospitals=hospital_list
    )


@app.route('/add-hospital', methods=['GET', 'POST'])
def add_hospital():

    if request.method == 'POST':

        name = request.form.get('name')
        location = request.form.get('location')
        department = request.form.get('department')
        beds = request.form.get('beds')
        emergency = request.form.get('emergency')
        contact = request.form.get('contact')
        verified = request.form.get('verified')
        source = request.form.get('source')

        conn = sqlite3.connect("healthcare.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO hospitals
            (name, location, department, beds, emergency, contact, verified, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name,
            location,
            department,
            beds,
            emergency,
            contact,
            verified,
            source
        ))

        conn.commit()
        conn.close()

        return render_template(
            "add-hospital.html",
            message="Hospital data added successfully."
        )

    return render_template("add-hospital.html")


@app.route('/generate-image', methods=['POST'])
def generate_image():

    symptoms = request.form.get('symptoms')

    image_prompt = f"""
Create a simple educational medical illustration related to these symptoms:

{symptoms}

Show the relevant human body system or medical concept.
Do not show a real patient.
Do not make a diagnosis.
The image should be suitable for healthcare education and triage support.
"""

    interaction = client.interactions.create(
        model="gemini-nano-banana-2.1",
        input=image_prompt,
        generation_config={
            "thinking_level": "minimal"
        }
    )

    image_data = base64.b64decode(
        interaction.output_image.data
    )

    with open("static/generated_medical_image.png", "wb") as f:
        f.write(image_data)

    return render_template(
        "index.html",
        result="Medical image generated successfully."
    )


if __name__ == '__main__':
    app.run(debug=True)
