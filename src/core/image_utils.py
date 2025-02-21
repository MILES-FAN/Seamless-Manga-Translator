import cv2
import numpy as np
from PIL import Image
from PyQt5.QtGui import QImage

def qimage_to_cv(qimg):
    """将 QImage 转换为 OpenCV 图像"""
    qimg = qimg.convertToFormat(QImage.Format_RGB888)
    width = qimg.width()
    height = qimg.height()
    
    bytes_per_line = qimg.bytesPerLine()
    ptr = qimg.bits()
    ptr.setsize(height * bytes_per_line)
    
    arr = np.array(ptr).reshape(height, bytes_per_line)
    arr = arr[:, :width*3].reshape(height, width, 3)
    
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def cv_to_qimage(img):
    """将 OpenCV 图像转换为 QImage"""
    height, width, channel = img.shape
    bytes_per_line = 3 * width
    return QImage(img.data, width, height, bytes_per_line,
                 QImage.Format_RGB888).rgbSwapped()

def pil_to_cv(pil_image):
    """将 PIL Image 转换为 OpenCV 图像"""
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

def cv_to_pil(cv_image):
    """将 OpenCV 图像转换为 PIL Image"""
    return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)) 