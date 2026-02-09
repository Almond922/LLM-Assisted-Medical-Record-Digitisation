from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from dotenv import load_dotenv
import requests
import ollama
from datetime import datetime
import json
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database connection
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    return conn

# Check allowed file
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# OCR function
def extract_text_from_image(image_path):
    api_key = os.getenv('OCR_API_KEY')
    
    with open(image_path, 'rb') as f:
        payload = {
            'apikey': api_key,
            'language': 'eng',
            'isOverlayRequired': False,
            'detectOrientation': True,
            'scale': True,
            'OCREngine': 2,
        }
        files = {'file': f}
        
        try:
            response = requests.post('https://api.ocr.space/parse/image', 
                                    data=payload, 
                                    files=files,
                                    timeout=30)
            result = response.json()
            
            if result['IsErroredOnProcessing']:
                return None, result['ErrorMessage']
            
            extracted_text = result['ParsedResults'][0]['ParsedText']
            return extracted_text, None
            
        except Exception as e:
            return None, str(e)

# PII Masking
def mask_pii(text):
    model_name = os.getenv('OLLAMA_MODEL', 'llama3')
    prompt = f"""You are a medical data anonymization tool. Replace personal information with tokens:

Replace:
- Patient names → [PATIENT_NAME]
- Ages/DOB → [AGE]
- Phone numbers → [PHONE]
- Patient IDs → [PATIENT_ID]
- Addresses → [ADDRESS]

Keep unchanged:
- Medicine names
- Dosages
- Doctor names
- Hospital names

Text:
{text}

Output only the masked text:"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}
        )
        return response['message']['content']
    except Exception as e:
        return text

# Extract medicine data
def extract_medicine_data(ocr_text):
    model_name = os.getenv('OLLAMA_MODEL', 'llama3')
    prompt = f"""Extract medicine information and return ONLY a JSON object:

{{
  "medicines": [
    {{
      "name": "medicine name",
      "dosage": "dosage with unit",
      "route": "route (oral/IV/IM)",
      "frequency": "frequency (OD/BD/TDS)",
      "duration": "duration"
    }}
  ]
}}

If information is missing, use "Not specified".

OCR Text:
{ocr_text}

