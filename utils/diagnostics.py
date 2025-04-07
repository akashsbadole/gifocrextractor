"""
Diagnostics utility for troubleshooting OCR and GIF processing issues.
This module provides functions to diagnose common issues with Tesseract OCR
and GIF image processing.
"""
import os
import platform
import subprocess
import logging
import shutil
import sys

def check_system_resources():
    """
    Check system resources like disk space, memory, etc.
    
    Returns:
        dict: Dictionary with system resource information
    """
    resources = {}
    
    # Check available disk space
    try:
        total, used, free = shutil.disk_usage('/')
        resources['disk'] = {
            'total_gb': total / (1024**3),
            'used_gb': used / (1024**3),
            'free_gb': free / (1024**3),
            'percent_used': (used / total) * 100
        }
    except Exception as e:
        resources['disk'] = {'error': str(e)}
    
    # Check memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        resources['memory'] = {
            'total_gb': mem.total / (1024**3),
            'available_gb': mem.available / (1024**3),
            'percent_used': mem.percent
        }
    except ImportError:
        resources['memory'] = {'error': 'psutil not installed'}
    except Exception as e:
        resources['memory'] = {'error': str(e)}
    
    # Get system info
    resources['platform'] = platform.platform()
    resources['python_version'] = platform.python_version()
    resources['architecture'] = platform.architecture()
    
    return resources

def check_tesseract_installation():
    """
    Check details of Tesseract OCR installation
    
    Returns:
        dict: Dictionary with Tesseract installation information
    """
    tesseract_info = {'installed': False}
    
    try:
        # Check if tesseract is available by running a simple command
        result = subprocess.run(['tesseract', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE,
                               text=True,
                               timeout=5)
        
        if result.returncode == 0:
            tesseract_info['installed'] = True
            version_output = result.stdout.splitlines()
            if version_output:
                tesseract_info['version'] = version_output[0]
            
            # Check for language data availability
            lang_result = subprocess.run(['tesseract', '--list-langs'],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True,
                                timeout=5)
            
            if lang_result.returncode == 0:
                langs = [lang.strip() for lang in lang_result.stdout.splitlines() if lang.strip()]
                # Skip the first line which is usually a header
                if len(langs) > 1:
                    langs = langs[1:]
                    tesseract_info['languages'] = langs
                    tesseract_info['num_languages'] = len(langs)
                    tesseract_info['has_english'] = 'eng' in langs
                else:
                    tesseract_info['languages'] = []
                    tesseract_info['error'] = 'No language packs found'
            else:
                tesseract_info['error'] = f"Language check error: {lang_result.stderr}"
        else:
            tesseract_info['error'] = f"Tesseract error: {result.stderr}"
            
    except Exception as e:
        tesseract_info['error'] = f"Error checking Tesseract: {str(e)}"
    
    return tesseract_info

def check_image_libraries():
    """
    Check availability and versions of image processing libraries
    
    Returns:
        dict: Dictionary with image library information
    """
    libraries = {}
    
    # Check PIL/Pillow
    try:
        from PIL import Image, __version__ as pil_version
        libraries['pillow'] = {
            'installed': True,
            'version': pil_version,
            'formats': Image.registered_extensions()
        }
    except ImportError:
        libraries['pillow'] = {'installed': False, 'error': 'Not installed'}
    except Exception as e:
        libraries['pillow'] = {'installed': False, 'error': str(e)}
    
    # Check pytesseract
    try:
        import pytesseract
        version = getattr(pytesseract, '__version__', 'Unknown')
        libraries['pytesseract'] = {
            'installed': True,
            'version': version
        }
    except ImportError:
        libraries['pytesseract'] = {'installed': False, 'error': 'Not installed'}
    except Exception as e:
        libraries['pytesseract'] = {'installed': False, 'error': str(e)}
    
    return libraries

def check_file_permissions(directory_path):
    """
    Check read/write permissions for a directory
    
    Args:
        directory_path (str): Path to directory to check
        
    Returns:
        dict: Dictionary with permission information
    """
    permissions = {
        'path': directory_path,
        'exists': os.path.exists(directory_path),
        'is_dir': False,
        'readable': False,
        'writable': False
    }
    
    if permissions['exists']:
        permissions['is_dir'] = os.path.isdir(directory_path)
        
        if permissions['is_dir']:
            # Check read permissions
            try:
                os.listdir(directory_path)
                permissions['readable'] = True
            except Exception as e:
                permissions['read_error'] = str(e)
            
            # Check write permissions
            try:
                test_file = os.path.join(directory_path, '.permission_test')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                permissions['writable'] = True
            except Exception as e:
                permissions['write_error'] = str(e)
    
    return permissions

def run_diagnostics(upload_dir=None):
    """
    Run full diagnostics and return results
    
    Args:
        upload_dir (str, optional): Directory to check for permissions
        
    Returns:
        dict: Dictionary with all diagnostic information
    """
    logging.info("Running system diagnostics...")
    diagnostics = {
        'system': check_system_resources(),
        'tesseract': check_tesseract_installation(),
        'libraries': check_image_libraries()
    }
    
    if upload_dir:
        diagnostics['upload_dir'] = check_file_permissions(upload_dir)
    
    # Log diagnostic results
    log_diagnostics(diagnostics)
    
    return diagnostics

def log_diagnostics(diagnostics):
    """
    Log diagnostic information
    
    Args:
        diagnostics (dict): Diagnostic information to log
    """
    logging.info("===== DIAGNOSTIC RESULTS =====")
    
    # Log system info
    logging.info("System Information:")
    for key, value in diagnostics['system'].items():
        if isinstance(value, dict):
            logging.info(f"  {key}:")
            for subkey, subvalue in value.items():
                logging.info(f"    {subkey}: {subvalue}")
        else:
            logging.info(f"  {key}: {value}")
    
    # Log Tesseract info
    logging.info("Tesseract OCR Information:")
    if diagnostics['tesseract']['installed']:
        logging.info(f"  Version: {diagnostics['tesseract'].get('version', 'Unknown')}")
        logging.info(f"  Languages: {diagnostics['tesseract'].get('num_languages', 0)} installed")
        if not diagnostics['tesseract'].get('has_english', False):
            logging.warning("  WARNING: English language pack not found!")
    else:
        logging.error(f"  NOT INSTALLED: {diagnostics['tesseract'].get('error', 'Unknown error')}")
    
    # Log library info
    logging.info("Image Processing Libraries:")
    for lib, info in diagnostics['libraries'].items():
        if info.get('installed', False):
            logging.info(f"  {lib}: {info.get('version', 'Unknown version')}")
        else:
            logging.error(f"  {lib}: Not installed - {info.get('error', 'Unknown error')}")
    
    # Log upload directory info if provided
    if 'upload_dir' in diagnostics:
        upload_info = diagnostics['upload_dir']
        logging.info(f"Upload Directory ({upload_info['path']}):")
        if not upload_info['exists']:
            logging.error("  Directory does not exist!")
        elif not upload_info['is_dir']:
            logging.error("  Path exists but is not a directory!")
        else:
            logging.info(f"  Readable: {upload_info['readable']}")
            logging.info(f"  Writable: {upload_info['writable']}")
            if not upload_info['readable'] or not upload_info['writable']:
                logging.error("  Permission issues with upload directory!")
    
    logging.info("===============================")