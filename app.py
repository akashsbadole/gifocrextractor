import os
import logging
import uuid
import tempfile
import sys
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from utils.image_processor import extract_frames_from_image
from utils.ocr_engine import perform_ocr_on_frames
from utils.export_util import export_to_excel, export_to_csv
from utils.diagnostics import run_diagnostics

# Configure detailed logging for debugging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

# Set specific logger levels
logging.getLogger('PIL').setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure upload settings
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ALLOWED_EXTENSIONS = {'gif', 'jpg', 'jpeg', 'png', 'avif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['DEBUG_MODE'] = os.environ.get('DEBUG_MODE', 'True').lower() in ('true', '1', 't')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Run diagnostics on startup
try:
    logging.info("Running system diagnostics on startup...")
    diagnostics_results = run_diagnostics(app.config['UPLOAD_FOLDER'])
    app.config['DIAGNOSTICS_RESULTS'] = diagnostics_results
    
    # Check for critical issues
    if not diagnostics_results['tesseract']['installed']:
        logging.critical(f"Tesseract OCR is not installed or not working properly: {diagnostics_results['tesseract'].get('error', 'Unknown error')}")
        
    if 'upload_dir' in diagnostics_results and not (diagnostics_results['upload_dir']['readable'] and diagnostics_results['upload_dir']['writable']):
        logging.critical(f"Upload directory has permission issues: {app.config['UPLOAD_FOLDER']}")
        
except Exception as diag_err:
    logging.error(f"Error running diagnostics: {str(diag_err)}")
    app.config['DIAGNOSTICS_RESULTS'] = {'error': str(diag_err)}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logging.warning("Upload attempt with no file part")
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        logging.warning("Upload attempt with empty filename")
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        logging.warning(f"Upload attempt with invalid file type: {file.filename}")
        return jsonify({'error': 'Only GIF, JPEG, JPG, PNG, and AVIF files are allowed'}), 400
    
    try:
        # Check file size before reading it fully
        file_size_bytes = request.content_length
        if file_size_bytes:
            file_size_mb = file_size_bytes / (1024 * 1024)
            if file_size_mb > 16:
                logging.warning(f"Upload attempt with file too large: {file_size_mb:.2f}MB")
                return jsonify({
                    'error': f'File too large ({file_size_mb:.2f}MB). Maximum size is 16MB'
                }), 413
        
        # Clean up previous session
        if 'session_id' in session:
            cleanup()
        
        # Create unique ID for this upload session
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        
        # Create temporary directories for this session
        frames_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'image_frames_{session_id}')
        os.makedirs(frames_dir, exist_ok=True)
        
        # Save the uploaded file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{session_id}_{filename}')
        
        logging.info(f"Saving uploaded file: {filename} for session {session_id}")
        file.save(file_path)
        
        if not os.path.exists(file_path):
            logging.error(f"Failed to save uploaded file to {file_path}")
            return jsonify({'error': 'Failed to save uploaded file'}), 500
        
        session['original_filename'] = filename
        session['file_path'] = file_path
        
        # Check if it's a valid image file in the supported formats
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                supported_formats = ['GIF', 'JPEG', 'PNG', 'AVIF']
                if img.format not in supported_formats:
                    logging.warning(f"File extension suggests supported format but PIL detects {img.format}")
                    return jsonify({'error': f'The file format {img.format} is not supported. Please use GIF, JPEG, PNG, or AVIF.'}), 400
                
                frame_count = getattr(img, 'n_frames', 1)
                logging.info(f"Valid {img.format} image detected: {img.size}, mode: {img.mode}, {frame_count} frames")
        except Exception as img_err:
            logging.error(f"Error validating image: {str(img_err)}")
            return jsonify({'error': 'The file is not a valid image. Please use GIF, JPEG, PNG, or AVIF formats.'}), 400
        
        # Extract frames
        try:
            frames_paths = extract_frames_from_image(file_path, frames_dir)
            
            if not frames_paths:
                logging.error("No frames were extracted from the image")
                return jsonify({
                    'error': 'Could not extract any frames from the image. The file may be corrupted or empty.'
                }), 400
                
            session['frames_paths'] = frames_paths
            
            logging.info(f"Successfully processed {filename}. Extracted {len(frames_paths)} frames.")
            
            # Return the frames for preview
            return jsonify({
                'success': True,
                'message': f'Successfully processed image with {len(frames_paths)} frames',
                'frames_count': len(frames_paths),
                'session_id': session_id
            })
                
        except Exception as extract_err:
            logging.error(f"Error extracting frames: {str(extract_err)}")
            return jsonify({
                'error': 'Error extracting frames from the image. The file may be corrupted.'
            }), 500
    
    except Exception as e:
        logging.error(f"Unexpected error during file upload: {str(e)}")
        return jsonify({
            'error': 'An unexpected error occurred while uploading the file. Please try again.'
        }), 500

