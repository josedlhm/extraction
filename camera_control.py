########################################################################
#
# Copyright (c) 2022, STEREOLABS.
#
# All rights reserved.
#
########################################################################

"""
    Original Stereolabs camera control sample,
    minimally adapted to:
      - Open an SVO/SVO2 if a path is passed as argv[1]
      - Support pause/resume (space) and single-step ('n')
    Everything else (keys, ROI, behavior) is unchanged.
"""

import sys
import cv2
import pyzed.sl as sl

# Global variable 
camera_settings = sl.VIDEO_SETTINGS.BRIGHTNESS
str_camera_settings = "BRIGHTNESS" 
step_camera_settings = 1
led_on = True 
selection_rect = sl.Rect()
select_in_progress = False
origin_rect = (-1,-1 )
paused = False  # added

# Function that handles mouse events when interacting with the OpenCV window.
def on_mouse(event,x,y,flags,param):
    global select_in_progress,selection_rect,origin_rect
    if event == cv2.EVENT_LBUTTONDOWN:
        origin_rect = (x, y)
        select_in_progress = True
    elif event == cv2.EVENT_LBUTTONUP:
        select_in_progress = False 
    elif event == cv2.EVENT_RBUTTONDOWN:
        select_in_progress = False 
        selection_rect = sl.Rect(0,0,0,0)
    
    if select_in_progress:
        selection_rect.x = min(x,origin_rect[0])
        selection_rect.y = min(y,origin_rect[1])
        selection_rect.width = abs(x-origin_rect[0])+1
        selection_rect.height = abs(y-origin_rect[1])+1

def main():
    global paused

    init = sl.InitParameters()

    # If an SVO/SVO2 path is provided, open it instead of a live camera
    if len(sys.argv) >= 2:
        svo_path = sys.argv[1]
        init.set_from_svo_file(svo_path)
        # better responsiveness when pausing/stepping SVO playback
        init.svo_real_time_mode = False

    cam = sl.Camera()
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print("Camera Open : "+repr(status)+". Exit program.")
        exit()
    
    runtime = sl.RuntimeParameters()
    mat = sl.Mat() 
    win_name = "Camera Control"
    cv2.namedWindow(win_name)
    cv2.setMouseCallback(win_name,on_mouse)
    print_camera_information(cam)
    print_help()
    switch_camera_settings()
    key = ''
    last_frame = None

    while key != 113:  # for 'q' key
        # grab when not paused; if paused we keep showing last frame
        if not paused:
            err = cam.grab(runtime) 
            if err <= sl.ERROR_CODE.SUCCESS: # Check that a new image is successfully acquired
                cam.retrieve_image(mat, sl.VIEW.LEFT) # Retrieve left image
                cvImage = mat.get_data() # Convert sl.Mat to cv2.Mat
                last_frame = cvImage
                if (not selection_rect.is_empty() and selection_rect.is_contained(sl.Rect(0,0,cvImage.shape[1],cvImage.shape[0]))): #Check if selection rectangle is valid and draw it on the image
                    cv2.rectangle(cvImage,(selection_rect.x,selection_rect.y),(selection_rect.width+selection_rect.x,selection_rect.height+selection_rect.y),(220, 180, 20), 2)
                cv2.imshow(win_name, cvImage) #Display image
            else:
                print("Error during capture : ", err)
                break
        else:
            # paused: keep showing the last frame if we have one
            if last_frame is not None:
                show = last_frame.copy()
                if (not selection_rect.is_empty() and selection_rect.is_contained(sl.Rect(0,0,show.shape[1],show.shape[0]))):
                    cv2.rectangle(show,(selection_rect.x,selection_rect.y),(selection_rect.width+selection_rect.x,selection_rect.height+selection_rect.y),(220, 180, 20), 2)
                cv2.imshow(win_name, show)

        key = (cv2.waitKey(5) & 0xFF)

        # space toggles pause/resume
        if key == 32:  # space
            paused = not paused
            print("[Sample] Pause =", paused)
            continue

        # 'n' steps one frame forward while paused (does not unpause)
        if key == 110 and paused:  # 'n'
            err = cam.grab(runtime)
            if err <= sl.ERROR_CODE.SUCCESS:
                cam.retrieve_image(mat, sl.VIEW.LEFT)
                cvImage = mat.get_data()
                last_frame = cvImage
                if (not selection_rect.is_empty() and selection_rect.is_contained(sl.Rect(0,0,cvImage.shape[1],cvImage.shape[0]))):
                    cv2.rectangle(cvImage,(selection_rect.x,selection_rect.y),(selection_rect.width+selection_rect.x,selection_rect.height+selection_rect.y),(220, 180, 20), 2)
                cv2.imshow(win_name, cvImage)
            else:
                print("Error during capture : ", err)
            continue

        # Change camera settings with keyboard
        update_camera_settings(key, cam, runtime, mat)

    cv2.destroyAllWindows()
    cam.close()

