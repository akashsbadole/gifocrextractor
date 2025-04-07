#!/usr/bin/env python3
"""
Test OCR functionality with the test images
"""
import os
import sys
from utils.ocr_engine import perform_ocr_on_frame

def test_ocr_on_image(image_path):
    """Test OCR on a single image"""
    print(f"Testing OCR on image: {image_path}")
    text = perform_ocr_on_frame(image_path)
    print(f"OCR Result: {text}")
    return text

if __name__ == "__main__":
    # Use the first test image
    test_dir = os.path.join(os.getcwd(), 'test_files')
    test_images = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.endswith(('.png', '.jpg'))]
    
    if not test_images:
        print("No test images found!")
        sys.exit(1)
    
    print(f"Found {len(test_images)} test images")
    
    # Test each image
    for image_path in test_images:
        test_ocr_on_image(image_path)
        print("-" * 40)
