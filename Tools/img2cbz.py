# Code By @V_Sbotmaker (on Telegram)

import os
import zipfile
from loguru import logger

def images_to_cbz(image_files, cbz_output_path):
    os.makedirs(os.path.dirname(cbz_output_path), exist_ok=True)
    try:
        with zipfile.ZipFile(cbz_output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for image_file_path in image_files:
                file_name = os.path.basename(image_file_path)
                
                zip_file.write(image_file_path, arcname=file_name)
                
        zip_file.close()
        
        #logger.info(f"Compressed PDF created at {cbz_output_path}")
    except Exception as e:
        logger.exception(f"Making CBZ: {e}")
        return e
    
