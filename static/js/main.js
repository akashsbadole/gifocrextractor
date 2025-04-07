/**
 * Enhanced error handling for API responses
 * This function handles both successful JSON responses and error cases,
 * including when the server returns HTML instead of JSON.
 */
function handleFetchResponse(response) {
    return response.text().then(text => {
        let json;
        try {
            json = JSON.parse(text);
            return { ok: response.ok, json };
        } catch (e) {
            console.error("Failed to parse response as JSON:", e);
            console.log("Response text:", text);
            
            // If the response contains HTML (likely an error page), extract any message
            let errorMessage = "Failed to parse server response. See console for details.";
            if (text.includes("<html") && text.includes("Error")) {
                // Simple extraction of error message from HTML
                const errorMatch = text.match(/<h1[^>]*>(.*?)<\/h1>/i);
                if (errorMatch && errorMatch[1]) {
                    errorMessage = errorMatch[1].replace(/<[^>]*>/g, '').trim();
                }
            }
            
            return { 
                ok: false, 
                json: {
                    success: false,
                    error: errorMessage,
                    message: "Server encountered an error. Please try again with a different image.",
                    results: []
                } 
            };
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const uploadForm = document.getElementById('upload-form');
    const uploadInput = document.getElementById('file-upload');
    const uploadBtn = document.getElementById('upload-btn');
    const processingContainer = document.getElementById('processing-container');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const framesPreviewContainer = document.getElementById('frames-preview-container');
    const framesPreview = document.getElementById('frames-preview');
    const resultsContainer = document.getElementById('results-container');
    const ocrResultsContainer = document.getElementById('ocr-results-container');
    const exportBtn = document.getElementById('export-btn');
    const exportFormatSelect = document.getElementById('export-format');
    const globalAlertContainer = document.getElementById('alert-container');
    const uploadAlertContainer = document.getElementById('upload-alert');
    const cleanupBtn = document.getElementById('cleanup-btn');
    const diagnosticsBtn = document.getElementById('diagnostics-btn');
    const diagnosticsContainer = document.getElementById('diagnostics-container');

    // Function to show alerts
    function showAlert(message, type, container = globalAlertContainer) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        container.innerHTML = '';
        container.appendChild(alertDiv);
        container.style.display = 'block';
    }

    // Function to reset UI
    function resetUI() {
        progressBar.style.width = '0%';
        progressBar.textContent = '';
        processingContainer.style.display = 'none';
        progressContainer.style.display = 'none';
        framesPreviewContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
        diagnosticsContainer.style.display = 'none';
        framesPreview.innerHTML = '';
        ocrResultsContainer.innerHTML = '';
    }

    // Process frames when upload is complete
    function processFrames() {
        processingContainer.style.display = 'block';
        progressContainer.style.display = 'block';
        
        let progress = 0;
        
        // Update progress bar
        const progressInterval = setInterval(() => {
            progress += 5;
            // Cap at 90% - the last 10% will happen on completion
            if (progress > 90) {
                clearInterval(progressInterval);
                return;
            }
            progressBar.style.width = progress + "%";
            progressBar.textContent = progress + "%";
        }, 300);
        
        fetch('/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({}) // Session ID is handled by the server
        })
        .then(handleFetchResponse)
        .then(({ ok, json }) => {
            clearInterval(progressInterval);
            
            progressBar.style.width = "100%";
            progressBar.textContent = "100%";
            
            // Check for error messages in the response regardless of HTTP status
            if (!json.success) {
                showAlert(json.message || json.error || 'An error occurred during processing', 'danger');
                // Still display any results that might be present, even with errors
                if (!json.results || !json.results.length) {
                    resetUI();
                    return;
                }
            }
            
            // Display frames preview
            if (json.frames && json.frames.length) {
                framesPreviewContainer.style.display = 'block';
                framesPreview.innerHTML = '';
                
                json.frames.forEach((frame, index) => {
                    const frameCard = document.createElement('div');
                    frameCard.className = 'col-md-3 mb-3';
                    frameCard.innerHTML = `
                        <div class="card">
                            <img src="${frame}" class="card-img-top" alt="Frame ${index+1}">
                            <div class="card-body">
                                <h5 class="card-title">Frame ${index+1}</h5>
                            </div>
                        </div>
                    `;
                    framesPreview.appendChild(frameCard);
                });
            }
            
            // Display OCR results if they exist, regardless of success flag
            if (json.results) {
                resultsContainer.style.display = 'block';
                ocrResultsContainer.innerHTML = '';
                
                // Check if results is empty
                if (json.results.length === 0) {
                    const noResultsCard = document.createElement('div');
                    noResultsCard.className = 'card mb-3';
                    noResultsCard.innerHTML = `
                        <div class="card-body text-center">
                            <p>No text was detected in the image. Please try a different image.</p>
                        </div>
                    `;
                    ocrResultsContainer.appendChild(noResultsCard);
                } else {
                    // Process and display the results
                    json.results.forEach((result) => {
                        if (result.text && result.text.trim()) {
                            const resultCard = document.createElement('div');
                            resultCard.className = 'card mb-3';
                            
                            // If the text starts with "Error:", display it as an error message
                            const isError = result.text.startsWith("Error:") || 
                                          result.text.includes("Error during OCR processing");
                            
                            resultCard.innerHTML = `
                                <div class="card-header ${isError ? 'bg-danger' : 'bg-info'} text-white">
                                    Frame ${result.frame_number}
                                </div>
                                <div class="card-body ${isError ? 'bg-light' : ''}">
                                    <pre class="mb-0">${result.text}</pre>
                                </div>
                            `;
                            ocrResultsContainer.appendChild(resultCard);
                        }
                    });
                }
                
                if (ocrResultsContainer.children.length === 0) {
                    const noTextCard = document.createElement('div');
                    noTextCard.className = 'card mb-3';
                    noTextCard.innerHTML = `
                        <div class="card-body text-center">
                            <p>No text was detected in any frame. Please try a different image.</p>
                        </div>
                    `;
                    ocrResultsContainer.appendChild(noTextCard);
                } else {
                    exportBtn.disabled = false;
                }
            } else {
                showAlert('No OCR results were returned from the server', 'warning');
            }
            
            setTimeout(() => {
                processingContainer.style.display = 'none';
            }, 1000);
        })
        .catch(error => {
            clearInterval(progressInterval);
            console.error('Error processing frames:', error);
            showAlert('Error processing frames: ' + error.message, 'danger');
            resetUI();
        });
    }

    // Add event listener for upload form submission
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Reset UI first
            resetUI();
            globalAlertContainer.innerHTML = '';
            uploadAlertContainer.innerHTML = '';
            
            // Validate file
            const file = uploadInput.files[0];
            if (!file) {
                showAlert('Please select a file to upload', 'warning', uploadAlertContainer);
                return;
            }
            
            // Check file extension
            const fileExtension = file.name.split('.').pop().toLowerCase();
            if (!['gif', 'jpg', 'jpeg', 'png', 'avif'].includes(fileExtension)) {
                showAlert('Only GIF, JPEG, JPG, PNG, and AVIF files are allowed', 'warning', uploadAlertContainer);
                return;
            }
            
            // Check file size (max 16MB)
            if (file.size > 16 * 1024 * 1024) {
                showAlert('File size exceeds the 16MB limit', 'warning', uploadAlertContainer);
                return;
            }
            
            // Create FormData and append file
            const formData = new FormData();
            formData.append('file', file);
            
            // Set button to loading state
            uploadBtn.disabled = true;
            uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uploading...';
            
            // Upload file
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(handleFetchResponse)
            .then(({ ok, json }) => {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = 'Upload';
                
                if (!ok || !json.success) {
                    showAlert(json.error || 'Upload failed. Please try again.', 'danger', uploadAlertContainer);
                    return;
                }
                
                // Show success message with frame count
                const framesStr = json.frames_count === 1 ? 'frame' : 'frames';
                showAlert(`File uploaded successfully! Extracted ${json.frames_count} ${framesStr}.`, 'success');
                
                // Process frames
                processFrames();
            })
            .catch(error => {
                uploadBtn.disabled = false;
                uploadBtn.innerHTML = 'Upload';
                console.error('Error uploading file:', error);
                showAlert('Error uploading file: ' + error.message, 'danger', uploadAlertContainer);
            });
        });
    }

    // Add event listener for export button
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            const format = exportFormatSelect.value;
            window.location.href = `/export?format=${format}`;
        });
    }

    // Add event listener for cleanup button
    if (cleanupBtn) {
        cleanupBtn.addEventListener('click', function() {
            fetch('/cleanup', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                resetUI();
                showAlert('Session cleared successfully', 'success');
                exportBtn.disabled = true;
                
                // Reset file input
                uploadInput.value = '';
            })
            .catch(error => {
                console.error('Error clearing session:', error);
                showAlert('Error clearing session: ' + error.message, 'danger');
            });
        });
    }

    // Add event listener for diagnostics button
    if (diagnosticsBtn) {
        diagnosticsBtn.addEventListener('click', function() {
            fetch('/diagnostics')
            .then(response => response.json())
            .then(data => {
                diagnosticsContainer.style.display = 'block';
                diagnosticsContainer.innerHTML = `
                    <div class="card my-4">
                        <div class="card-header bg-secondary text-white">
                            System Diagnostics
                        </div>
                        <div class="card-body">
                            <h5>System Information</h5>
                            <pre>${JSON.stringify(data.diagnostics.system, null, 2)}</pre>
                            
                            <h5>Tesseract OCR</h5>
                            <pre>${JSON.stringify(data.diagnostics.tesseract, null, 2)}</pre>
                            
                            <h5>Image Libraries</h5>
                            <pre>${JSON.stringify(data.diagnostics.image_libs, null, 2)}</pre>
                            
                            <h5>Upload Directory</h5>
                            <pre>${JSON.stringify(data.diagnostics.upload_dir, null, 2)}</pre>
                            
                            <h5>Test OCR</h5>
                            <pre>${JSON.stringify(data.test_ocr, null, 2)}</pre>
                        </div>
                    </div>
                `;
            })
            .catch(error => {
                console.error('Error fetching diagnostics:', error);
                showAlert('Error fetching diagnostics: ' + error.message, 'danger');
            });
        });
    }

    // Add drag and drop functionality to the drop zone
    const dropArea = document.getElementById('drop-area');
    if (dropArea) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, preventDefaults, false);
        });
        
        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropArea.addEventListener(eventName, highlight, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropArea.addEventListener(eventName, unhighlight, false);
        });
        
        function highlight() {
            dropArea.classList.add('highlight');
        }
        
        function unhighlight() {
            dropArea.classList.remove('highlight');
        }
        
        dropArea.addEventListener('drop', handleDrop, false);
        
        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            
            if (files.length > 0) {
                uploadInput.files = files;
                uploadForm.dispatchEvent(new Event('submit'));
            }
        }
    }
});
