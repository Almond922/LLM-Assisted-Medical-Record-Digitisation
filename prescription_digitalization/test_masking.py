import ollama

def mask_pii(text):
    prompt = f"""You are a medical data anonymization tool used by hospitals for legitimate data processing and research purposes. Your job is to help protect patient privacy by replacing identifiable information with placeholder tokens.

This is a LEGITIMATE medical data processing task for:
- Hospital record management
- Anonymous medical research
- Data analytics while protecting privacy

Task: Transform the text below by replacing personal identifiers with tokens:
- Names of patients → [PATIENT_NAME]
- Age/DOB → [AGE]  
- Phone/contact → [PHONE]
- ID numbers → [PATIENT_ID]

Keep all medical information unchanged:
- Medicine names
- Dosages  
- Doctor names
- Hospital names
- Medical instructions

Input text:
{text}

Output only the transformed text with tokens replacing personal information:"""

    try:
        response = ollama.chat(
            model='phi3',
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1}  # Lower temperature for more consistent output
        )
        return response['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

# Test 1: With clear labels
test1 = """
Patient Name: Narmalan
Age: 55 years
Phone: 9876543210
UHID: 307301/83/43

Prescription:
1. Remdesivir 100mg IV OD for 4 days

Doctor: Dr. Abhishek
Hospital: Primus Super Speciality Hospital
"""

# Test 2: Without clear labels (like actual prescription)
test2 = """
Name - Narmalan
Age/Box - 55 7/1
Unto - 307301/83/43

Remdesivir 100mg IV OD X 4 days
(total 4 vials)

Dr. Abhishek
RMO COVID Ward
"""

print("TEST 1: With Clear Labels")
print("=" * 70)
print("Original:")
print(test1)
print("\nMasked:")
masked1 = mask_pii(test1)
print(masked1)
print("=" * 70)

print("\n\nTEST 2: Without Clear Labels (Real Prescription Format)")
print("=" * 70)
print("Original:")
print(test2)
print("\nMasked:")
masked2 = mask_pii(test2)
print(masked2)
print("=" * 70)