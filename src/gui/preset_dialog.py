from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                            QLineEdit, QPushButton, QComboBox,
                            QHBoxLayout)

class PresetDialog(QDialog):
    def __init__(self, parent=None, preset_data=None):
        super().__init__(parent)
        self.preset_data = preset_data
        self.lang_manager = parent.lang_manager  # 从父窗口获取语言管理器
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(self.lang_manager.get_text('preset_config'))
        self.setGeometry(150, 150, 720, 540)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 预设名称
        self.name_input = QLineEdit()
        if self.preset_data:
            self.name_input.setText(self.preset_data.get('name', ''))
        form.addRow(self.lang_manager.get_text('preset_name') + ":", self.name_input)

        # API类型
        self.type_combo = QComboBox()
        self.type_combo.addItems(['Ollama', 'Remote API'])
        if self.preset_data:
            self.type_combo.setCurrentText(self.preset_data.get('type', 'Ollama'))
        form.addRow(self.lang_manager.get_text('api_type') + ":", self.type_combo)

        # API地址
        self.api_input = QLineEdit()
        if self.preset_data:
            self.api_input.setText(self.preset_data.get('api_url', ''))
        form.addRow(self.lang_manager.get_text('api_url') + ":", self.api_input)

        # 模型名称
        self.model_input = QLineEdit()
        if self.preset_data:
            self.model_input.setText(self.preset_data.get('model', ''))
        form.addRow(self.lang_manager.get_text('model_name') + ":", self.model_input)

        # Bearer Token
        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        if self.preset_data:
            self.token_input.setText(self.preset_data.get('bearer_token', ''))
        form.addRow("Bearer Token:", self.token_input)

        layout.addLayout(form)

        # 按钮
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(self.lang_manager.get_text('save'))
        cancel_button = QPushButton(self.lang_manager.get_text('cancel'))
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        layout.addLayout(buttons_layout)

    def get_preset_data(self):
        """获取预设数据"""
        return {
            'name': self.name_input.text(),
            'type': self.type_combo.currentText(),
            'api_url': self.api_input.text(),
            'model': self.model_input.text(),
            'bearer_token': self.token_input.text()
        } 