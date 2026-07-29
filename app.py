import os
import uuid
import shutil
import cv2
import numpy as np
import pytesseract
from PIL import Image
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename

try:
    # pyrefly: ignore [missing-import]
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ocr-tesseract-secret-key-2026')

# Configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'}
PDF_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB max upload limit

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Tesseract config: single uniform block of text (justified prose paragraphs).
# Switch to '--oem 3 --psm 3' if you need multi-column / mixed layout support.
TESS_CONFIG = r'--oem 3 --psm 6'


# System check for Tesseract binary path fallback
def configure_tesseract():
    if not shutil.which('tesseract'):
        possible_paths = [
            '/opt/homebrew/bin/tesseract',
            '/usr/local/bin/tesseract',
            '/usr/bin/tesseract',
            'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

configure_tesseract()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_pdf(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in PDF_EXTENSIONS


def _remove_underlines(binary_img):
    """Erase long, thin horizontal strokes (hand-drawn underlines) so they
    stop fusing with descenders (g, y, p, f). This is what breaks words
    like 'mindfulness' and 'experience' when underlines run through them."""
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    detected = cv2.morphologyEx(binary_img, cv2.MORPH_OPEN, horiz_kernel, iterations=1)
    cnts, _ = cv2.findContours(detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cleaned = binary_img.copy()
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w > 20 and h <= 4:  # wide + thin => underline stroke, not a letter
            cv2.rectangle(cleaned, (x, y - 1), (x + w, y + h + 1), 0, -1)
    return cleaned


def preprocess_for_ocr(img):
    """Clean up a scanned page image before handing it to Tesseract.

    Steps: grayscale -> upscale (if small) -> denoise -> deskew ->
    adaptive threshold -> underline removal -> light morphological close.

    Returns a single-channel binary image (black text on white background)
    ready to be passed straight into pytesseract.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale small/low-res scans — Tesseract likes ~300dpi-equivalent text height
    h, w = gray.shape[:2]
    if max(h, w) < 2000:
        scale = 2000 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.fastNlMeansDenoising(gray, h=10)

    # Rough binary estimate just to measure skew angle
    _, rough_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(rough_bin > 0))
    angle = 0.0
    if coords.shape[0] > 10:
        rect_angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + rect_angle) if rect_angle < -45 else -rect_angle
    if abs(angle) > 0.1:
        hh, ww = gray.shape[:2]
        M = cv2.getRotationMatrix2D((ww // 2, hh // 2), angle, 1.0)
        gray = cv2.warpAffine(gray, M, (ww, hh), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)

    # Adaptive threshold copes with scan shadow/lighting better than global Otsu
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY_INV, 31, 15)

    binary = _remove_underlines(binary)

    # Light close to reconnect strokes broken by thresholding
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    ocr_ready = cv2.bitwise_not(binary)  # Tesseract wants black text on white
    return ocr_ready


def process_single_image(img, file_ext='png'):
    """Run bounding-box OCR on a single OpenCV image array.
    Returns (annotated_img_bytes, extracted_text, stats_dict).
    """
    h_img, w_img = img.shape[:2]

    ocr_ready = preprocess_for_ocr(img)
    annotated_img = cv2.cvtColor(ocr_ready, cv2.COLOR_GRAY2BGR)

    ocr_data = pytesseract.image_to_data(ocr_ready, config=TESS_CONFIG,
                                          output_type=pytesseract.Output.DICT)

    detected_boxes = 0
    total_conf = 0.0
    conf_count = 0
    words_detected = []

    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        text = ocr_data['text'][i].strip()
        conf = int(ocr_data['conf'][i])
        if text != '' and conf > 25:
            x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i],
                          ocr_data['width'][i], ocr_data['height'][i])
            cv2.rectangle(annotated_img, (x, y), (x + w, y + h), (230, 81, 0), 2)
            label_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            label_w, label_h = label_size
            label_y1 = max(y - label_h - 4, 0)
            label_y2 = max(y, label_h + 4)
            cv2.rectangle(annotated_img, (x, label_y1), (x + label_w + 6, label_y2), (230, 81, 0), -1)
            cv2.putText(annotated_img, text, (x + 3, label_y2 - 3),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
            detected_boxes += 1
            total_conf += conf
            conf_count += 1
            words_detected.append(text)

    extracted_text = pytesseract.image_to_string(ocr_ready, config=TESS_CONFIG).strip()
    avg_confidence = round(total_conf / conf_count, 1) if conf_count > 0 else 0.0

    encode_ext = f'.{file_ext}' if file_ext in ['jpg', 'jpeg', 'png', 'webp'] else '.png'
    is_success, buffer = cv2.imencode(encode_ext, annotated_img)
    img_bytes = buffer.tobytes() if is_success else cv2.imencode('.png', annotated_img)[1].tobytes()

    stats = {
        'detected_regions': detected_boxes,
        'word_count': len(words_detected) if words_detected else len(extracted_text.split()),
        'avg_confidence': avg_confidence,
        'image_size': f'{w_img}x{h_img} px'
    }
    return img_bytes, extracted_text, stats

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_image():
    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
               or request.accept_mimetypes.best == 'application/json')

    # 1. Validate file presence
    if 'image' not in request.files:
        error_msg = 'No file part in request.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 400
        return render_template('index.html', error=error_msg)

    file = request.files['image']

    if file.filename == '':
        error_msg = 'No file selected for upload.'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 400
        return render_template('index.html', error=error_msg)

    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''

    # Route to PDF handler if applicable
    if file_ext == 'pdf':
        if not PDF_SUPPORT:
            error_msg = 'PDF support requires pdf2image and poppler. Please install them.'
            if is_ajax:
                return jsonify({'success': False, 'error': error_msg}), 400
            return render_template('index.html', error=error_msg)
        return _process_pdf(file, is_ajax)

    if not allowed_file(file.filename):
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS | PDF_EXTENSIONS))
        error_msg = f'Unsupported file type. Allowed: {allowed}'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 400
        return render_template('index.html', error=error_msg)

    try:
        # 2. Save original image securely with unique prefix
        unique_id = uuid.uuid4().hex[:8]
        safe_basename = secure_filename(file.filename.rsplit('.', 1)[0]) or 'image'
        filename = f'{unique_id}_{safe_basename}.{file_ext}'
        processed_filename = f'processed_{filename}'

        orig_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        processed_filepath = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)

        file.save(orig_filepath)

        # 3. Read image with OpenCV
        img_np = np.fromfile(orig_filepath, dtype=np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError('Failed to decode image format.')

        h_img, w_img = img.shape[:2]

        # 4. OCR with bounding boxes
        img_bytes, extracted_text, stats = process_single_image(img, file_ext)

        with open(processed_filepath, 'wb') as f:
            f.write(img_bytes)

        result_data = {
            'success': True,
            'file_type': 'image',
            'original_image': url_for('static', filename=f'uploads/{filename}'),
            'processed_image': url_for('static', filename=f'uploads/{processed_filename}'),
            'extracted_text': extracted_text if extracted_text else '(No readable text detected)',
            'stats': stats
        }

        if is_ajax:
            return jsonify(result_data)
        return render_template('index.html', result=result_data)

    except Exception as e:
        error_msg = f'Error processing image: {str(e)}'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 500
        return render_template('index.html', error=error_msg)


def _process_pdf(file, is_ajax):
    """Convert each PDF page to an image, run OCR, return aggregated results."""
    try:
        pdf_bytes = file.read()
        unique_id = uuid.uuid4().hex[:8]
        safe_basename = secure_filename(file.filename.rsplit('.', 1)[0]) or 'document'

        # Convert PDF pages to PIL Images at 200 DPI
        pil_pages = convert_from_bytes(pdf_bytes, dpi=200)

        if not pil_pages:
            raise ValueError('Could not extract any pages from the PDF.')

        pages_result = []
        all_text_parts = []
        total_regions = 0
        total_words = 0
        total_conf_sum = 0.0
        conf_count_total = 0

        for page_idx, pil_img in enumerate(pil_pages):
            # Convert PIL → numpy BGR for OpenCV
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # Save original page
            orig_filename = f'{unique_id}_{safe_basename}_p{page_idx + 1}.png'
            proc_filename = f'processed_{orig_filename}'
            orig_path = os.path.join(app.config['UPLOAD_FOLDER'], orig_filename)
            proc_path = os.path.join(app.config['UPLOAD_FOLDER'], proc_filename)

            cv2.imwrite(orig_path, img)

            img_bytes, page_text, page_stats = process_single_image(img, 'png')

            with open(proc_path, 'wb') as f:
                f.write(img_bytes)

            if page_text:
                all_text_parts.append(f'--- Page {page_idx + 1} ---\n{page_text}')

            total_regions += page_stats['detected_regions']
            total_words += page_stats['word_count']
            total_conf_sum += page_stats['avg_confidence'] * (page_stats['detected_regions'] or 1)
            conf_count_total += (page_stats['detected_regions'] or 1)

            pages_result.append({
                'page': page_idx + 1,
                'original_image': url_for('static', filename=f'uploads/{orig_filename}'),
                'processed_image': url_for('static', filename=f'uploads/{proc_filename}'),
                'text': page_text or '(No readable text on this page)',
                'stats': page_stats
            })

        full_text = '\n\n'.join(all_text_parts) if all_text_parts else '(No readable text detected)'
        avg_conf = round(total_conf_sum / conf_count_total, 1) if conf_count_total > 0 else 0.0
        first_page = pages_result[0]

        result_data = {
            'success': True,
            'file_type': 'pdf',
            'page_count': len(pil_pages),
            # Convenience fields (first page) for backward-compat with image view
            'original_image': first_page['original_image'],
            'processed_image': first_page['processed_image'],
            'extracted_text': full_text,
            'pages': pages_result,
            'stats': {
                'detected_regions': total_regions,
                'word_count': total_words,
                'avg_confidence': avg_conf,
                'image_size': f"{len(pil_pages)} page(s)"
            }
        }

        if is_ajax:
            return jsonify(result_data)
        return render_template('index.html', result=result_data)

    except Exception as e:
        error_msg = f'Error processing PDF: {str(e)}'
        if is_ajax:
            return jsonify({'success': False, 'error': error_msg}), 500
        return render_template('index.html', error=error_msg)

if __name__ == '__main__':
    print("Starting OCR Detection Flask Server on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=True)