document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const dropZonePrompt = document.getElementById('drop-zone-prompt');
    const filePreviewContainer = document.getElementById('file-preview-container');
    // filePreviewImg declared below alongside pdfThumbIcon
    const fileNameSpan = document.getElementById('file-name');
    const fileSizeSpan = document.getElementById('file-size');
    const btnRemoveFile = document.getElementById('btn-remove-file');
    const btnSubmit = document.getElementById('btn-submit');
    const ocrForm = document.getElementById('ocr-form');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const resultsSection = document.getElementById('results-section');

    // Stats Elements
    const statRegions = document.getElementById('stat-regions');
    const statWords = document.getElementById('stat-words');
    const statConfidence = document.getElementById('stat-confidence');
    const statDimensions = document.getElementById('stat-dimensions');

    // Result Elements
    const resultProcessedImg = document.getElementById('result-processed-img');
    const resultOriginalImg = document.getElementById('result-original-img');
    const extractedTextArea = document.getElementById('extracted-text-area');
    const btnToggleView = document.getElementById('btn-toggle-view');
    const btnCopy = document.getElementById('btn-copy');
    const btnDownload = document.getElementById('btn-download');

    // PDF elements
    const pdfPageNav = document.getElementById('pdf-page-nav');
    const btnPrevPage = document.getElementById('btn-prev-page');
    const btnNextPage = document.getElementById('btn-next-page');
    const pdfPageLabel = document.getElementById('pdf-page-label');
    const loadingTitle = document.getElementById('loading-title');
    const loadingSubtitle = document.getElementById('loading-subtitle');
    const statDimensionsLabel = document.getElementById('stat-dimensions-label');
    const filePreviewImg = document.getElementById('file-preview-img');
    const pdfThumbIcon = document.getElementById('pdf-thumb-icon');

    let currentFile = null;
    let pdfPages = [];        // array of page objects from server
    let currentPageIdx = 0;  // 0-based index into pdfPages

    // Helper: Format bytes to KB/MB
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }

    // Helper: Display Error
    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.classList.remove('hidden');
    }

    function clearError() {
        errorBanner.classList.add('hidden');
        errorMessage.textContent = '';
    }

    // File Selection Handler
    function handleFile(file) {
        clearError();
        if (!file) return;

        const isPDF = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
        const allowedImageTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp', 'image/bmp'];

        if (!isPDF && !allowedImageTypes.includes(file.type)) {
            showError('Invalid file type. Please select a PNG, JPG, WEBP, BMP image or a PDF document.');
            resetFileInput();
            return;
        }

        currentFile = file;
        fileNameSpan.textContent = file.name;
        fileSizeSpan.textContent = formatBytes(file.size);

        if (isPDF) {
            // Show PDF icon, hide image preview
            filePreviewImg.src = '';
            filePreviewImg.classList.add('hidden');
            pdfThumbIcon.classList.remove('hidden');
            if (window.lucide) lucide.createIcons();
            dropZonePrompt.classList.add('hidden');
            filePreviewContainer.classList.remove('hidden');
            btnSubmit.disabled = false;

            // Update loading text
            loadingTitle.textContent = 'Processing PDF & Detecting Text...';
            loadingSubtitle.textContent = 'Converting pages and running PyTesseract engine';
        } else {
            // Show image thumbnail
            filePreviewImg.classList.remove('hidden');
            pdfThumbIcon.classList.add('hidden');

            loadingTitle.textContent = 'Analyzing & Detecting Text...';
            loadingSubtitle.textContent = 'Running OpenCV contours & PyTesseract engine';

            const reader = new FileReader();
            reader.onload = (e) => {
                filePreviewImg.src = e.target.result;
                dropZonePrompt.classList.add('hidden');
                filePreviewContainer.classList.remove('hidden');
                btnSubmit.disabled = false;
            };
            reader.readAsDataURL(file);
        }
    }

    function resetFileInput() {
        fileInput.value = '';
        currentFile = null;
        pdfPages = [];
        currentPageIdx = 0;
        filePreviewImg.src = '';
        filePreviewImg.classList.remove('hidden');
        pdfThumbIcon.classList.add('hidden');
        dropZonePrompt.classList.remove('hidden');
        filePreviewContainer.classList.add('hidden');
        btnSubmit.disabled = true;
    }

    // Event Listeners for File Input & Drag and Drop
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    btnRemoveFile.addEventListener('click', (e) => {
        e.stopPropagation();
        resetFileInput();
    });

    // Drag and Drop Events
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            handleFile(files[0]);
        }
    });

    // Form Submission Handler (AJAX)
    ocrForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        clearError();

        if (!currentFile && (!fileInput.files || fileInput.files.length === 0)) {
            showError('Please select an image file first.');
            return;
        }

        const formData = new FormData();
        formData.append('image', currentFile || fileInput.files[0]);

        // Show loader
        loadingOverlay.classList.remove('hidden');
        btnSubmit.disabled = true;

        try {
            const response = await fetch('/process', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to process file');
            }

            // Render stats
            statRegions.textContent = data.stats.detected_regions;
            statWords.textContent = data.stats.word_count;
            statConfidence.textContent = `${data.stats.avg_confidence}%`;
            statDimensions.textContent = data.stats.image_size;

            if (data.file_type === 'pdf') {
                // ---- PDF multi-page handling ----
                pdfPages = data.pages;
                currentPageIdx = 0;
                statDimensionsLabel.textContent = 'Pages Processed';

                // Show page navigator
                pdfPageNav.classList.remove('hidden');
                renderPdfPage(currentPageIdx, data.pages, 'processed');

                // Full merged text
                extractedTextArea.value = data.extracted_text;
            } else {
                // ---- Image handling ----
                pdfPages = [];
                statDimensionsLabel.textContent = 'Image Dimensions';
                pdfPageNav.classList.add('hidden');

                resultProcessedImg.src = data.processed_image;
                resultOriginalImg.src = data.original_image;
                extractedTextArea.value = data.extracted_text;
            }

            // Show results workspace
            resultsSection.classList.remove('hidden');

            // Re-initialize view toggle state
            btnToggleView.setAttribute('data-mode', 'processed');
            btnToggleView.innerHTML = `<i data-lucide="layers"></i> Show Original`;
            resultProcessedImg.classList.remove('hidden');
            resultOriginalImg.classList.add('hidden');

            if (window.lucide) {
                lucide.createIcons();
            }

            // Smooth scroll to results
            resultsSection.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            showError(err.message || 'An error occurred while processing the image.');
        } finally {
            loadingOverlay.classList.add('hidden');
            btnSubmit.disabled = false;
        }
    });

    // --- PDF Page Navigator ---
    function renderPdfPage(idx, pages, viewMode) {
        const page = pages[idx];
        if (!page) return;

        const isProcessed = viewMode !== 'original';
        resultProcessedImg.src = page.processed_image;
        resultOriginalImg.src = page.original_image;
        btnToggleView.setAttribute('data-mode', 'processed');
        btnToggleView.innerHTML = `<i data-lucide="layers"></i> Show Original`;
        resultProcessedImg.classList.remove('hidden');
        resultOriginalImg.classList.add('hidden');

        pdfPageLabel.textContent = `Page ${idx + 1} of ${pages.length}`;
        btnPrevPage.disabled = idx === 0;
        btnNextPage.disabled = idx === pages.length - 1;

        // Show this page's extracted text
        extractedTextArea.value = page.text || '';

        if (window.lucide) lucide.createIcons();
    }

    if (btnPrevPage) {
        btnPrevPage.addEventListener('click', () => {
            if (currentPageIdx > 0) {
                currentPageIdx--;
                renderPdfPage(currentPageIdx, pdfPages, btnToggleView.getAttribute('data-mode'));
            }
        });
    }

    if (btnNextPage) {
        btnNextPage.addEventListener('click', () => {
            if (currentPageIdx < pdfPages.length - 1) {
                currentPageIdx++;
                renderPdfPage(currentPageIdx, pdfPages, btnToggleView.getAttribute('data-mode'));
            }
        });
    }

    // Toggle View Button (Processed Bounding Box vs Original Image)
    if (btnToggleView) {
        btnToggleView.addEventListener('click', () => {
            const currentMode = btnToggleView.getAttribute('data-mode');
            if (currentMode === 'processed') {
                btnToggleView.setAttribute('data-mode', 'original');
                btnToggleView.innerHTML = `<i data-lucide="eye"></i> Show Processed Box`;
                resultProcessedImg.classList.add('hidden');
                resultOriginalImg.classList.remove('hidden');
            } else {
                btnToggleView.setAttribute('data-mode', 'processed');
                btnToggleView.innerHTML = `<i data-lucide="layers"></i> Show Original`;
                resultProcessedImg.classList.remove('hidden');
                resultOriginalImg.classList.add('hidden');
            }
            if (window.lucide) {
                lucide.createIcons();
            }
        });
    }

    // Copy to Clipboard Action
    if (btnCopy) {
        btnCopy.addEventListener('click', async () => {
            const textToCopy = extractedTextArea.value;
            if (!textToCopy) return;

            try {
                await navigator.clipboard.writeText(textToCopy);
                const originalHtml = btnCopy.innerHTML;
                btnCopy.innerHTML = `<i data-lucide="check"></i> Copied!`;
                btnCopy.style.background = 'var(--accent-success)';
                btnCopy.style.borderColor = 'var(--accent-success)';
                btnCopy.style.color = '#fff';

                if (window.lucide) lucide.createIcons();

                setTimeout(() => {
                    btnCopy.innerHTML = originalHtml;
                    btnCopy.style.background = '';
                    btnCopy.style.borderColor = '';
                    btnCopy.style.color = '';
                    if (window.lucide) lucide.createIcons();
                }, 2000);
            } catch (err) {
                showError('Could not copy text to clipboard.');
            }
        });
    }

    // Download as .txt file Action
    if (btnDownload) {
        btnDownload.addEventListener('click', () => {
            const text = extractedTextArea.value;
            if (!text) return;

            const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `ocr_extracted_${Date.now()}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }
});
