import cv2
import time

cap = cv2.VideoCapture(0)

while (1):
    ret, frame = cap.read()
    cv2.imshow('Capture', frame)

    if cv2.waitKey(1) & 0xFF == ord('c'):
        localtime = time.localtime(time.time())
        cv2.imwrite(str(localtime.tm_year) + str(localtime.tm_mon) + str(localtime.tm_mday) + '-' + \
                    str(localtime.tm_hour) + str(localtime.tm_min) + str(localtime.tm_sec) + '.png', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