@app.route('/process', methods=['POST'])
def process_frames():
    try:
        if 'session_id' not in session or 'frames_paths' not in session:
            logging.warning("Attempted to process frames without an active session")
            return jsonify({
                'success': False,
                'message': 'No active image processing session',
                'results': []
            }), 200  # Return 200 with error message for better client handling
        
        frames_paths = session['frames_paths']
        session_id = session['session_id']
        
        if not frames_paths:
            logging.warning(f"No frames found for session {session_id}")
            return jsonify({
                'success': False,
                'message': 'No frames were extracted from the image',
                'results': []
            }), 200  # Return 200 with error message
            
        logging.info(f"Starting OCR processing for session {session_id} with {len(frames_paths)} frames")
        
        # Validate the existence of frame files before processing
        missing_frames = []
        for i, frame_path in enumerate(frames_paths):
            if not os.path.exists(frame_path):
                missing_frames.append((i+1, frame_path))
        
        if missing_frames:
            logging.error(f"Found {len(missing_frames)} missing frame files: {missing_frames[:5]}")
            # We'll continue processing even with missing frames
        
        # Check Tesseract availability before processing
        try:
            from utils.ocr_engine import check_tesseract
            tesseract_available = check_tesseract()
            if not tesseract_available:
                logging.error("Tesseract OCR not available, cannot proceed with OCR")
                return jsonify({
                    'success': False,
                    'message': 'OCR engine (Tesseract) is not properly installed or configured. Please contact support.',
                    'results': []
                }), 200  # Return 200 with error message
            
            # Log available disk space
            import shutil
            stat = shutil.disk_usage(app.config['UPLOAD_FOLDER'])
            free_space_mb = stat.free / (1024 * 1024)
            logging.info(f"Available disk space: {free_space_mb:.2f}MB")
            
            if free_space_mb < 50:  # Less than 50MB free
                logging.warning(f"Low disk space: {free_space_mb:.2f}MB free")
        except Exception as check_err:
            logging.error(f"Error checking OCR prerequisites: {str(check_err)}")
        
        # Initialize ocr_results to empty list to ensure we always have something to return
        ocr_results = []
        
        # Perform OCR on each frame with improved error handling
        try:
            # Check if we need to get system diagnostics first
            if app.config.get('DEBUG_MODE', False) and not app.config.get('OCR_CHECKED', False):
                try:
                    # Do a quick diagnostic check of OCR system
                    from utils.diagnostics import check_tesseract_installation
                    tesseract_info = check_tesseract_installation()
                    app.config['OCR_CHECKED'] = True
                    
                    if not tesseract_info.get('installed', False):
                        logging.critical(f"Tesseract OCR not properly installed: {tesseract_info.get('error', 'Unknown reason')}")
                        return jsonify({
                            'success': False,
                            'message': 'The OCR engine is not properly installed on the server.',
                            'details': tesseract_info.get('error', 'Unknown installation issue'),
                            'results': []
                        }), 200  # Return 200 with error message
                except Exception as diag_err:
                    logging.error(f"Error checking Tesseract: {str(diag_err)}")
            
            # Limit the number of frames we process to avoid timeouts
            max_frames = min(len(frames_paths), 30)  # Process at most 30 frames
            if len(frames_paths) > max_frames:
                logging.warning(f"Limiting OCR processing to {max_frames} frames out of {len(frames_paths)} for performance")
                frames_to_process = frames_paths[:max_frames]
            else:
                frames_to_process = frames_paths
                
            # Run OCR with proper error handling
            try:
                ocr_results = perform_ocr_on_frames(frames_to_process)
                
                # If we limited the frames, add a message to the results
                if len(frames_paths) > max_frames:
                    for idx in range(max_frames, len(frames_paths)):
                        ocr_results.append({
                            'frame_number': idx + 1,
                            'frame_path': frames_paths[idx],
                            'text': "(Frame skipped to improve performance)"
                        })
                        
                # Ensure ocr_results is never None
                if ocr_results is None:
                    ocr_results = []
                    logging.warning("OCR engine returned None instead of results list")
                
            except Exception as ocr_err:
                error_msg = str(ocr_err)
                logging.error(f"Exception during OCR processing: {error_msg}", exc_info=True)
                
                # Recover gracefully - provide empty results rather than failing with 500 error
                ocr_results = []
                
                # Add a message for the user about the error
                for idx, frame_path in enumerate(frames_to_process):
                    ocr_results.append({
                        'frame_number': idx + 1,
                        'frame_path': frame_path,
                        'text': "Error during OCR processing. Please try a different image."
                    })
                
                logging.info("Recovered from OCR error by creating placeholder results")
            
        except Exception as ocr_err:
            # This is a fallback for any other error that might occur
            error_msg = str(ocr_err)
            logging.error(f"Unhandled exception during processing: {error_msg}", exc_info=True)
            
            # Return a user-friendly message
            ocr_results = [{
                'frame_number': 1,
                'frame_path': frames_paths[0] if frames_paths else '',
                'text': "Error occurred during processing. Please try again with a different image."
            }]
            
            # Always return a 200 response with JSON content
            return jsonify({
                'success': False,
                'message': 'An error occurred during OCR processing.',
                'results': ocr_results
            }), 200
        
        # Check if we got any results
        if len(ocr_results) == 0:
            logging.warning("OCR processing returned no results")
            return jsonify({
                'success': False,
                'message': 'OCR processing did not return any results. Please try a different image.',
                'suggestion': 'Try an image with clearer text content.',
                'results': []
            }), 200  # Return 200 with error message
        
        # Count successful extractions vs errors
        error_count = sum(1 for result in ocr_results if result.get('text', '').startswith('Error:'))
        empty_count = sum(1 for result in ocr_results if not result.get('text') or result.get('text') == 'No text detected')
        success_count = len(ocr_results) - error_count - empty_count
        
        # Log detailed statistics
        logging.info(f"OCR results statistics: Total frames: {len(ocr_results)}, " +
                     f"With text: {success_count}, Empty: {empty_count}, Errors: {error_count}")
        
        # Store results in session
        session['ocr_results'] = ocr_results
        
        # Determine if overall process was successful
        if success_count > 0:
            logging.info(f"OCR processing complete. Found text in {success_count} frames, errors in {error_count} frames")
            return jsonify({
                'success': True,
                'message': f'OCR processing complete. Found text in {success_count} frames.',
                'results': ocr_results
            })
        elif error_count > 0:
            # If we have errors but no successes, still return a 200 with the error details in results
            logging.warning(f"OCR completed with {error_count} errors and no text found")
            return jsonify({
                'success': True,
                'message': f'OCR processing complete, but encountered errors in all {error_count} frames. No text was found.',
                'results': ocr_results
            })
        else:
            logging.warning("OCR completed but no text was found in any frame")
            return jsonify({
                'success': True,
                'message': 'OCR processing complete, but no text was found in any frame.',
                'results': ocr_results
            })
    
    except Exception as e:
        logging.error(f"Error in OCR processing: {str(e)}", exc_info=True)
        # Return a more user-friendly error message
        return jsonify({
            'success': False,
            'error': f'Error in OCR processing: {str(e)}. Please try again with a different image.'
        }), 500

