########################################################################
#
# Copyright (c) 2022, STEREOLABS.
#
# All rights reserved.
#
########################################################################

"""
    Camera control sample adapted for SVO/SVO2 files.
    - Pause/play with spacebar
    - Step one frame forward with 'n'
    - ROI removed
"""

import sys
import cv2
import pyzed.sl as sl

# Global variables
camera_settings = sl.VIDEO_SETTINGS.BRIGHTNESS
str_camera_settings = "BRIGHTNESS"
step_camera_settings = 1
led_on = True
paused = False

def main():
    global paused

    if len(sys.argv) < 2:
        print("Usage: python camera_control_svo_pause.py /path/to/recording.svo2")
        exit(1)

    svo_path = sys.argv[1]

    init = sl.InitParameters()
    init.set_from_svo_file(svo_path)
    init.svo_real_time_mode = False  # disable real-time so pause/step works better

    cam = sl.Camera()
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print("Camera Open : " + repr(status) + ". Exit program.")
        exit(1)

    runtime = sl.RuntimeParameters()
    mat = sl.Mat()
    win_name = "Camera Control (SVO)"
    cv2.namedWindow(win_name)

    print_camera_information(cam)
    print_help()
    switch_camera_settings()

    key = -1
    while key != 113:  # 'q'
        if not paused or key == 110:  # grab if playing, or stepping one frame ('n')
            err = cam.grab(runtime)
            if err == sl.ERROR_CODE.SUCCESS:
                cam.retrieve_image(mat, sl.VIEW.LEFT)
                cvImage = mat.get_data()
                cv2.imshow(win_name, cvImage)
            else:
                print("End of SVO or error during capture:", err)
                break

        key = cv2.waitKey(5)
        if key > 0:
            if key == 32:  # spacebar -> toggle pause
                paused = not paused
                print("[Sample] Pause =", paused)
            else:
                update_camera_settings(key, cam)

    cv2.destroyAllWindows()
    cam.close()

# Display camera/SVO information
def print_camera_information(cam):
    cam_info = cam.get_camera_information()
    print("ZED Model                 : {0}".format(cam_info.camera_model))
    print("ZED Serial Number         : {0}".format(cam_info.serial_number))
    print("ZED Camera Firmware       : {0}/{1}".format(
        cam_info.camera_configuration.firmware_version,
        cam_info.sensors_configuration.firmware_version))
    print("ZED Camera Resolution     : {0}x{1}".format(
        round(cam_info.camera_configuration.resolution.width, 2),
        cam_info.camera_configuration.resolution.height))
    print("ZED Camera FPS            : {0}".format(int(cam_info.camera_configuration.fps)))

# Print help
def print_help():
    print("\n\nCamera controls hotkeys:")
    print("* Increase camera settings value:  '+'")
    print("* Decrease camera settings value:  '-'")
    print("* Toggle camera settings:          's'")
    print("* Toggle camera LED:               'l' (lower L)")
    print("* Reset all parameters:            'r'")
    print("* Pause / resume playback:         spacebar")
    print("* Step forward one frame:          'n'")
    print("* Exit :                           'q'\n")

# Update camera setting on key press
def update_camera_settings(key, cam):
    global led_on
    if key == 115:  # 's'
        switch_camera_settings()
    elif key == 43:  # '+'
        current_value = cam.get_camera_settings(camera_settings)[1]
        cam.set_camera_settings(camera_settings, current_value + step_camera_settings)
        print(str_camera_settings + ": " + str(current_value + step_camera_settings))
    elif key == 45:  # '-'
        current_value = cam.get_camera_settings(camera_settings)[1]
        if current_value >= 1:
            cam.set_camera_settings(camera_settings, current_value - step_camera_settings)
            print(str_camera_settings + ": " + str(current_value - step_camera_settings))
    elif key == 114:  # 'r'
        cam.set_camera_settings(sl.VIDEO_SETTINGS.BRIGHTNESS, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.CONTRAST, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.HUE, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.SATURATION, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.SHARPNESS, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.GAIN, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE, -1)
        cam.set_camera_settings(sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE, -1)
        print("[Sample] Reset all settings to default")
    elif key == 108:  # 'l'
        led_on = not led_on
        cam.set_camera_settings(sl.VIDEO_SETTINGS.LED_STATUS, led_on)

# Cycle through settings
def switch_camera_settings():
    global camera_settings, str_camera_settings
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
