# VisionOCR - OpenCV & Tesseract OCR Text Detection Flask App

A modern, full-stack Python Flask web application for image-based text region detection (bounding boxes) and text extraction using **OpenCV** and **Tesseract OCR (PyTesseract)**.

---

## 🌟 Key Features

- 🔍 **Text Detection & Bounding Boxes**: Automatically locates text regions using `pytesseract.image_to_data` and draws annotated bounding boxes with OpenCV (`cv2.rectangle`).
- 📝 **Full Text Extraction**: Extracts full text content using `pytesseract.image_to_string` with high accuracy.
- 🎨 **Modern Glassmorphism UI**: Sleek dark theme with drag-and-drop file uploader, live file preview, loading state animations, and responsiveness.
- 📊 **OCR Analytics**: Live dashboard showing detected text regions, word count, confidence scores, and image dimensions.
- 📋 **Copy & Download Utilities**: One-click "Copy to Clipboard" and "Download as .txt file".
- 🔄 **Original vs Annotated Toggle**: Instant side-by-side view toggle to compare original vs OCR detected image.

---

## 📁 Project Structure

```
AM_tesseract_AN/
├── app.py                  # Flask backend server & OCR pipeline
├── requirements.txt        # Python package dependencies
├── README.md               # Documentation and setup instructions
├── static/
│   ├── css/
│   │   └── style.css       # Design system & responsive layout
│   ├── js/
│   │   └── main.js         # Interactive file handling & AJAX logic
│   └── uploads/            # Temporary storage for uploaded/annotated images
└── templates/
    └── index.html          # HTML5 UI template
```

---

## 🛠️ System Prerequisites

Ensure you have Python 3 and the **Tesseract OCR engine binary** installed on your system.

### Installing Tesseract OCR Engine:

- **macOS** (Homebrew):
  ```bash
  brew install tesseract
  ```

- **Ubuntu / Debian**:
  ```bash
  sudo apt update
  sudo apt install -y tesseract-ocr libtesseract-dev
  ```

- **Windows**:
  Download and install the official binary installer from [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).
  Ensure `C:\Program Files\Tesseract-OCR` is added to your System PATH environment variables.

---

## 🚀 Quickstart & Installation

1. **Clone or Navigate to Project Directory**:
   ```bash
   cd AM_tesseract_AN
   ```

2. **Create & Activate a Virtual Environment** (Optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # On Windows: venv\Scripts\activate
   ```

3. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Flask Application**:
   ```bash
   python app.py
   ```

5. **Open Application in Web Browser**:
   Open your browser and visit: `http://127.0.0.1:5000`

---

## 🧪 Testing & Verification

1. Drag & drop or select an image containing text (`.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.pdf`).
2. Click **Process & Detect Text**.
3. View the generated bounding box image highlighting detected text regions.
4. Copy or download the extracted OCR text!