JSON:"""

    try:
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}
        )
        
        response_text = response['message']['content']
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group(0)
            medicine_data = json.loads(json_str)
            return medicine_data
        else:
            return {"medicines": []}
            
    except Exception as e:
        print(f"Error: {e}")
        return {"medicines": []}

# Home - Login
@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif session['role'] == 'staff':
            return redirect(url_for('staff_dashboard'))
    
    return render_template('login.html')

# Login
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute('SELECT * FROM users WHERE username = %s', (username,))
    user = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = user['role']
        session['full_name'] = user['full_name']
        
        flash('Login successful!', 'success')
        
        if user['role'] == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif user['role'] == 'staff':
            return redirect(url_for('staff_dashboard'))
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('index'))

# Logout
@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

# Registration page
@app.route('/register')
def register_page():
    if 'user_id' in session:
        if session['role'] == 'patient':
            return redirect(url_for('patient_dashboard'))
        elif session['role'] == 'staff':
            return redirect(url_for('staff_dashboard'))
    
    return render_template('register.html')

# Registration handler
@app.route('/register', methods=['POST'])
def register():
    full_name = request.form.get('full_name')
    username = request.form.get('username')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    role = request.form.get('role')
    
    # Validation
    if not all([full_name, username, password, confirm_password, role]):
        flash('All fields are required', 'error')
        return redirect(url_for('register_page'))
    
    if password != confirm_password:
        flash('Passwords do not match', 'error')
        return redirect(url_for('register_page'))
    
    if len(password) < 6:
        flash('Password must be at least 6 characters long', 'error')
        return redirect(url_for('register_page'))
    
    if role not in ['patient', 'staff']:
        flash('Invalid role selected', 'error')
        return redirect(url_for('register_page'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check if username already exists
    cur.execute('SELECT username FROM users WHERE username = %s', (username,))
    existing_user = cur.fetchone()
    
    if existing_user:
        flash('Username already exists. Please choose another.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('register_page'))
    
    # Create new user
    password_hash = generate_password_hash(password)
    
    try:
        cur.execute('''
            INSERT INTO users (username, password_hash, role, full_name)
            VALUES (%s, %s, %s, %s)
        ''', (username, password_hash, role, full_name))
        
        conn.commit()
        flash('Account created successfully! Please sign in.', 'success')
        
    except Exception as e:
        conn.rollback()
        flash(f'Error creating account: {str(e)}', 'error')
    
    cur.close()
    conn.close()
    
    return redirect(url_for('index'))

# Patient Dashboard
@app.route('/patient/dashboard')
def patient_dashboard():
    if 'user_id' not in session or session['role'] != 'patient':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get patient's prescriptions
    cur.execute('''
        SELECT p.prescription_id, p.upload_date, p.image_filename
        FROM prescriptions p
        WHERE p.patient_id = %s
        ORDER BY p.upload_date DESC
    ''', (session['user_id'],))
    
    prescriptions = cur.fetchall()
    
    # Get medicines for each prescription
    for prescription in prescriptions:
        cur.execute('''
            SELECT medicine_name, dosage, frequency, duration
            FROM medicines_extracted
            WHERE prescription_id = %s
        ''', (prescription['prescription_id'],))
        prescription['medicines'] = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('patient_dashboard.html', prescriptions=prescriptions)

# Upload Prescription
@app.route('/upload_prescription', methods=['POST'])
def upload_prescription():
    if 'user_id' not in session or session['role'] != 'patient':
        return redirect(url_for('index'))
    
    if 'prescription' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('patient_dashboard'))
    
    file = request.files['prescription']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('patient_dashboard'))
    
    if file and allowed_file(file.filename):
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{session['user_id']}_{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # OCR Processing
        flash('Processing prescription... Please wait.', 'info')
        ocr_text, ocr_error = extract_text_from_image(filepath)
        
        if ocr_error:
            flash(f'OCR Error: {ocr_error}', 'error')
            return redirect(url_for('patient_dashboard'))
        
        # Mask PII
        masked_text = mask_pii(ocr_text)
        
        # Extract medicines
        medicine_data = extract_medicine_data(ocr_text)
        
        # Save to database
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert prescription (no doctor_id needed)
        cur.execute('''
            INSERT INTO prescriptions (patient_id, image_filename, ocr_raw_text, ocr_masked_text)
            VALUES (%s, %s, %s, %s)
            RETURNING prescription_id
        ''', (session['user_id'], filename, ocr_text, masked_text))
        
        prescription_id = cur.fetchone()[0]
        
        # Insert medicines
        if medicine_data and 'medicines' in medicine_data:
            for med in medicine_data['medicines']:
                # Insert into medicines_extracted
                cur.execute('''
                    INSERT INTO medicines_extracted (prescription_id, medicine_name, dosage, frequency, duration)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (prescription_id, med.get('name', 'Unknown'), med.get('dosage', 'Not specified'), 
                      med.get('frequency', 'Not specified'), med.get('duration', 'Not specified')))
                
                # Update anonymized_medicines
                cur.execute('''
                    SELECT id FROM anonymized_medicines 
                    WHERE medicine_name = %s AND dosage = %s AND frequency = %s
                ''', (med.get('name', 'Unknown'), med.get('dosage', 'Not specified'), 
                      med.get('frequency', 'Not specified')))
                
                existing = cur.fetchone()
                
                if existing:
                    cur.execute('''
                        UPDATE anonymized_medicines 
                        SET prescription_count = prescription_count + 1, last_updated = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (existing[0],))
                else:
                    cur.execute('''
                        INSERT INTO anonymized_medicines (medicine_name, dosage, frequency, duration)
                        VALUES (%s, %s, %s, %s)
                    ''', (med.get('name', 'Unknown'), med.get('dosage', 'Not specified'), 
                          med.get('frequency', 'Not specified'), med.get('duration', 'Not specified')))
        
        conn.commit()
        cur.close()
        conn.close()
        
        flash('Prescription uploaded and processed successfully!', 'success')
        return redirect(url_for('patient_dashboard'))
    
    flash('Invalid file type', 'error')
    return redirect(url_for('patient_dashboard'))

# Staff Dashboard
@app.route('/staff/dashboard')
def staff_dashboard():
    if 'user_id' not in session or session['role'] != 'staff':
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all prescriptions with patient names
    cur.execute('''
        SELECT p.prescription_id, p.upload_date, u.full_name as patient_name
        FROM prescriptions p
        JOIN users u ON p.patient_id = u.user_id
        ORDER BY p.upload_date DESC
    ''')
    prescriptions = cur.fetchall()
    
    # Get medicines for each prescription
    for prescription in prescriptions:
        cur.execute('''
            SELECT medicine_name, dosage, frequency, duration
            FROM medicines_extracted
            WHERE prescription_id = %s
        ''', (prescription['prescription_id'],))
        prescription['medicines'] = cur.fetchall()
    
    # Statistics
    cur.execute('SELECT COUNT(*) as count FROM prescriptions')
    total_prescriptions = cur.fetchone()['count']
    
    cur.execute('SELECT COUNT(*) as count FROM users WHERE role = %s', ('patient',))
    total_patients = cur.fetchone()['count']
    
    cur.execute('SELECT COUNT(DISTINCT medicine_name) as count FROM anonymized_medicines')
    unique_medicines = cur.fetchone()['count']
    
    # Top medicines
    cur.execute('''
        SELECT medicine_name, dosage, frequency, prescription_count
        FROM anonymized_medicines
        ORDER BY prescription_count DESC
        LIMIT 10
    ''')
    top_medicines = cur.fetchall()
    
    # All anonymized medicines
    cur.execute('''
        SELECT medicine_name, dosage, frequency, prescription_count
        FROM anonymized_medicines
        ORDER BY prescription_count DESC
    ''')
    all_medicines = cur.fetchall()

    # Get masked prescription texts (anonymized)
    cur.execute('''
        SELECT prescription_id, upload_date, ocr_masked_text
        FROM prescriptions
        WHERE ocr_masked_text IS NOT NULL
        ORDER BY upload_date DESC
    ''')
    masked_prescriptions = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('staff_dashboard.html',
                         prescriptions=prescriptions,
                         total_prescriptions=total_prescriptions,
                         total_patients=total_patients,
                         unique_medicines=unique_medicines,
                         top_medicines=top_medicines,
                         all_medicines=all_medicines,
                         masked_prescriptions=masked_prescriptions)

# View prescription image
@app.route('/prescription/image/<int:prescription_id>')
def view_prescription_image(prescription_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check access
    if session['role'] == 'patient':
        cur.execute('SELECT image_filename FROM prescriptions WHERE prescription_id = %s AND patient_id = %s', 
                   (prescription_id, session['user_id']))
    else:  # staff
        cur.execute('SELECT image_filename FROM prescriptions WHERE prescription_id = %s', (prescription_id,))
    
    prescription = cur.fetchone()
    cur.close()
    conn.close()
    
    if prescription:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], prescription['image_filename'])
        return send_file(filepath)
    else:
        flash('Access denied', 'error')
        return redirect(url_for('index'))
# Delete prescription (Patient can delete own, Staff can delete any)
@app.route('/prescription/delete/<int:prescription_id>', methods=['POST'])
def delete_prescription(prescription_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Check access rights
    if session['role'] == 'patient':
        # Patient can only delete their own prescriptions
        cur.execute('SELECT prescription_id, image_filename FROM prescriptions WHERE prescription_id = %s AND patient_id = %s', 
                   (prescription_id, session['user_id']))
    elif session['role'] == 'staff':
        # Staff can delete any prescription
        cur.execute('SELECT prescription_id, image_filename FROM prescriptions WHERE prescription_id = %s', 
                   (prescription_id,))
    else:
        cur.close()
        conn.close()
        flash('Access denied', 'error')
        return redirect(url_for('index'))
    
    prescription = cur.fetchone()
    
    if prescription:
        try:
            # Delete associated medicines first (foreign key constraint)
            cur.execute('DELETE FROM medicines_extracted WHERE prescription_id = %s', (prescription_id,))
            
            # Delete prescription
            cur.execute('DELETE FROM prescriptions WHERE prescription_id = %s', (prescription_id,))
            
            # Delete image file
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], prescription['image_filename'])
            if os.path.exists(image_path):
                os.remove(image_path)
            
            conn.commit()
            flash('Prescription deleted successfully!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f'Error deleting prescription: {str(e)}', 'error')
    else:
        flash('Prescription not found or access denied', 'error')
    
    cur.close()
    conn.close()
    
    # Redirect based on role
    if session['role'] == 'patient':
        return redirect(url_for('patient_dashboard'))
    else:
        return redirect(url_for('staff_dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)