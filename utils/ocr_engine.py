import os
import logging
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import subprocess
import time
import tempfile
import re

def check_tesseract():
    """
    Check if Tesseract is installed and running properly
    
    Returns:
        bool: True if Tesseract is working, False otherwise
    """
    try:
        # Check if tesseract is available by running a simple command
        result = subprocess.run(['tesseract', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               timeout=5)
        
        if result.returncode == 0:
            logging.info(f"Tesseract is installed: {result.stdout.splitlines()[0]}")
            
            # Check for language data availability
            lang_result = subprocess.run(['tesseract', '--list-langs'],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        timeout=5)
            
            if lang_result.returncode == 0:
                langs = [l.strip() for l in lang_result.stdout.splitlines()[1:]]
                logging.info(f"Tesseract language packs found: {len(langs)}")
                
                # Check specifically for English language pack, which we need
                if 'eng' in langs:
                    logging.info(f"English language pack is available")
                else:
                    logging.warning(f"English language pack not found")
            else:
                logging.warning(f"Could not retrieve language packs: {lang_result.stderr}")
            
            return True
            
        else:
            logging.error(f"Tesseract check failed: {result.stderr}")
            return False
    
    except subprocess.TimeoutExpired:
        logging.error("Tesseract version check timed out")
        return False
    except FileNotFoundError:
        logging.error("Tesseract is not installed or not in PATH")
        return False
    except Exception as e:
        logging.error(f"Error checking Tesseract: {str(e)}")
        return False

def enhance_image_for_ocr(img):
    """
    Apply image enhancements to improve OCR text detection
    
    Args:
        img: PIL Image object
        
    Returns:
        enhanced_img: Enhanced PIL Image object
    """
    try:
        # Convert to RGB if needed
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        elif img.mode == 'P':
            img = img.convert('RGB')
        
        # Create a grayscale version
        gray_img = img.convert('L')
        
        # Enhance contrast
        contrast_img = ImageEnhance.Contrast(gray_img).enhance(2.0)
        
        # Sharpen the image
        sharp_img = ImageEnhance.Sharpness(contrast_img).enhance(2.0)
        
        # Apply a slight blur to reduce noise
        blur_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        return blur_img
    except Exception as e:
        logging.warning(f"Image enhancement failed: {str(e)}")
        return img  # Return original image if enhancement fails

def perform_ocr_on_frame(frame_path):
    """
    Perform OCR on a single image frame
    
    Args:
        frame_path (str): Path to the image frame
        
    Returns:
        str: Extracted text from the image, or error message if failed
    """
    # First check if tesseract is working
    if not check_tesseract():
        logging.error("Tesseract OCR is not available, skipping OCR processing")
        return "Error: Tesseract OCR is not available"
    
    try:
        # Check if the file exists and has content
        if not os.path.exists(frame_path):
            logging.error(f"Frame file does not exist: {frame_path}")
            return "Error: Frame file not found"
            
        file_size = os.path.getsize(frame_path)
        if file_size == 0:
            logging.error(f"Frame file is empty (0 bytes): {frame_path}")
            return "Error: Frame file is empty"
            
        logging.info(f"Processing frame: {frame_path}, Size: {file_size} bytes")
        
        try:
            # Open the image using PIL
            with Image.open(frame_path) as img:
                # Try several OCR approaches with different image processing
                results = []
                
                # 1. Original image OCR
                try:
                    text1 = pytesseract.image_to_string(img, lang='eng')
                    if text1.strip():
                        results.append(text1.strip())
                except Exception as e:
                    logging.debug(f"Original image OCR failed: {str(e)}")
                
                # 2. Enhanced image OCR
                try:
                    enhanced_img = enhance_image_for_ocr(img)
                    text2 = pytesseract.image_to_string(enhanced_img, lang='eng')
                    if text2.strip():
                        results.append(text2.strip())
                except Exception as e:
                    logging.debug(f"Enhanced image OCR failed: {str(e)}")
                
                # 3. Try different OCR configurations for challenging text
                try:
                    # Try a different PSM mode that might detect text better in some cases
                    custom_config = r'--oem 3 --psm 11'  # Sparse text
                    text3 = pytesseract.image_to_string(img, lang='eng', config=custom_config)
                    if text3.strip():
                        results.append(text3.strip())
                except Exception as e:
                    logging.debug(f"Custom config OCR failed: {str(e)}")
                
                # Choose the best result by length
                if results:
                    best_text = max(results, key=len)
                    
                    frame_filename = os.path.basename(frame_path)
                    logging.info(f"OCR on {frame_filename} successful, extracted: {best_text[:50]}...")
                    return best_text
                else:
                    logging.info(f"No text found in {frame_path}")
                    return "No text detected"
                
        except Exception as img_err:
            # Log details about the image opening/processing error
            logging.error(f"Error opening/processing image {frame_path}: {str(img_err)}")
            return f"Error: Invalid image file: {str(img_err)}"
                
    except Exception as e:
        # This catches any other errors not related to image processing or OCR
        logging.error(f"Unexpected error processing {frame_path}: {str(e)}")
        # Return a generic message instead of the error to avoid exposing system details
        return "Error: OCR processing failed for this frame"

def perform_ocr_on_frames(frames_paths):
    """
    Perform OCR on multiple image frames with robust error handling
    
    Args:
        frames_paths (list): List of paths to image frames
        
    Returns:
        list: List of dictionaries containing frame number, path, and extracted text
              Returns an empty list if an unrecoverable error occurs
    """
    try:
        # Early validation
        if not frames_paths:
            logging.warning("No frames provided for OCR processing")
            return []
        
        # Initialize tracking variables
        logging.info(f"Starting OCR processing on {len(frames_paths)} frames")
        
        ocr_results = []
        error_count = 0
        success_count = 0
        empty_count = 0
        
        # Process each frame, continuing even if some fail
        for idx, frame_path in enumerate(frames_paths):
            try:
                # Process the frame
                extracted_text = perform_ocr_on_frame(frame_path)
                
                # Check if it's an error message
                if extracted_text.startswith("Error:"):
                    error_count += 1
                    logging.warning(f"OCR error on frame {idx+1}: {extracted_text}")
                elif not extracted_text or extracted_text == "No text detected":
                    empty_count += 1
                else:
                    success_count += 1
                
                # Add result
                ocr_results.append({
                    'frame_number': idx + 1,
                    'frame_path': frame_path,
                    'text': extracted_text
                })
                
                logging.info(f"OCR Progress: Processed {idx+1}/{len(frames_paths)} frames")
                
            except Exception as frame_err:
                logging.error(f"Unhandled error processing frame {idx+1}: {str(frame_err)}")
                ocr_results.append({
                    'frame_number': idx + 1,
                    'frame_path': frame_path,
                    'text': "Error: OCR processing failed. Please try a different image."
                })
                error_count += 1
        
        # If we have OCR results, try to find longer text spans by analyzing all frames
        if success_count > 0:
            try:
                # Combine OCR results to look for patterns across frames (for animated reveals)
                all_text = " ".join([r['text'] for r in ocr_results if not r['text'].startswith("Error:") and r['text'] != "No text detected"])
                
                # Look for common phrases with at least 3 consecutive letters or numbers
                word_pattern = re.compile(r'[A-Za-z0-9]{3,}')
                words = word_pattern.findall(all_text)
                
                if words:
                    # Find longest detected word
                    longest_word = max(words, key=len)
                    if len(longest_word) >= 4:  # Only care about substantial words
                        logging.info(f"Found significant word across frames: {longest_word}")
                        
                        # Add a combined analysis note if we found a substantial word
                        ocr_results.append({
                            'frame_number': len(frames_paths) + 1,
                            'frame_path': "combined_analysis",
                            'text': f"Combined analysis: Found text pattern '{longest_word}'"
                        })
            except Exception as analysis_err:
                logging.debug(f"Combined frame analysis failed: {str(analysis_err)}")
        
        # Log summary statistics
        total_processed = len(ocr_results) - (1 if success_count > 0 and "combined_analysis" in [r.get('frame_path', '') for r in ocr_results] else 0)
        logging.info(f"OCR completed on {total_processed} frames. Success: {success_count}, Empty: {empty_count}, Errors: {error_count}")
        
        return ocr_results
        
    except Exception as e:
        # If we encounter a fatal error, log it and return a helpful error message
        logging.error(f"Fatal error in OCR processing: {str(e)}")
        
        # Return a list with one error result rather than an empty list
        # This makes it easier for the frontend to display the error
        return [{
            'frame_number': 1,
            'frame_path': frames_paths[0] if frames_paths and len(frames_paths) > 0 else "",
            'text': "Error: OCR processing failed. Please try a different image."
        }]
