import base64
import cv2
import requests
from ..config.settings import SettingsManager
from ..i18n.language_manager import LanguageManager

def ocr_through_UmiOCR(img, source_lang):
    """通过UmiOCR进行OCR识别"""
    url = SettingsManager().load_settings().get('umiocr_api', 'http://localhost:1224/api/ocr')
    lang_manager = LanguageManager()

    # 将图像转换为 Base64
    _, encoded_img = cv2.imencode('.jpg', img)
    base64_img = base64.b64encode(encoded_img).decode('utf-8')

    # 语言到配置文件的映射（只需要内部标识符的映射）
    lang_config_map = {
        'Simplified Chinese': "models/config_chinese.txt",
        'Traditional Chinese': "models/config_chinese_cht.txt",
        'English': "models/config_en.txt",
        'Japanese': "models/config_japan.txt",
        'Korean': "models/config_korean.txt"
    }

    # 获取对应的配置文件
    model_config = lang_config_map.get(source_lang, "")
    if not model_config:
        # 如果找不到对应的配置，使用默认配置
        print(f"Warning: No OCR config found for language: {source_lang}")
        model_config = "models/config_chinese.txt"

    # 组织 JSON 请求数据
    data = {
        "base64": base64_img,
        "options": {
            "ocr.language": model_config,
        }
    }
    headers = {"Content-Type": "application/json"}

    # 发送请求
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()

def preprocess_image(img, min_size=800):
    """预处理图像"""
    if img.shape[0] < min_size or img.shape[1] < min_size:
        multiplier = min_size / min(img.shape[0], img.shape[1])
        img = cv2.resize(img, (0, 0), fx=multiplier, fy=multiplier, interpolation=cv2.INTER_LANCZOS4)
        img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
    return img 