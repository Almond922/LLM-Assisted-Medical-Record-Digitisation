import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_ocr_with_file():
    api_key = os.getenv('OCR_API_KEY')
    
    if not api_key:
        print("❌ API Key not found in .env file!")
        return
    
    print("✅ API Key loaded successfully!")
    print(f"Testing OCR.space API with local file...")
    
    # Path to your test prescription image
    image_path = 'uploads/6.jpg'  # Change to .png if needed
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found at: {image_path}")
        print("Please add a prescription image to the uploads folder!")
        return
    
    print(f"✅ Image found: {image_path}")
    
    # Open and send the image file
    with open(image_path, 'rb') as f:
        payload = {
            'apikey': api_key,
            'language': 'eng',
            'isOverlayRequired': False,
            'detectOrientation': True,
            'scale': True,
            'OCREngine': 2,  # Engine 2 is better for handwriting
        }
        
        files = {
            'file': f
        }
        
        try:
            response = requests.post('https://api.ocr.space/parse/image', 
                                    data=payload, 
                                    files=files)
            result = response.json()
            
            if result['IsErroredOnProcessing']:
                print("❌ OCR Processing Error:", result['ErrorMessage'])
            else:
                print("\n✅ OCR Test Successful!")
                print("\n📄 Extracted Text:")
                print("=" * 60)
                extracted_text = result['ParsedResults'][0]['ParsedText']
                print(extracted_text)
                print("=" * 60)
                print(f"\n📊 Characters extracted: {len(extracted_text)}")
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    test_ocr_with_file()