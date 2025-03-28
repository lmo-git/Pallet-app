import streamlit as st
from PIL import Image
import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.write("Loaded Email:", st.secrets["google_service_account"]["client_email"])


# Set the title of the application
st.title("📦 Pallet Detection & Save to Drive")

# --- Step 1: กรอกเลขอ้างอิงเอกสารด้วยตนเอง ---
st.subheader("1️⃣ Document Reference")
ocr_text = st.text_input("Enter document reference (e.g., PT123456)")

# --- Step 2: ถ่ายภาพ Pallet ---
st.subheader("2️⃣ Pallet Detection")
pallet_image_file = st.camera_input("Capture a pallet photo")
detected_count = 0  # Default value

if pallet_image_file:
    pallet_image = Image.open(pallet_image_file)
    temp_image_path = "pallet_temp.jpg"
    pallet_image.save(temp_image_path)

    # --- Step 3: Roboflow Inference ---
    st.subheader("🔍 Detecting Pallets...")
    try:
        from inference_sdk import InferenceHTTPClient

        CLIENT = InferenceHTTPClient(
            api_url="https://detect.roboflow.com",
            api_key="WtsFf6wpMhlX16yRNb6e"
        )

        result = CLIENT.infer(temp_image_path, model_id="pallet-detection-measurement/1")
        predictions = result.get("predictions", [])
        detected_count = len(predictions)
        st.write(f"✅ Detected Pallets: {detected_count}")

    except Exception as e:
        st.error(f"❌ Error during inference: {e}")
        detected_count = 0

# --- Step 4: ยืนยันจำนวนพาเลท ---
st.subheader("3️⃣ Confirm Pallet Count")
pallet_count_str = st.text_input("Enter number of pallets", value=str(detected_count))
try:
    pallet_count = int(pallet_count_str)
except ValueError:
    pallet_count = 0
    st.warning("⚠️ Pallet count is invalid. Defaulting to 0.")

# --- Step 5: บันทึกข้อมูลลง Google Sheets และ Drive ---
if st.button("✅ Confirm and Save Data"):
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        service_account_info = st.secrets["google_service_account"]
        creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)

        gc = gspread.authorize(creds)
        sheet = gc.open_by_key("1ed2x0LCFSFhxewFRUZZiJO-h2tNnv11o8xbmrCazgMA").sheet1
        drive_service = build('drive', 'v3', credentials=creds)

        # Google Drive Folder Handling
        folder_name = "Pallet"
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        folder_id = files[0]['id'] if files else drive_service.files().create(
            body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'},
            fields='id'
        ).execute()['id']

        # Create filename and upload to Drive
        file_name = ocr_text.strip().replace(" ", "_") if ocr_text.strip() else "pallet_image"
        file_name += ".jpg"

        media = MediaFileUpload(temp_image_path, mimetype='image/jpeg')
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        uploaded_file_id = uploaded_file.get('id')
        file_link = f"https://drive.google.com/file/d/{uploaded_file_id}/view?usp=sharing"

        # Save to Google Sheet
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, ocr_text, pallet_count, file_link]
        sheet.append_row(row)

        st.success("🎉 Data saved successfully to Google Drive and Google Sheets!")

    except Exception as e:
        st.error(f"❌ Failed to save data: {e}")
