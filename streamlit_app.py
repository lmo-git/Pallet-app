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
ocr_text = st.text_input("Enter document reference (e.g., PT123456)")

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
        # Define required scopes for Google Sheets and Google Drive
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        # Load credentials from the JSON file with specified scopes
        json_key = st.secrets["gcp"]
        creds = Credentials.from_service_account_info(json_key, scopes = scopes)

        # Authorize with Google Sheets using gspread
        gc = gspread.authorize(creds)
        # Open the Google Sheet using its key (replace with your sheet key)
        sheet = gc.open_by_key("1ed2x0LCFSFhxewFRUZZiJO-h2tNnv11o8xbmrCazgMA").sheet1

        # Build Google Drive service
        drive_service = build('drive', 'v3', credentials=creds)

        # Check for a folder named "pallet folder" in Drive (create if it doesn't exist)
        folder_name = "Pallet"
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        if files:
            folder_id = files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')

        # Create a file name based on OCR text; if OCR text is empty, use a default name
        if ocr_text.strip():
            file_name = ocr_text.strip().replace(" ", "_").replace("\n", "_")
        else:
            file_name = "pallet_image"
        file_name += ".jpg"

        # Upload the image file to Google Drive within the specified folder
        media = MediaFileUpload(temp_image_path, mimetype='image/jpeg')
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_file_id = uploaded_file.get('id')
        # Construct a sharable link for the uploaded file
        file_link = f"https://drive.google.com/file/d/{uploaded_file_id}/view?usp=sharing"

        # Create a timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Prepare row data: timestamp, OCR text, pallet count, and Google Drive file link
        row = [timestamp, ocr_text, pallet_count, file_link]
        # Append the row to the sheet
        sheet.append_row(row)
        st.success("Data successfully saved to Google Drive & Google Sheets!")
    except Exception as e:
        st.error(f"Failed to save data: {e}")