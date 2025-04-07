from app import app
import logging
import sys
import os
import platform
import subprocess

def get_system_info():
    """Collect system information for better debugging"""
    info = {}
    info['platform'] = platform.platform()
    info['python_version'] = platform.python_version()
    info['memory'] = {}
    
    try:
        import psutil
        vm = psutil.virtual_memory()
        info['memory']['total'] = f"{vm.total / (1024**3):.2f} GB"
        info['memory']['available'] = f"{vm.available / (1024**3):.2f} GB"
        info['memory']['percent'] = f"{vm.percent}%"
    except ImportError:
        info['memory'] = "psutil not available"
    
    # Check tesseract version
    try:
        result = subprocess.run(['tesseract', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               timeout=5)
        if result.returncode == 0:
            info['tesseract'] = result.stdout.splitlines()[0].strip()
        else:
            info['tesseract'] = f"Error: {result.stderr}"
    except Exception as e:
        info['tesseract'] = f"Error checking: {str(e)}"
    
    # Check if required directories exist and are writable
    temp_dir = os.environ.get('TEMP') or os.environ.get('TMP') or '/tmp'
    info['temp_dir'] = {
        'path': temp_dir,
        'exists': os.path.exists(temp_dir),
        'writable': os.access(temp_dir, os.W_OK) if os.path.exists(temp_dir) else False
    }
    
    return info

if __name__ == "__main__":
    # Configure more detailed logging
    logging.basicConfig(
        level=logging.DEBUG,  # Set to DEBUG for more detailed logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout
    )
    
    # Set specific logger levels
    logging.getLogger('PIL').setLevel(logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Log system information
    system_info = get_system_info()
    logging.info("System Information:")
    for key, value in system_info.items():
        if isinstance(value, dict):
            logging.info(f"  {key}:")
            for subkey, subvalue in value.items():
                logging.info(f"    {subkey}: {subvalue}")
        else:
            logging.info(f"  {key}: {value}")
    
    # Set up Flask app and check environment variables
    secret_key = os.environ.get("SESSION_SECRET")
    if not secret_key:
        logging.warning("SESSION_SECRET environment variable not set. Using default secret key.")
    
    # Check if we have a working tesseract installation
    from utils.ocr_engine import check_tesseract
    if check_tesseract():
        logging.info("Tesseract OCR is installed and working correctly.")
    else:
        logging.error("Tesseract OCR is not working properly. OCR functionality will be unavailable.")
    
    logging.info("Starting GIF OCR Extractor application")
    app.run(host="0.0.0.0", port=5000, debug=True)
