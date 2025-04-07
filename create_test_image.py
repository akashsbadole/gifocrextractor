#!/usr/bin/env python3
"""
Create a simple test image with text for OCR testing.
This script generates a PNG image with sample text that can be used
to test the OCR functionality.
"""
import os
from PIL import Image, ImageDraw, ImageFont

def create_text_image(output_path, text="Hello World! This is a test image for OCR.", size=(800, 300), 
                     bg_color=(255, 255, 255), text_color=(0, 0, 0)):
    """
    Create a simple image with text.
    
    Args:
        output_path (str): Path to save the generated image
        text (str): Text to draw on the image
        size (tuple): Size of the image (width, height)
        bg_color (tuple): Background color (R, G, B)
        text_color (tuple): Text color (R, G, B)
    
    Returns:
        str: Path to the generated image
    """
    # Create a blank image with the specified background color
    image = Image.new('RGB', size, color=bg_color)
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, fall back to default if not available
    try:
        # Use a built-in font that should be available on most systems
        font_size = 36
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except IOError:
        # Fall back to default font
        font = None
    
    # Calculate text position (center of image)
    # Newer versions of Pillow use .textbbox or .textlength instead of .textsize
    try:
        if font:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top
        else:
            left, top, right, bottom = draw.textbbox((0, 0), text)
            text_width = right - left
            text_height = bottom - top
    except AttributeError:
        # Fall back to older method if textbbox is not available
        try:
            text_width, text_height = draw.textsize(text, font=font) if font else draw.textsize(text)
        except AttributeError:
            # For very new Pillow where both are deprecated
            text_width = size[0] // 4  # Estimate
            text_height = font_size if 'font_size' in locals() else 36
    
    position = ((size[0] - text_width) // 2, (size[1] - text_height) // 2)
    
    # Draw the text
    draw.text(position, text, fill=text_color, font=font)
    
    # Save the image
    image.save(output_path)
    print(f"Created test image: {output_path}")
    return output_path

def create_multiple_test_images(output_dir):
    """
    Create multiple test images with different text and styles
    
    Args:
        output_dir (str): Directory to save test images
    
    Returns:
        list: Paths to generated images
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # List of sample texts
    texts = [
        "Hello World! This is a test image for OCR.",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890",
        "abcdefghijklmnopqrstuvwxyz !@#$%^&*()",
        "The quick brown fox jumps over the lazy dog.",
        "OCR Test: Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    ]
    
    # Create images with different text
    generated_files = []
    for i, text in enumerate(texts):
        output_path = os.path.join(output_dir, f"test_image_{i+1}.png")
        create_text_image(output_path, text)
        generated_files.append(output_path)
    
    return generated_files

if __name__ == "__main__":
    # Create test images in the 'test_files' directory
    output_dir = os.path.join(os.getcwd(), 'test_files')
    created_files = create_multiple_test_images(output_dir)
    print(f"Created {len(created_files)} test images in {output_dir}")