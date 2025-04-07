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
            let errorMessage = "Failed to parse server response.";
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
                    message: "Server encountered an error. Please try again with a different image."
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
            
            if (!ok) {
                showAlert(json.error || 'An error occurred during processing', 'danger');
                resetUI();
                return;
            }
            
            progressBar.style.width = "100%";
            progressBar.textContent = "100%";
            
            // Display frames preview
            if (json.results && json.results.length) {
                framesPreviewContainer.style.display = 'block';
                framesPreview.innerHTML = '';
                
                // Create frame preview cards
                json.results.forEach((result, index) => {
                    if (result.frame_path) {
                        const frameCard = document.createElement('div');
                        frameCard.className = 'col-md-3 mb-3';
                        frameCard.innerHTML = `
                            <div class="card">
                                <img src="/uploads/${result.frame_path.split('/').pop()}" class="card-img-top" alt="Frame ${index+1}">
                                <div class="card-body">
                                    <h5 class="card-title">Frame ${index+1}</h5>
                                </div>
                            </div>
                        `;
                        framesPreview.appendChild(frameCard);
                    }
                });
            }
            
            // Display OCR results
            if (json.results && json.results.length) {
                resultsContainer.style.display = 'block';
                ocrResultsContainer.innerHTML = '';
                
                json.results.forEach((result, index) => {
                    if (result.text && result.text.trim()) {
                        const resultCard = document.createElement('div');
                        resultCard.className = 'card mb-3';
                        resultCard.innerHTML = `
                            <div class="card-header bg-info text-white">
                                Frame ${result.frame_number || (index + 1)}
                            </div>
                            <div class="card-body">
                                <pre class="mb-0">${result.text}</pre>
                            </div>
                        `;
                        ocrResultsContainer.appendChild(resultCard);
                    }
                });
                
                if (ocrResultsContainer.children.length === 0) {
                    ocrResultsContainer.innerHTML = `
                        <div class="alert alert-warning">
                            No text was detected in any of the frames. 
                            <br>Try adjusting the image or uploading a different one.
                        </div>
                    `;
                }
                
                exportBtn.style.display = 'block';
            } else {
                resultsContainer.style.display = 'block';
                ocrResultsContainer.innerHTML = `
                    <div class="alert alert-danger">
                        No OCR results were returned. There may have been an error processing the image.
                    </div>
                `;
                exportBtn.style.display = 'none';
            }
        })
        .catch(error => {
            clearInterval(progressInterval);
            console.error('Error:', error);
            showAlert('An error occurred during processing: ' + error.message, 'danger');
            resetUI();
        });
    }

    // Handle file upload
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const file = uploadInput.files[0];
        if (!file) {
            showAlert('Please select a file to upload', 'warning', uploadAlertContainer);
            return;
        }
        
        // Check file type
        const fileType = file.type.toLowerCase();
        const validTypes = ['image/gif', 'image/jpeg', 'image/png', 'image/avif'];
        if (!validTypes.includes(fileType) && !file.name.toLowerCase().endsWith('.gif')) {
            showAlert('Please upload a valid image file (GIF, JPEG, PNG, or AVIF)', 'warning', uploadAlertContainer);
            return;
        }
        
        resetUI();
        uploadAlertContainer.style.display = 'none';
        processingContainer.style.display = 'block';
        progressContainer.style.display = 'block';
        
        const formData = new FormData();
        formData.append('file', file);
        
        // Set up progress tracking
        let progress = 0;
        
        // Start progress animation for upload
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
        progressBar.style.width = "0%";
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(handleFetchResponse)
        .then(({ ok, json }) => {
            clearInterval(progressInterval);
            
            if (!ok) {
                showAlert(json.error || 'An error occurred during upload', 'danger', uploadAlertContainer);
                resetUI();
                return;
            }
            
            // Process the uploaded frames
            processFrames();
        })
        .catch(error => {
            clearInterval(progressInterval);
            console.error('Error:', error);
            showAlert('An error occurred during upload: ' + error.message, 'danger', uploadAlertContainer);
            resetUI();
        });
    });

    // Handle export
    exportBtn.addEventListener('click', function() {
        const format = exportFormatSelect.value;
        
        fetch(`/export?format=${format}`, {
            method: 'GET'
        })
        .then(response => {
            if (!response.ok) {
                return handleFetchResponse(response).then(({ json }) => {
                    throw new Error(json.error || 'Failed to export results');
                });
            }
            return response.blob();
        })
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `ocr_results.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Export failed: ' + error.message, 'danger');
        });
    });

    // Handle cleanup
    cleanupBtn.addEventListener('click', function() {
        fetch('/cleanup', {
            method: 'POST'
        })
        .then(handleFetchResponse)
        .then(({ ok, json }) => {
            if (ok && json.success) {
                showAlert('Temporary files cleaned up successfully', 'success');
                resetUI();
            } else {
                showAlert(json.error || 'Failed to clean up files', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Cleanup failed: ' + error.message, 'danger');
        });
    });

    // Handle diagnostics
    diagnosticsBtn.addEventListener('click', function() {
        fetch('/diagnostics', {
            method: 'GET'
        })
        .then(handleFetchResponse)
        .then(({ ok, json }) => {
            if (!ok) {
                throw new Error(json.error || 'Failed to run diagnostics');
            }
            
            diagnosticsContainer.style.display = 'block';
            diagnosticsContainer.innerHTML = '';
            
            const card = document.createElement('div');
            card.className = 'card mb-3';
            card.innerHTML = `
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">System Diagnostics</h5>
                </div>
                <div class="card-body">
                    <pre class="mb-0">${JSON.stringify(json, null, 2)}</pre>
                </div>
            `;
            diagnosticsContainer.appendChild(card);
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Failed to run diagnostics: ' + error.message, 'danger');
        });
    });
});