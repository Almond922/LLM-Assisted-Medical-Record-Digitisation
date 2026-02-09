# LLM-Assisted-Medical-Record-Digitisation

This project digitizes medical prescriptions using OCR and LLMs for anonymization and medicine extraction.

## Features
- User registration/login (patient/staff)
- Upload prescription images (JPG, PNG, PDF)
- OCR extraction (via OCR.space API)
- PII masking (via Ollama LLM)
- Medicine extraction (via Ollama LLM)
- PostgreSQL database
- Flask web interface

## Setup
1. Clone the repo:
   ```
   git clone https://github.com/Almond922/LLM-Assisted-Medical-Record-Digitisation.git
   ```
2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Set up `.env` file with your keys and DB info.
4. Start PostgreSQL and create the database.
5. (Optional) Pull Ollama model:
   ```
   ollama pull phi3
   ```
   Or use `llama3` (default).
6. Run the app:
   ```
   python prescription_digitalization/app.py
   ```
7. Open [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Folder Structure
- `app.py` — main Flask app
- `static/` — CSS/JS
- `templates/` — HTML templates
- `uploads/` — prescription images

## Notes
- Do not commit `.env` (contains secrets)
- Uploaded files may contain sensitive data
- For best results, use clear prescription images

## License
MIT
