########################################################################
# STEREOLABS sample, minimally adapted:
# - If argv[1] is an SVO/SVO2, open it and apply settings in software (post-process)
# - If no arg, open live camera and use SDK camera settings as before
# - Normalize key reads (& 0xFF) so 's', '+', '-' work reliably
########################################################################

import sys
import os
from pathlib import Path
import cv2
import numpy as np
import pyzed.sl as sl

# Globals (unchanged names)
camera_settings = sl.VIDEO_SETTINGS.BRIGHTNESS
str_camera_settings = "BRIGHTNESS"
step_camera_settings = 1
led_on = True
selection_rect = sl.Rect()
select_in_progress = False
origin_rect = (-1, -1)

# Playback mode flag + software "registers" for SVO
is_playback = False
proc_vals = {
    "BRIGHTNESS": 0,                  # [-100..100] beta
    "CONTRAST": 0,                    # [0..100] maps to alpha=1+0.02*v
    "HUE": 0,                         # [-90..90] -> +/-180 deg
    "SATURATION": 0,                  # [-100..100]
    "SHARPNESS": 0,                   # [0..60] amount=0.05*v
    "GAIN": 0,                        # extra brightness-ish
    "EXPOSURE": 0,                    # extra brightness-ish
    "WHITEBALANCE_TEMPERATURE": 5500  # Kelvin
}

# --- Helpers for SVO software adjustments ---
def _apply_brightness_contrast(img, brightness, contrast_units):
    alpha = 1.0 + 0.02 * max(0, contrast_units)  # 0..100 -> 1..3
    beta = int(brightness)
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

