import os
import logging
from PIL import Image, ImageEnhance
import uuid
import time
import sys

def extract_frames_from_image(image_path, output_dir):
    """
    Extract frames from an image file (GIF, JPEG, JPG, PNG, AVIF)
    For animated GIFs, extracts all frames
    For static images (JPEG, PNG, AVIF), treats the image as a single frame
    
    Args:
        image_path (str): Path to the image file
        output_dir (str): Directory to save extracted frames
        
    Returns:
        list: List of paths to extracted frame images
    """
    # Verify that the image file exists
    if not os.path.exists(image_path):
        logging.error(f"Image file not found: {image_path}")
        raise FileNotFoundError(f"Image file not found: {image_path}")
    
    # Check if the file is of a reasonable size
    file_size = os.path.getsize(image_path)
    if file_size == 0:
        logging.error(f"Image file is empty (0 bytes): {image_path}")
        raise ValueError(f"Image file is empty: {image_path}")
    
    file_size_mb = file_size / (1024 * 1024)  # Size in MB
    logging.info(f"Processing image: {os.path.basename(image_path)}, Size: {file_size_mb:.2f} MB")
        
    # Ensure output directory exists
    if not os.path.exists(output_dir):
        logging.info(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    
    # Verify we have write access to the output directory
    try:
        test_file = os.path.join(output_dir, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logging.info(f"Output directory {output_dir} is writable")
    except Exception as perm_err:
        logging.error(f"Cannot write to output directory {output_dir}: {str(perm_err)}")
        raise PermissionError(f"Cannot write to output directory: {str(perm_err)}")
    
    try:
        frames_paths = []
        start_time = time.time()
        
        # Try to open the image file and process it
        try:
            # Open the image file
            with Image.open(image_path) as img:
                # Get the format and check if it's an animated GIF or a static image
                img_format = img.format
                img_size = img.size
                img_mode = img.mode
                
                # Get the number of frames (will be 1 for static images)
                frames_count = getattr(img, "n_frames", 1)
                logging.info(f"{img_format} image details: {frames_count} frames, dimensions: {img_size}, mode: {img_mode}")
                
                # Check if it's a reasonable number of frames for animated GIFs
                if frames_count > 200:
                    logging.warning(f"Image has a large number of frames ({frames_count}), this may take a while to process")
                
                # Process each frame
                for frame_idx in range(frames_count):
                    frame_start_time = time.time()
                    
                    try:
                        # For multi-frame images (animated GIFs), seek to the specific frame
                        if frames_count > 1:
                            img.seek(frame_idx)
                        
                        # Create a copy of the frame to prevent issues with the original image
                        frame = img.copy()
                        
                        # Convert to RGB if needed (for RGBA or palette images)
                        original_mode = frame.mode
                        if frame.mode == 'RGBA' or frame.mode == 'P':
                            frame = frame.convert('RGB')
                            logging.info(f"Converted frame {frame_idx+1} from {original_mode} to RGB")
                        
                        # Apply image enhancements for better OCR results
                        try:
                            # Increase contrast slightly
                            enhancer = ImageEnhance.Contrast(frame)
                            frame = enhancer.enhance(1.5)  # Increase contrast by 50%
                            
                            # Increase sharpness
                            enhancer = ImageEnhance.Sharpness(frame)
                            frame = enhancer.enhance(1.5)  # Increase sharpness by 50%
                            
                            # Enhance brightness slightly if needed
                            enhancer = ImageEnhance.Brightness(frame)
                            frame = enhancer.enhance(1.2)  # Increase brightness by 20%
                        except Exception as enhance_err:
                            logging.warning(f"Could not apply image enhancements to frame {frame_idx+1}: {str(enhance_err)}")
                        
                        # Generate a unique filename for each frame
                        frame_filename = f"frame_{frame_idx}_{uuid.uuid4().hex}.jpg"
                        frame_path = os.path.join(output_dir, frame_filename)
                        
                        # Save the frame with high quality
                        frame.save(frame_path, "JPEG", quality=95)
                        
                        # Verify the frame was saved correctly
                        if not os.path.exists(frame_path) or os.path.getsize(frame_path) == 0:
                            logging.error(f"Failed to save frame {frame_idx+1} to {frame_path}")
                            continue
                            
                        frames_paths.append(frame_path)
                        
                        frame_time = time.time() - frame_start_time
                        if frames_count == 1 or frame_idx == 0 or (frame_idx + 1) % 10 == 0 or frame_idx == frames_count - 1:
                            logging.info(f"Processed frame {frame_idx + 1}/{frames_count}, time: {frame_time:.2f}s, saved to: {frame_path}")
                    
                    except Exception as frame_err:
                        logging.error(f"Error processing frame {frame_idx+1}: {str(frame_err)}")
                        # Continue with the next frame instead of failing the entire process
                
                # Summary of extraction process
                total_time = time.time() - start_time
                if len(frames_paths) > 0:
                    logging.info(f"Successfully extracted {len(frames_paths)}/{frames_count} frames in {total_time:.2f}s")
                    return frames_paths
                else:
                    logging.error("Failed to extract any frames from the image")
                    raise ValueError("No frames could be extracted from the image")
        
        except Exception as img_err:
            logging.error(f"Error opening or processing image file {image_path}: {str(img_err)}")
            raise ValueError(f"Invalid image file: {str(img_err)}")
    
    except Exception as e:
        logging.error(f"Error extracting frames from image: {str(e)}")
        raise
