#!/usr/bin/env python3
# Interactive single-frame preview for ZED-like camera settings.
# - If you pass an image: uses that image.
# - If you pass an .svo/.svo2: grabs the first LEFT frame via pyzed, then closes the file.
# - Adjust with sliders; press 'p' to print SDK-ready values; 'w' to save JSON; 's' to save image.

import sys, json
from pathlib import Path
import cv2
import numpy as np

# ---------- Optional ZED frame extraction ----------
def load_frame_from_svo(svo_path: Path):
    try:
        import pyzed.sl as sl
    except Exception as e:
        print("[Error] pyzed not available; install ZED SDK & pyzed or pass a still image.")
        sys.exit(1)

    init = sl.InitParameters()
    # SDK 4.x style (preferred), else fallback to 3.x
    try:
        it = sl.InputType(); it.set_from_svo_file(str(svo_path))
        init.input = it
    except Exception:
        init.set_from_svo_file(str(svo_path))
    init.svo_real_time_mode = False

    cam = sl.Camera()
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print("[Error] cam.open failed:", status)
        sys.exit(1)

    runtime = sl.RuntimeParameters()
    mat = sl.Mat()
    # Grab first frame
    for _ in range(500):  # try a few times in case of initial delays
        if cam.grab(runtime) == sl.ERROR_CODE.SUCCESS:
            cam.retrieve_image(mat, sl.VIEW.LEFT)
            img = mat.get_data().copy()
            cam.close()
            return img
    cam.close()
    print("[Error] Could not retrieve a frame from SVO.")
    sys.exit(1)

# ---------- Image adjustment helpers (OpenCV) ----------
def apply_brightness_contrast(img_bgr, brightness, contrast_units):
    # contrast_units 0..100 -> alpha 1..3
    alpha = 1.0 + 0.02 * max(0, contrast_units)
    beta  = int(brightness)  # -100..100
    return cv2.convertScaleAbs(img_bgr, alpha=alpha, beta=beta)

def kelvin_to_rgb(kelvin):
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

def apply_wb_temperature(img_bgr, kelvin):
    rgb = kelvin_to_rgb(kelvin)
    scale = rgb / max(rgb[1], 1e-6)  # normalize to green for neutral pivot
    out = img_bgr.astype(np.float32)
    out[..., 2] *= scale[0]  # R
    out[..., 1] *= scale[1]  # G
    out[..., 0] *= scale[2]  # B
    return np.clip(out, 0, 255).astype(np.uint8)

