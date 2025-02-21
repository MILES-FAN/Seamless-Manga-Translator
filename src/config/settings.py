import os
import json

class SettingsManager:
    def __init__(self):
        self.config_path = os.path.expanduser('~/.config/manga_translator/settings.json')
        self.presets_path = os.path.expanduser('~/.config/manga_translator/presets.json')
        
        # 默认设置使用英文标识符
        self.settings = {
            'trans_mode': 'Ollama',
            'ollama_api': 'http://localhost:11434/api/chat',
            'ollama_model': 'qwen2.5:14b',
            'openai_api': 'https://api.siliconflow.cn/v1/chat/completions',
            'remote_model': 'Qwen/Qwen2.5-32B-Instruct',
            'bearer_token': '',
            'umiocr_api': 'http://localhost:1224/api/ocr',
            'source_lang': '日文',
            'target_lang': '中文',
            'interface_language': 'zh_CN'
        }
        
        # 默认preset
        self.default_presets = {
            'default': {
                'name': 'default',
                'type': 'Ollama',
                'api_url': 'http://localhost:11434/api/chat',
                'model': 'qwen2.5:14b',
                'bearer_token': ''
            },
            'openai-siliconflow': {
                'name': 'openai-siliconflow',
                'type': 'Remote API',
                'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
                'model': 'Qwen/Qwen2.5-32B-Instruct',
                'bearer_token': ''
            }
        }
        
        # 加载预设和设置
        self.load_presets()
        self.load_settings()

    def load_presets(self):
        """加载API预设"""
        try:
            os.makedirs(os.path.dirname(self.presets_path), exist_ok=True)
            if os.path.exists(self.presets_path):
                with open(self.presets_path, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
            else:
                self.presets = self.default_presets
                self.save_presets()
        except Exception as e:
            print(f"加载预设失败: {str(e)}")
            self.presets = self.default_presets

    def save_presets(self):
        """保存API预设"""
        try:
            with open(self.presets_path, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存预设失败: {str(e)}")

    def add_preset(self, preset_data):
        """添加新的API预设"""
        name = preset_data['name']
        self.presets[name] = preset_data
        self.save_presets()

    def update_preset(self, name, preset_data):
        """更新现有的API预设"""
        if name in self.presets:
            self.presets[name].update(preset_data)
            self.save_presets()

    def delete_preset(self, name):
        """删除API预设"""
        if name in self.presets and name != 'default':
            del self.presets[name]
            if self.settings['current_preset'] == name:
                self.settings['current_preset'] = 'default'
            self.save_presets()
            self.save_settings(self.settings)

    def get_preset(self, name):
        """获取指定的API预设"""
        return self.presets.get(name, self.presets['default'])

    def get_current_preset(self):
        """获取当前使用的API预设"""
        current_preset = self.settings.get('current_preset', 'default')
        return self.get_preset(current_preset)

    def load_settings(self):
        """加载设置"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
        except Exception as e:
            print(f"加载设置失败: {str(e)}")
        return self.settings

    def save_settings(self, settings):
        """保存设置"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {str(e)}") 