@app.route('/export', methods=['GET', 'POST'])
def export_results():
    # Check if we have OCR results to export
    if 'session_id' not in session:
        logging.error("No session_id in session")
        return jsonify({'error': 'No active session found. Please process an image first.'}), 400
        
    if 'ocr_results' not in session:
        logging.error("No ocr_results in session")
        return jsonify({'error': 'No OCR results to export. Please process an image first.'}), 400
    
    # Log session data for debugging
    logging.info(f"Export request with session_id: {session.get('session_id')}")
    logging.info(f"OCR results count: {len(session.get('ocr_results', []))}")
    
    # Handle both GET and POST methods
    if request.method == 'GET':
        export_format = request.args.get('format', 'excel')
    else:
        export_format = request.form.get('format', 'excel')
    
    logging.info(f"Requested export format: {export_format}")
        
    # Get the original filename or use a default
    original_filename = session.get('original_filename', 'ocr_results')
    base_filename = original_filename.rsplit('.', 1)[0]
    
    # Create timestamp to ensure unique filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Get OCR results from session
    ocr_results = session.get('ocr_results', [])
    
    try:
        # Create export directory if it doesn't exist
        export_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        if export_format.lower() == 'excel':
            export_path = os.path.join(export_dir, f'{base_filename}_{timestamp}_ocr.xlsx')
            export_to_excel(ocr_results, export_path)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            download_filename = f'{base_filename}_ocr.xlsx'
        else:  # csv
            export_path = os.path.join(export_dir, f'{base_filename}_{timestamp}_ocr.csv')
            export_to_csv(ocr_results, export_path)
            mimetype = 'text/csv'
            download_filename = f'{base_filename}_ocr.csv'
        
        logging.info(f"Sending exported file: {export_path}")
        
        # Check if file exists before sending
        if not os.path.exists(export_path):
            logging.error(f"Export file not found: {export_path}")
            return jsonify({'error': 'Failed to create export file'}), 500
            
        # Get file size for logging
        file_size = os.path.getsize(export_path)
        logging.info(f"Export file size: {file_size} bytes")
        
        return send_file(
            export_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=mimetype
        )
    
    except Exception as e:
        logging.error(f"Error exporting results: {str(e)}", exc_info=True)
        
        # Create a more user-friendly error response
        error_message = str(e)
        if "NotImplementedError" in error_message:
            error_message = "Export format not supported. Please try a different format."
        elif "PermissionError" in error_message:
            error_message = "Permission error when saving file. Please try again."
        elif "No such file or directory" in error_message:
            error_message = "Directory not found. Please make sure the upload directory exists."
            
        return jsonify({
            'success': False,
            'error': f'Error exporting results: {error_message}'
        }), 500