def apply_hue_saturation(img_bgr, hue_units, sat_units):
    # hue_units -90..90 -> +/-180 degrees (OpenCV H is 0..179; ~2 deg/step)
    hue_shift_deg = int(hue_units * 2)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.int32)
    h, s, v = cv2.split(hsv)
    h = (h + hue_shift_deg // 2) % 180
    s = np.clip(s + sat_units, 0, 255)
    hsv = cv2.merge([h.astype(np.uint8), s.astype(np.uint8), v.astype(np.uint8)])
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

def apply_sharpness(img_bgr, sharp_units):
    # amount 0..3.0 for 0..60
    amount = 0.05 * max(0, sharp_units)
    if amount <= 1e-6:
        return img_bgr
    blur = cv2.GaussianBlur(img_bgr, (0, 0), 1.2)
    return cv2.addWeighted(img_bgr, 1.0 + amount, blur, -amount, 0)

def render(img0, params):
    img = img0.copy()
    # exposure/gain preview as extra brightness (rough approximation)
    extra_beta = int(params["EXPOSURE"] + 0.6 * params["GAIN"])
    img = apply_brightness_contrast(img, params["BRIGHTNESS"] + extra_beta, params["CONTRAST"])
    img = apply_wb_temperature(img, params["WHITEBALANCE_TEMPERATURE"])
    img = apply_hue_saturation(img, params["HUE"], params["SATURATION"])
    img = apply_sharpness(img, params["SHARPNESS"])
    return img

# ---------- Trackbar plumbing ----------
def tb_get_params():
    # Map trackbar positions back to SDK-like values
    return {
        "BRIGHTNESS": cv2.getTrackbarPos("Brightness", WIN) - 100,          # [-100..100]
        "CONTRAST":   cv2.getTrackbarPos("Contrast",   WIN),                # [0..100]
        "HUE":        cv2.getTrackbarPos("Hue",        WIN) - 90,           # [-90..90]
        "SATURATION": cv2.getTrackbarPos("Saturation", WIN) - 100,          # [-100..100]
        "SHARPNESS":  cv2.getTrackbarPos("Sharpness",  WIN),                # [0..60]
        "GAIN":       cv2.getTrackbarPos("Gain",       WIN),                # [0..100]
        "EXPOSURE":   cv2.getTrackbarPos("Exposure",   WIN),                # [0..100]
        "WHITEBALANCE_TEMPERATURE": 2000 + cv2.getTrackbarPos("WB_K", WIN)  # [2000..8000]
    }

def tb_init_defaults(defaults):
    cv2.createTrackbar("Brightness", WIN, defaults["BRIGHTNESS"] + 100, 200, lambda v: None)
    cv2.createTrackbar("Contrast",   WIN, defaults["CONTRAST"],          100, lambda v: None)
    cv2.createTrackbar("Hue",        WIN, defaults["HUE"] + 90,          180, lambda v: None)
    cv2.createTrackbar("Saturation", WIN, defaults["SATURATION"] + 100,  200, lambda v: None)
    cv2.createTrackbar("Sharpness",  WIN, defaults["SHARPNESS"],          60, lambda v: None)
    cv2.createTrackbar("Gain",       WIN, defaults["GAIN"],              100, lambda v: None)
    cv2.createTrackbar("Exposure",   WIN, defaults["EXPOSURE"],          100, lambda v: None)
    cv2.createTrackbar("WB_K",       WIN, defaults["WHITEBALANCE_TEMPERATURE"] - 2000, 6000, lambda v: None)

def print_sdk_snippet(params):
    import textwrap
    lines = [
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.BRIGHTNESS, {BRIGHTNESS})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.CONTRAST, {CONTRAST})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.HUE, {HUE})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.SATURATION, {SATURATION})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.SHARPNESS, {SHARPNESS})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.GAIN, {GAIN})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.EXPOSURE, {EXPOSURE})",
        "cam.set_camera_settings(sl.VIDEO_SETTINGS.WHITEBALANCE_TEMPERATURE, {WHITEBALANCE_TEMPERATURE})",
    ]
    print("\n[Use these with the ZED SDK]")
    print(textwrap.indent("\n".join(l.format(**params) for l in lines), "  "))
    print("\n[JSON]")
    print(json.dumps(params, indent=2))

# ---------- Main ----------
WIN = "Single-frame preview"

def main():
    if len(sys.argv) < 2:
        print("Usage: python preview_single_frame.py /path/to/image_or_recording.(png|jpg|svo|svo2)")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser().resolve()
    if not path.exists():
        print("[Error] Path does not exist:", path)
        sys.exit(1)

    # Load image
    if path.suffix.lower() in [".svo", ".svo2"]:
        img0 = load_frame_from_svo(path)
        print("[Info] Grabbed first frame from:", path)
    else:
        img0 = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img0 is None:
            print("[Error] Failed to read image:", path)
            sys.exit(1)
        print("[Info] Loaded image:", path)

    # Window + sliders
    cv2.namedWindow(WIN, cv2.WINDOW_AUTOSIZE)
    defaults = {
        "BRIGHTNESS": 0, "CONTRAST": 0, "HUE": 0, "SATURATION": 0,
        "SHARPNESS": 0, "GAIN": 0, "EXPOSURE": 0, "WHITEBALANCE_TEMPERATURE": 5500
    }
    tb_init_defaults(defaults)

    # Loop
    while True:
        params = tb_get_params()
        vis = render(img0, params)
        cv2.imshow(WIN, vis)
        k = cv2.waitKey(20) & 0xFF
        if k in (27, ord('q')):  # ESC or 'q'
            break
        elif k == ord('p'):
            print_sdk_snippet(params)
        elif k == ord('w'):
            out = {"sdk_version": "preview", "settings": params}
            Path("zed_settings.json").write_text(json.dumps(out, indent=2))
            print("[Saved] zed_settings.json")
        elif k == ord('s'):
            cv2.imwrite("preview.png", vis)
            print("[Saved] preview.png")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
