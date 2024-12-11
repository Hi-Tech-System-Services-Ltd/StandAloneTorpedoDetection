import pyodbc
import datetime
from ultralytics import YOLO
import os
import shutil
import time
import threading
import datetime

save_directory = "Cam1_2DetectionApp\\images_cam2"  # Directory for saving images
temp_image_dir = "Cam1_2DetectionApp\\tempimages"  # Directory for temporary image storage

# Ensure that the temporary image directory exists
if not os.path.exists(temp_image_dir):
    os.makedirs(temp_image_dir)

# Image paths
cam1_image_path = "E:\\flir\\images\\thermal_image_2.jpg"

# Model paths
torpedo_classification_model_path = "E:\\flir\\Detection\\Cam1_2DetectionApp\\models\\cam1classify.pt"
cam1_detection_model_path = "E:\\flir\\Detection\\Cam1_2DetectionApp\\models\\cam2detect.pt"

# Load models
torpedo_classification_model = YOLO(torpedo_classification_model_path)
cam1_detection_model = YOLO(cam1_detection_model_path)

# Class to detect the largest bounding box
class LargestBoundingBoxDetector:
    def __init__(self, model, save_directory, temp_image_dir):
        self.model = model
        self.save_directory = save_directory
        self.temp_image_dir = temp_image_dir
        self.largest_box = None
        self.largest_area = 0
        self.save_path = os.path.join(self.temp_image_dir, "largest_box_image.jpg")  # Save in tempimages

    def save_image(self, source_image_path):
        print(f"Saving image to {self.save_path}")
        shutil.copy(source_image_path, self.save_path)

    def detect_objects(self, image_path):
        results = self.model(image_path)
        if not results:
            print("No results returned from model.")
            return None
        for result in results:
            boxes = result.boxes
            if not boxes:
                print("No boxes detected.")
                return None
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().detach().numpy().astype(int)
                width = x2 - x1
                height = y2 - y1
                area = width * height
                if area > self.largest_area:
                    self.largest_box = (x1, y1, x2, y2, width, height)
                    self.largest_area = area
                    self.save_image(image_path)
        return self.largest_box

    def compare_and_update(self, image_path):
        current_box = self.detect_objects(image_path)
        if current_box:
            x1, y1, x2, y2, width, height = current_box
            current_area = width * height
            if current_area < self.largest_area:
                print(f"Reducing size detected. Returning last largest bounding box: {self.largest_box}")
                return self.largest_box
        return current_box

# Process image and detect objects
def process_image(image_path, model, save_directory, temp_image_dir, check_interval=1):
    detector = LargestBoundingBoxDetector(model, save_directory, temp_image_dir)
    
    # Initial processing and save
    detector.detect_objects(image_path)
    print(f"Initial largest bounding box: {detector.largest_box}")
    
    try:
        while True:
            bounding_box = detector.compare_and_update(image_path)
            print(f"Current bounding box: {bounding_box}")
            time.sleep(check_interval)
    except KeyboardInterrupt:
        print("Stopping the process.")

# Calculate bounding box information
def calculate_bbox_info(x1, y1, x2, y2):
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    return center_x, center_y

# Database insertion function
def insert_detection_data(torpedo_id, center_x, center_y, width, height, camera_id):
    torpedo_id = int(torpedo_id)
    center_x = int(center_x)
    center_y = int(center_y)
    width = int(width)
    height = int(height)
    camera_id = int(camera_id)

    # SQL Server connection details
    server = '192.168.1.1\SQLEXPRESS'
    database = 'flir_torpedo_monitoring'
    username = 'sa'
    password = 'hitech@1234'

    # Connection string
    connection_string = (
        'DRIVER={ODBC Driver 17 for SQL Server};'
        f'SERVER={server};'
        f'DATABASE={database};'
        f'UID={username};'
        f'PWD={password};'
    )

    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    detection_data = {
        "TorpedoID": torpedo_id,
        "detectiondttime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "centerx": center_x,
        "centery": center_y,
        "width": width,
        "height": height,
        "udt": 0,
        "CameraID": camera_id
    }

    insert_query = """
    INSERT INTO torpedo_detection_master (TorpedoID, detectiondttime, centerx, centery, width, height, udt, CameraID)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    try:
        cursor.execute(insert_query, (
            detection_data["TorpedoID"],
            detection_data["detectiondttime"],
            detection_data["centerx"],
            detection_data["centery"],
            detection_data["width"],
            detection_data["height"],
            detection_data["udt"],
            detection_data["CameraID"]
        ))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()

# check if torpedo in frame
def is_torpedo_present():
    results = torpedo_classification_model.predict(source=cam1_image_path)
    if not results:
        print("No results from torpedo model.")
        return False
    for result in results:
        top1_class_id = result.probs.top1
        top1_confidence = result.probs.top1conf  # Directly using top1conf
        s = f"{top1_class_id} {result.names[top1_class_id]} {top1_confidence:.2f}"
        if "NonTorpedoFrame" in s:
            return False
    return True



# Main function to start detection
def main():
    detector_cam1 = LargestBoundingBoxDetector(cam1_detection_model, save_directory, temp_image_dir)
    torpedo_id = 100

    def cam1_detection_thread():
        global x1_cam1, y1_cam1, x2_cam1, y2_cam1, width_cam1, height_cam1
        coordinates_cam1 = detector_cam1.detect_objects(cam1_image_path)
        
        if coordinates_cam1 is None:
            print("No bounding box detected, skipping data push.")
            return

        print(coordinates_cam1)
        x1_cam1, y1_cam1, x2_cam1, y2_cam1, width_cam1, height_cam1 = coordinates_cam1
        center_x, center_y = calculate_bbox_info(x1_cam1, y1_cam1, x2_cam1, y2_cam1)
        filename = f"{datetime.datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.jpg"
        save_image_path = os.path.join(save_directory, filename)
        
        try:
            shutil.copy(os.path.join(temp_image_dir, "largest_box_image.jpg"), save_image_path)
        except FileNotFoundError as e:
            print(f"File not found error: {e}")
        
        insert_detection_data(torpedo_id, center_x, center_y, width_cam1, height_cam1, 2)
        print("Cam2 data pushed\n")

    torpedo_in_frame = is_torpedo_present()

    if torpedo_in_frame:
        cam2_thread = threading.Thread(target=cam1_detection_thread)
        cam2_thread.start()
        cam2_thread.join()
    else:
        print("No torpedo detected, hence not pushed")

if __name__ == "__main__":
    main()
