import pandas as pd
import logging
import os

def export_to_excel(ocr_results, output_path):
    """
    Export OCR results to Excel format
    
    Args:
        ocr_results (list): List of dictionaries containing OCR results
        output_path (str): Path to save the Excel file
        
    Returns:
        bool: True if export was successful
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Log what we're trying to export
        logging.info(f"Exporting {len(ocr_results)} OCR results to Excel: {output_path}")
        
        # Handle empty results
        if not ocr_results:
            logging.warning("No OCR results to export")
            # Create a dataframe with a message
            df = pd.DataFrame([{"frame_number": 1, "text": "No text was detected in the image"}])
            df.to_excel(output_path, index=False, sheet_name='OCR Results')
            return True
            
        # Clean up the OCR results to ensure they have the expected format
        cleaned_results = []
        for result in ocr_results:
            # Ensure the result has the required keys
            if isinstance(result, dict) and 'frame_number' in result and 'text' in result:
                # Create a clean record with just the frame number and text
                cleaned_results.append({
                    'frame_number': result['frame_number'],
                    'text': result['text']
                })
        
        # Create a DataFrame from the cleaned OCR results
        df = pd.DataFrame(cleaned_results)
        
        # Export to Excel
        df.to_excel(output_path, index=False, sheet_name='OCR Results')
        
        logging.info(f"Successfully exported {len(df)} OCR results to Excel: {output_path}")
        return True
    
    except Exception as e:
        logging.error(f"Error exporting to Excel: {str(e)}")
        # Create a simple Excel file with the error message
        try:
            df = pd.DataFrame([{"Error": f"Failed to export results: {str(e)}"}])
            df.to_excel(output_path, index=False)
            logging.info(f"Created error message Excel file at {output_path}")
            return True
        except Exception as fallback_err:
            logging.error(f"Even fallback Excel export failed: {str(fallback_err)}")
            raise

def export_to_csv(ocr_results, output_path):
    """
    Export OCR results to CSV format
    
    Args:
        ocr_results (list): List of dictionaries containing OCR results
        output_path (str): Path to save the CSV file
        
    Returns:
        bool: True if export was successful
    """
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Log what we're trying to export
        logging.info(f"Exporting {len(ocr_results)} OCR results to CSV: {output_path}")
        
        # Handle empty results
        if not ocr_results:
            logging.warning("No OCR results to export")
            # Create a dataframe with a message
            df = pd.DataFrame([{"frame_number": 1, "text": "No text was detected in the image"}])
            df.to_csv(output_path, index=False)
            return True
            
        # Clean up the OCR results to ensure they have the expected format
        cleaned_results = []
        for result in ocr_results:
            # Ensure the result has the required keys
            if isinstance(result, dict) and 'frame_number' in result and 'text' in result:
                # Create a clean record with just the frame number and text
                cleaned_results.append({
                    'frame_number': result['frame_number'],
                    'text': result['text']
                })
        
        # Create a DataFrame from the cleaned OCR results
        df = pd.DataFrame(cleaned_results)
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        logging.info(f"Successfully exported {len(df)} OCR results to CSV: {output_path}")
        return True
    
    except Exception as e:
        logging.error(f"Error exporting to CSV: {str(e)}")
        # Create a simple CSV file with the error message
        try:
            df = pd.DataFrame([{"Error": f"Failed to export results: {str(e)}"}])
            df.to_csv(output_path, index=False)
            logging.info(f"Created error message CSV file at {output_path}")
            return True
        except Exception as fallback_err:
            logging.error(f"Even fallback CSV export failed: {str(fallback_err)}")
            raise