# Display camera information
def print_camera_information(cam):
    cam_info = cam.get_camera_information()
    print("ZED Model                 : {0}".format(cam_info.camera_model))
    print("ZED Serial Number         : {0}".format(cam_info.serial_number))
    print("ZED Camera Firmware       : {0}/{1}".format(cam_info.camera_configuration.firmware_version,cam_info.sensors_configuration.firmware_version))
    print("ZED Camera Resolution     : {0}x{1}".format(round(cam_info.camera_configuration.resolution.width, 2), cam.get_camera_information().camera_configuration.resolution.height))
    print("ZED Camera FPS            : {0}".format(int(cam_info.camera_configuration.fps)))

# Print help
def print_help():
    print("\n\nCamera controls hotkeys:")
    print("* Increase camera settings value:  '+'")
    print("* Decrease camera settings value:  '-'")
    print("* Toggle camera settings:          's'")
    print("* Toggle camera LED:               'l' (lower L)")
    print("* Reset all parameters:            'r'")
    print("* Reset exposure ROI to full image 'f'")
    print("* Use mouse to select an image area to apply exposure (press 'a')")
    print("* Pause / resume playback:         'space'")
    print("* Step forward one frame:          'n'")
    print("* Exit :                           'q'\n")

# update camera setting on key press
def update_camera_settings(key, cam, runtime, mat):
    global led_on
    if key == 115:  # for 's' key
        # Switch camera settings
        switch_camera_settings()
    elif key == 43:  # for '+' key
        # Increase camera settings value.
        current_value = cam.get_camera_settings(camera_settings)[1]
        cam.set_camera_settings(camera_settings, current_value + step_camera_settings)
        print(str_camera_settings + ": " + str(current_value + step_camera_settings))
    elif key == 45:  # for '-' key
        # Decrease camera settings value.
        current_value = cam.get_camera_settings(camera_settings)[1]
        if current_value >= 1:
            cam.set_camera_settings(camera_settings, current_value - step_camera_settings)
            print(str_camera_settings + ": " + str(current_value - step_camera_settings))
    elif key == 114:  # for 'r' key
        # Reset all camera settings to default.
        cam.set_camera_settings(sl.VIDEO_SETTINGS.BRIGHTNESS, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.CONTRAST, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.HUE, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.SATURATION, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.SHARPNESS, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.GAIN, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE, -1)
        print("[Sample] Reset all settings to default")
    elif key == 108: # for 'l' key
        # Turn on or off camera LED.
        led_on = not led_on
        cam.set_camera_settings(sl.VIDEO_SETTINGS.LED_STATUS, led_on)
    elif key == 97 : # for 'a' key 
        # Set exposure region of interest (ROI) on a target area.
        print("[Sample] set AEC_AGC_ROI on target [",selection_rect.x,",",selection_rect.y,",",selection_rect.width,",",selection_rect.height,"]")
        cam.set_camera_settings_roi(sl.VIDEO_SETTINGS.AEC_AGC_ROI,selection_rect,sl.SIDE.BOTH)
    elif key == 102: #for 'f' key 
        # Reset exposure ROI to full resolution.
        print("[Sample] reset AEC_AGC_ROI to full res")
        cam.set_camera_settings_roi(sl.VIDEO_SETTINGS.AEC_AGC_ROI,selection_rect,sl.SIDE.BOTH,True)

# Function to switch between different camera settings (brightness, contrast, etc.).
def switch_camera_settings():
    global camera_settings
    global str_camera_settings
    if camera_settings == sl.VIDEO_SETTINGS.BRIGHTNESS:
        camera_settings = sl.VIDEO_SETTINGS.CONTRAST
        str_camera_settings = "Contrast"
        print("[Sample] Switch to camera settings: CONTRAST")
    elif camera_settings == sl.VIDEO_SETTINGS.CONTRAST:
        camera_settings = sl.VIDEO_SETTINGS.HUE
        str_camera_settings = "Hue"
        print("[Sample] Switch to camera settings: HUE")
    elif camera_settings == sl.VIDEO_SETTINGS.HUE:
        camera_settings = sl.VIDEO_SETTINGS.SATURATION
        str_camera_settings = "Saturation"
        print("[Sample] Switch to camera settings: SATURATION")
    elif camera_settings == sl.VIDEO_SETTINGS.SATURATION:
        camera_settings = sl.VIDEO_SETTINGS.SHARPNESS
        str_camera_settings = "Sharpness"
        print("[Sample] Switch to camera settings: Sharpness")
    elif camera_settings == sl.VIDEO_SETTINGS.SHARPNESS:
        camera_settings = sl.VIDEO_SETTINGS.GAIN
        str_camera_settings = "Gain"
        print("[Sample] Switch to camera settings: GAIN")
    elif camera_settings == sl.VIDEO_SETTINGS.GAIN:
        camera_settings = sl.VIDEO_SETTINGS.EXPOSURE
        str_camera_settings = "Exposure"
        print("[Sample] Switch to camera settings: EXPOSURE")
    elif camera_settings == sl.VIDEO_SETTINGS.EXPOSURE:
        camera_settings = sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE
        str_camera_settings = "White Balance"
        print("[Sample] Switch to camera settings: WHITEBALANCE")
    elif camera_settings == sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE:
        camera_settings = sl.VIDEO_SETTINGS.BRIGHTNESS
        str_camera_settings = "Brightness"
        print("[Sample] Switch to camera settings: BRIGHTNESS")


if __name__ == "__main__":
    main()
