from .translations import TRANSLATIONS, LANGUAGE_CODES

class LanguageManager:
    def __init__(self):
        self.current_language = 'zh_CN'  # 默认语言
        
    def set_language(self, lang_code):
        """设置当前语言"""
        if lang_code in TRANSLATIONS:
            self.current_language = lang_code
            
    def get_text(self, key):
        """获取翻译文本"""
        try:
            # 如果是语言代码映射
            if key in LANGUAGE_CODES.get(self.current_language, {}):
                return TRANSLATIONS[self.current_language][LANGUAGE_CODES[self.current_language][key]]
            # 普通翻译文本
            return TRANSLATIONS[self.current_language][key]
        except KeyError:
            # 如果找不到翻译，返回英文或键名
            return TRANSLATIONS.get('en_US', {}).get(key, key) 