@app.route('/cleanup', methods=['POST'])
def cleanup():
    if 'session_id' in session:
        session_id = session['session_id']
        
        # Clean up temporary files
        try:
            if 'file_path' in session and os.path.exists(session['file_path']):
                os.remove(session['file_path'])
            
            # Remove frame files
            frames_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'image_frames_{session_id}')
            if os.path.exists(frames_dir):
                for frame_path in session.get('frames_paths', []):
                    if os.path.exists(frame_path):
                        os.remove(frame_path)
                os.rmdir(frames_dir)
        except Exception as e:
            logging.error(f"Error cleaning up files: {str(e)}")
    
    # Clear session data
    session.clear()
    return jsonify({'success': True})

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({'error': 'File too large (max 16MB)'}), 413

@app.errorhandler(500)
def server_error(error):
    """
    Handle 500 Internal Server Error by returning JSON instead of HTML
    This is important for frontend error handling to work properly
    """
    logging.error(f"500 error occurred: {str(error)}")
    response = jsonify({
        'success': False,
        'error': 'Internal server error. Please try again with a different image.',
        'message': 'Server encountered an error. Please try again with a different image.',
        'results': []
    })
    response.status_code = 500
    return response

@app.route('/diagnostics')
def run_system_diagnostics():
    """
    Run system diagnostics and return results
    This is mainly for administrators to troubleshoot OCR issues
    """
    try:
        # Re-run diagnostics to get the latest information
        from utils.diagnostics import run_diagnostics
        results = run_diagnostics(app.config['UPLOAD_FOLDER'])
        
        # Perform a test OCR on a sample image if diagnostic images are available
        test_results = {}
        
        try:
            from utils.ocr_engine import perform_ocr_on_frame
            import os
            
            # Try to find a test image
            test_image_path = None
            test_dir = os.path.join(os.getcwd(), 'test_files')
            
            if os.path.exists(test_dir):
                for filename in os.listdir(test_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                        test_image_path = os.path.join(test_dir, filename)
                        break
            
            if test_image_path and os.path.exists(test_image_path):
                test_results['test_image'] = test_image_path
                ocr_text = perform_ocr_on_frame(test_image_path)
                test_results['ocr_result'] = ocr_text
                test_results['success'] = ocr_text and not ocr_text.startswith('Error:')
            else:
                test_results['error'] = 'No test image found'
                
        except Exception as test_err:
            test_results['error'] = str(test_err)
        
        # Return diagnostics results as JSON
        return jsonify({
            'diagnostics': results,
            'test_ocr': test_results,
            'app_config': {
                'upload_folder': app.config['UPLOAD_FOLDER'],
                'max_content_length': app.config['MAX_CONTENT_LENGTH'],
                'debug_mode': app.config['DEBUG_MODE']
            }
        })
    except Exception as e:
        logging.error(f"Error running diagnostics: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Error running diagnostics: {str(e)}'
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