def _apply_hue_saturation(img, hue_units, sat_units):
    hue_shift_deg = int(hue_units * 2)  # +/-180 deg
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.int32)
    h, s, v = cv2.split(hsv)
    h = (h + hue_shift_deg // 2) % 180
    s = np.clip(s + sat_units, 0, 255)
    hsv = cv2.merge([h.astype(np.uint8), s.astype(np.uint8), v.astype(np.uint8)])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def _apply_sharpness(img, sharp_units):
    amount = 0.05 * max(0, sharp_units)  # 0..3.0
    if amount <= 1e-6: return img
    blur = cv2.GaussianBlur(img, (0, 0), 1.2)
    return cv2.addWeighted(img, 1.0 + amount, blur, -amount, 0)

def _kelvin_to_rgb(kelvin):
    k = float(np.clip(kelvin, 1000, 12000)) / 100.0
    if k <= 66: r = 255.0
    else:
        r = 329.698727446 * ((k - 60.0) ** -0.1332047592)
        r = np.clip(r, 0.0, 255.0)
    if k <= 66: g = 99.4708025861 * np.log(k) - 161.1195681661
    else:       g = 288.1221695283 * ((k - 60.0) ** -0.0755148492)
    g = np.clip(g, 0.0, 255.0)
    if k >= 66: b = 255.0
    elif k <= 19: b = 0.0
    else:
        b = 138.5177312231 * np.log(k - 10.0) - 305.0447927307
        b = np.clip(b, 0.0, 255.0)
    return np.array([r, g, b], dtype=np.float32) / 255.0

def _apply_wb_temperature(img, kelvin):
    rgb = _kelvin_to_rgb(kelvin)
    scale = rgb / max(rgb[1], 1e-6)  # normalize to green
    out = img.astype(np.float32)
    out[..., 2] *= scale[0]  # R
    out[..., 1] *= scale[1]  # G
    out[..., 0] *= scale[2]  # B
    return np.clip(out, 0, 255).astype(np.uint8)

def apply_svo_pipeline(img):
    # combine EXPOSURE/GAIN as extra brightness; keep mapping simple
    extra_beta = int(proc_vals["EXPOSURE"] + 0.6 * proc_vals["GAIN"])
    img = _apply_brightness_contrast(img, proc_vals["BRIGHTNESS"] + extra_beta, proc_vals["CONTRAST"])
    img = _apply_wb_temperature(img, proc_vals["WHITEBALANCE_TEMPERATURE"])
    img = _apply_hue_saturation(img, proc_vals["HUE"], proc_vals["SATURATION"])
    img = _apply_sharpness(img, proc_vals["SHARPNESS"])
    return img

# Mouse callback (unchanged)
def on_mouse(event, x, y, flags, param):
    global select_in_progress, selection_rect, origin_rect
    if event == cv2.EVENT_LBUTTONDOWN:
        origin_rect = (x, y); select_in_progress = True
    elif event == cv2.EVENT_LBUTTONUP:
        select_in_progress = False
    elif event == cv2.EVENT_RBUTTONDOWN:
        select_in_progress = False; selection_rect = sl.Rect(0, 0, 0, 0)
    if select_in_progress:
        selection_rect.x = min(x, origin_rect[0])
        selection_rect.y = min(y, origin_rect[1])
        selection_rect.width  = abs(x - origin_rect[0]) + 1
        selection_rect.height = abs(y - origin_rect[1]) + 1

def main():
    global is_playback
    init = sl.InitParameters()

    # If a path is provided, open SVO/SVO2
    if len(sys.argv) >= 2:
        p = Path(sys.argv[1]).expanduser().resolve()
        if not p.exists():
            print("[Error] SVO path does not exist:", p); sys.exit(1)
        try:
            it = sl.InputType(); it.set_from_svo_file(str(p))
            init.input = it
        except Exception:
            init.set_from_svo_file(str(p))
        init.svo_real_time_mode = False
        is_playback = True

    cam = sl.Camera()
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print("Camera Open :", repr(status), ". Exit."); sys.exit(1)

    runtime = sl.RuntimeParameters()
    mat = sl.Mat()
    win_name = "Camera Control"
    cv2.namedWindow(win_name)
    cv2.setMouseCallback(win_name, on_mouse)
    print_camera_information(cam)
    print_help()
    switch_camera_settings()

    key = ''
    while key != 113:  # 'q'
        err = cam.grab(runtime)
        if err == sl.ERROR_CODE.SUCCESS:
            cam.retrieve_image(mat, sl.VIEW.LEFT)
            frame = mat.get_data()
            # Draw ROI box (visual only)
            if (not selection_rect.is_empty() and
                selection_rect.is_contained(sl.Rect(0, 0, frame.shape[1], frame.shape[0]))):
                cv2.rectangle(frame,
                              (selection_rect.x, selection_rect.y),
                              (selection_rect.x + selection_rect.width, selection_rect.y + selection_rect.height),
                              (220, 180, 20), 2)
            # If playback, apply software adjustments so +/− have visible effect
            if is_playback:
                disp = apply_svo_pipeline(frame.copy())
            else:
                disp = frame
            cv2.imshow(win_name, disp)
        elif err == sl.ERROR_CODE.END_OF_SVOFILE_REACHED:
            print("[Info] End of SVO reached."); break
        else:
            print("Error during capture:", err); break

        key = cv2.waitKey(5) & 0xFF  # normalize keycode
        update_camera_settings(key, cam, runtime, mat)

    cv2.destroyAllWindows()
    cam.close()

# Display camera information (unchanged)
def print_camera_information(cam):
    cam_info = cam.get_camera_information()
    print("ZED Model                 : {0}".format(cam_info.camera_model))
    print("ZED Serial Number         : {0}".format(cam_info.serial_number))
    print("ZED Camera Firmware       : {0}/{1}".format(cam_info.camera_configuration.firmware_version,
                                                      cam_info.sensors_configuration.firmware_version))
    print("ZED Camera Resolution     : {0}x{1}".format(round(cam_info.camera_configuration.resolution.width, 2),
                                                        cam.get_camera_information().camera_configuration.resolution.height))
    print("ZED Camera FPS            : {0}".format(int(cam_info.camera_configuration.fps)))

# Print help (unchanged text)
def print_help():
    print("\n\nCamera controls hotkeys:")
    print("* Increase camera settings value:  '+'")
    print("* Decrease camera settings value:  '-'")
    print("* Toggle camera settings:          's'")
    print("* Toggle camera LED:               'l' (lower L)")
    print("* Reset all parameters:            'r'")
    print("* Reset exposure ROI to full image 'f'")
    print("* Use mouse to select an image area to apply exposure (press 'a')")
    print("* Exit :                           'q'\n")

# Key handling
def update_camera_settings(key, cam, runtime, mat):
    global led_on
    if key == 115:  # 's' -> switch which setting you're editing
        switch_camera_settings()

    elif key == 43:  # '+'
        if is_playback:
            _inc_proc(1)
        else:
            err, current_value = cam.get_camera_settings(camera_settings)
            # -1 (auto) -> 0 on first +, then step
            new_value = 0 if current_value < 0 else current_value + step_camera_settings
            cam.set_camera_settings(camera_settings, new_value)
            print(str_camera_settings + ": " + str(new_value))

    elif key == 45:  # '-'
        if is_playback:
            _inc_proc(-1)
        else:
            err, current_value = cam.get_camera_settings(camera_settings)
            # down to 0 then back to -1 (auto)
            new_value = -1 if current_value <= 0 else current_value - step_camera_settings
            cam.set_camera_settings(camera_settings, new_value)
            print(str_camera_settings + ": " + str(new_value))

    elif key == 114:  # 'r' -> reset to defaults/auto
        if is_playback:
            proc_vals.update({
                "BRIGHTNESS": 0, "CONTRAST": 0, "HUE": 0, "SATURATION": 0,
                "SHARPNESS": 0, "GAIN": 0, "EXPOSURE": 0, "WHITEBALANCE_TEMPERATURE": 5500
            })
            print("[Sample] Reset all (software) settings to default")
        else:
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
        if not is_playback:
            cam.set_camera_settings(sl.VIDEO_SETTINGS.LED_STATUS, led_on)

    elif key == 97:  # 'a' (ROI) / 102 'f' (reset ROI) -> SDK only; in playback, just print
        if key == 97:
            print("[Sample] set AEC_AGC_ROI on target [",
                  selection_rect.x, ",", selection_rect.y, ",",
                  selection_rect.width, ",", selection_rect.height, "]")
            if not is_playback:
                cam.set_camera_settings_roi(sl.VIDEO_SETTINGS.AEC_AGC_ROI, selection_rect, sl.SIDE.BOTH)
        else:  # 102 = 'f'
            print("[Sample] reset AEC_AGC_ROI to full res")
            if not is_playback:
                cam.set_camera_settings_roi(sl.VIDEO_SETTINGS.AEC_AGC_ROI, selection_rect, sl.SIDE.BOTH, True)

# Map current setting name -> adjust software register and print
def _inc_proc(delta):
    name = str_camera_settings.upper().replace(" ", "_")
    if name not in proc_vals:
        return
    # coarse clamping similar to SDK ranges
    bounds = {
        "BRIGHTNESS": (-100, 100),
        "CONTRAST":   (0, 100),
        "HUE":        (-90, 90),
        "SATURATION": (-100, 100),
        "SHARPNESS":  (0, 60),
        "GAIN":       (0, 100),
        "EXPOSURE":   (0, 100),
        "WHITEBALANCE_TEMPERATURE": (2000, 8000)
    }
    lo, hi = bounds[name]
    val0 = proc_vals[name]
    val1 = int(np.clip(val0 + delta * step_camera_settings, lo, hi))
    proc_vals[name] = val1
    print(str_camera_settings + ": " + str(val1))

# Cycle settings (unchanged)
def switch_camera_settings():
    global camera_settings, str_camera_settings
    if camera_settings == sl.VIDEO_SETTINGS.BRIGHTNESS:
        camera_settings = sl.VIDEO_SETTINGS.CONTRAST; str_camera_settings = "Contrast"
        print("[Sample] Switch to camera settings: CONTRAST")
    elif camera_settings == sl.VIDEO_SETTINGS.CONTRAST:
        camera_settings = sl.VIDEO_SETTINGS.HUE; str_camera_settings = "Hue"
        print("[Sample] Switch to camera settings: HUE")
    elif camera_settings == sl.VIDEO_SETTINGS.HUE:
        camera_settings = sl.VIDEO_SETTINGS.SATURATION; str_camera_settings = "Saturation"
        print("[Sample] Switch to camera settings: SATURATION")
    elif camera_settings == sl.VIDEO_SETTINGS.SATURATION:
        camera_settings = sl.VIDEO_SETTINGS.SHARPNESS; str_camera_settings = "Sharpness"
        print("[Sample] Switch to camera settings: Sharpness")
    elif camera_settings == sl.VIDEO_SETTINGS.SHARPNESS:
        camera_settings = sl.VIDEO_SETTINGS.GAIN; str_camera_settings = "Gain"
        print("[Sample] Switch to camera settings: GAIN")
    elif camera_settings == sl.VIDEO_SETTINGS.GAIN:
        camera_settings = sl.VIDEO_SETTINGS.EXPOSURE; str_camera_settings = "Exposure"
        print("[Sample] Switch to camera settings: EXPOSURE")
    elif camera_settings == sl.VIDEO_SETTINGS.EXPOSURE:
        camera_settings = sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE; str_camera_settings = "White Balance"
        print("[Sample] Switch to camera settings: WHITEBALANCE")
    elif camera_settings == sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE:
        camera_settings = sl.VIDEO_SETTINGS.BRIGHTNESS; str_camera_settings = "Brightness"
        print("[Sample] Switch to camera settings: BRIGHTNESS")

if __name__ == "__main__":
    main()
