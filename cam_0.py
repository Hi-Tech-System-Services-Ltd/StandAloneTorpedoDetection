
# imports
import pyodbc
import datetime
import os
import shutil
import time
import threading
import cv2
import numpy
import glob
import sys
import requests
from ultralytics import YOLO

# for cam {1, 2, 3}
cam_id = 0 #replace with actual camera id {1, 2, 3}

# dir paths
temp_dir = '' #temp storing of image for analysis
cam_dir = '' #final-storing of image based on cam_id
image_dir = '' #final-storing of image for report and DotNet application calling 

# image paths
stream_image_path = "" #live stream of images from camera

# model paths
cls_model_path = '' #replace with classification model path
detect_model_path = '' #replace with detection model path

#filenames
temp_filename = f"temp_cam0.jpg" # replace with camera number {1, 2, 3}
final_filename = f"cam{cam_id}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"

# delets all file in a dir for deleting temp files 
def deleteFiles(dir_path):
    try:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                
            
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                elif os.path.isdir(file_path):
                    print(f"Skipping directory: {file_path}")
                
            print("All files in the directory have been deleted.")
            
        else:
            print("Invalid directory path")
        
    except Exception as e:
        print(f"An error occured: {e}")    

# To find latest image path for processing and stuffs 
def findLatestImagePath(dir_path):
    image_extensions = ('*.jpg', '*.jpeg', '*.png')
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(dir_path, ext)))
    
    if not image_files:
        print("No images found in the directory")
        return None
    
    latest_image = max(image_files, key=os.path.getatime)
    
    return latest_image

# To find latest image NAME data push 
def findLatestImageName(dir_path):
    image_extensions = ('*.jpg', '*.jpeg', '*.png')  
    image_files = []
    
    for ext in image_extensions:
        image_files.extend(glob.glob(os.path.join(dir_path, ext)))
    
    if not image_files:
        print("No images found in the directory")
        return None
    
    latest_image = max(image_files, key=os.path.getatime)
    
    return os.path.basename(latest_image)

# classification function to classify torpedo frame 
def clsTorpedo(clsModelPath, imagePath):
    clsModel = YOLO(clsModelPath)
    
    results = clsModel.predict(source=imagePath)
    
    if not results:
        print("No result from Torpedo Model")
        return False
    
    for result in results:
        if hasattr(result, 'probs'):
            top1_class_id = result.probs.top1
            top1_confidence = result.probs.top1conf
            
            s = f"{top1_class_id} {result.names[top1_class_id]} {top1_confidence:.2f}"
            
            if "NonTorpedoFrame" in s:
                return False
        else:
            print("Result does not contain probability information")
    
    return True

# To make copy of stream image to temp and form temp to final store 
def makeCopy(src, dst_path, filename):
    try:
        dst = os.path.join(dst_path, filename)

        shutil.copy2(src, dst)
        print(f"Image saved to {dst}")
        
    except Exception as e:
        print(f"Error: {e}")

# detection funtion to detect the torpedo from frame
def detectTorpedo(detectModelPath, imagePath):
    detectModel = YOLO(detectModelPath)
    
    results = detectModel(imagePath)
    
    if not results:
        print("No bounding box")
        return -99, -99, -99, -99
    
    for result in results:
        boxes = result.boxes
        if not boxes:
            print("No boxes found")
            return -99, -99, -99, -99
        
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().detach().numpy().astype(int)
            return x1, y1, x2, y2

# return the bounding box values form the co-ordinates of opposite corners
def boundingBoxinfo(x1, y1, x2, y2):
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    
    width = x2 - x1
    height = y2 - y1
    
    return center_x, center_y, width, height

# pushes data to the server
def pushData_API(torpedo_id, c_x, c_y, w, h, cam_id, filename):
    torpdeo_id = int(torpedo_id)
    c_x = int(c_x)
    c_y = int(c_y)
    w = int(w)
    h = int(h)
    cam_id = int(cam_id)
    
    udt = 0 if 200 < c_x < 400 else 2
    
    # replace with api url {check env file of actual project}
    api_url = ''
    
    data = {
        "TorpedoID": torpdeo_id,
        "centerx": c_x,
        "centery": c_y,
        "width": w,
        "height": h,
        "udt": udt,
        "cameraID": cam_id,
        "filename": filename
    }
    
    try:
        response = requests.post(api_url, json=data)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        pass

"""
def torpedo_id():
    pass

"""
# dummy value late replace with actual logic 
torpedo_id = 99

# cam _ "0" sequence of functions for detection 
def cam0():
    deleteFiles(temp_dir)
    makeCopy(stream_image_path, temp_dir, temp_filename)
    tempImage = findLatestImagePath(temp_dir)
    
    torpedoInFrame = clsTorpedo(cls_model_path, tempImage)
    
    if torpedoInFrame:
        x1, y1, x2, y2 = detectTorpedo(detect_model_path, tempImage)
        
        if x1 == None:
            print("Detect Torpedo Return None")
            return -99, -99, -99, -99
        else:
            makeCopy(temp_dir, cam_dir, final_filename)
            makeCopy(temp_dir, image_dir, final_filename)
            c_x, c_y, w, h = boundingBoxinfo(x1, y1, x2, y2)
            return c_x, c_x, c_y, w, h
        
    
# cam0 thread for pre detection + post detection + push data like functions
def cam0_thread():
    c_x, c_y, w, h = cam0()
    
    if c_x == -99:
        print("No Detection")
    else:
        filename = findLatestImageName(image_dir)
        pushData_API(torpedo_id, c_x, c_y, w, h, cam_id, filename)
        print("Data Pushed")
    
    
# infinte loop for system level application 
def main():
    while True:
        try:
            cam_thread = threading.Thread(target=cam0_thread)
            cam_thread.start()
            cam_thread.join()
            time.sleep(2)
        except Exception as e:
            print(e)
            break


if __name__ == "__main__":
    main()



