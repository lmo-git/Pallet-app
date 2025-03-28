import streamlit as st
from PIL import Image
import pytesseract
import io
import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Set the title of the application
st.title("📄 Document OCR & Pallet Detection App")

# --- Step 1: Capture document photo ---
st.subheader("Document OCR")
doc_image = st.camera_input("Capture a document photo")
ocr_text = ""

if doc_image:
    # Convert the uploaded file to a PIL Image.
    image = Image.open(doc_image)

    # --- Step 2: OCR processing ---
    # Perform OCR using pytesseract
    full_text = pytesseract.image_to_string(image)
    # Filter lines that begin with "PTXX"
    filtered_lines = [line for line in full_text.splitlines() if line.startswith("PT")]
    ocr_text = "\n".join(filtered_lines)

    st.subheader("OCR Output : ")
    st.text(ocr_text)

# --- Step 3: Capture pallet photo ---
st.subheader("Pallet Detection")
pallet_image_file = st.camera_input("Capture a pallet photo")
detected_count = 0  # Initialize detected count

if pallet_image_file:
    pallet_image = Image.open(pallet_image_file)

    # Save the image temporarily
    temp_image_path = "pallet_temp.jpg"
    pallet_image.save(temp_image_path)

    # --- Step 4: Pallet Detection using Inference SDK ---
    st.subheader("Pallet Detection Inference")
    try:
        from inference_sdk import InferenceHTTPClient

        # Initialize the client with your API details
        CLIENT = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key="WtsFf6wpMhlX16yRNb6e"
        )

        # Perform inference on the pallet image
        result = CLIENT.infer(temp_image_path, model_id="pallet-detection-measurement/1")

        # Extract predictions and count the number of detected pallets
        predictions = result.get("predictions", [])
        detected_count = len(predictions)
        st.write(f"Detected Pallets: {detected_count}")

    except Exception as e:
        st.error(f"Error during inference: {e}")
        detected_count = 0  # Fallback if detection fails

# --- Step 5: User input for number of pallets ---
st.subheader("Confirm Pallet Count")
# Use text_input to capture the pallet count as text
pallet_count_str = st.text_input("Enter the number of pallets", value=str(detected_count))
try:
    pallet_count = int(pallet_count_str)
except ValueError:
    pallet_count = 0
    st.warning("Pallet count was not a valid number. Defaulting to 0.")
# --- Step 6 & 7: Confirm and then save photo to Google Drive & save link in Google Sheets ---
if st.button("Confirm and Save Data"):
    try:
        # Define scopes
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        # Load credentials from st.secrets
        service_account_info = st.secrets["google_service_account"]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
        st.write("Email loaded from secrets:", st.secrets["google_service_account"]["client_email"])


        # Authorize Google Sheets and Drive
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1ed2x0LCFSFhxewFRUZZiJO-h2tNnv11o8xbmrCazgMA").sheet1
        drive_service = build('drive', 'v3', credentials=creds)

        # Handle Drive folder
        folder_name = "Pallet"
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        folder_id = files[0]['id'] if files else drive_service.files().create(
            body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
            fields='id'
        ).execute()['id']

        # Build filename
        file_name = ocr_text.strip().replace(" ", "_").replace("\n", "_") if ocr_text.strip() else "pallet_image"
        file_name += ".jpg"

        # Upload image to Drive
        media = MediaFileUpload(temp_image_path, mimetype='image/jpeg')
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_file_id = uploaded_file.get('id')
        file_link = f"https://drive.google.com/file/d/{uploaded_file_id}/view?usp=sharing"

        # Log to Google Sheet
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, ocr_text, pallet_count, file_link]
        sheet.append_row(row)

        st.success("Data successfully saved to Google Drive & Google Sheets!")

    except Exception as e:
        st.error(f"Failed to save data: {e}")
