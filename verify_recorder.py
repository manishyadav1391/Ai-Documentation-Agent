import os
import time
import logging
import json
import zipfile
from recorder.recorder import Recorder

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def verify():
    logging.info("========================================")
    logging.info("Starting Desktop Recorder Verification")
    logging.info("========================================")
    
    # 1. Instantiate recorder
    recorder = Recorder(base_dir=".")
    
    # 2. Start recorder
    logging.info("Starting recording. Please perform 2-3 clicks or type some text now!")
    logging.info("The recorder will run for 10 seconds...")
    recorder.start()
    
    # Run for 10 seconds
    for i in range(10):
        time.sleep(1)
        logging.info(f"Recording... {10 - i} seconds remaining.")
        
    # 3. Stop recorder
    logging.info("Stopping recording and generating exports...")
    zip_path = recorder.stop()
    
    if not zip_path or not os.path.exists(zip_path):
        logging.error("❌ Verification Failed: Zip archive was not created!")
        return False
        
    logging.info(f"✅ Zip archive successfully created at: {zip_path}")
    
    # 4. Verify ZIP Contents
    logging.info("Verifying ZIP contents...")
    session_id = recorder.session_id
    expected_files = [
        f"{session_id}/session.json",
        f"{session_id}/metadata.json"
    ]
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            namelist = zipf.namelist()
            logging.info(f"Files inside ZIP: {namelist}")
            
            for expected in expected_files:
                if expected not in namelist:
                    logging.error(f"❌ Verification Failed: Missing expected file '{expected}' inside ZIP.")
                    return False
            
            # Read and print the session.json content
            session_json_content = zipf.read(f"{session_id}/session.json").decode('utf-8')
            session_data = json.loads(session_json_content)
            logging.info("========================================")
            logging.info("session.json Structure and Output:")
            logging.info(json.dumps(session_data, indent=2))
            logging.info("========================================")
            
            logging.info(f"Total actions logged: {len(session_data.get('steps', []))}")
            for step in session_data.get('steps', []):
                logging.info(f"  Step {step['step_no']}: [{step['action_type']}] in window '{step['window_title']}'")
                screenshot_in_zip = f"{session_id}/{step['screenshot'].replace(chr(92), '/')}"
                if screenshot_in_zip not in namelist:
                    logging.error(f"❌ Verification Failed: Screenshot '{screenshot_in_zip}' was not found in ZIP.")
                    return False
                else:
                    logging.info(f"    ✓ Screenshot verified in ZIP: {screenshot_in_zip}")
                    
    except Exception as e:
        logging.error(f"❌ Verification Failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    logging.info("========================================")
    logging.info("🎉 SUCCESS: Desktop Recorder verified successfully!")
    logging.info("========================================")
    return True

if __name__ == "__main__":
    verify()
