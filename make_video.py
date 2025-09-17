import cv2, glob 
frames = [cv2.rotate(cv2.imread(f), cv2.ROTATE_90_CLOCKWISE) for f in sorted(glob.glob("out/images/*.png"))]
h,w,_=frames[0].shape
out = cv2.VideoWriter("sequoia24.mp4", cv2.VideoWriter_fourcc('*mp4v',30,(w,h)))
[out.write(f) for f in frames]; out.release()