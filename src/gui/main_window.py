from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, 
                            QComboBox, QFormLayout, QLineEdit, QPushButton,
                            QFileDialog, QApplication, QHBoxLayout, QTabWidget, QTextEdit, QScrollArea)
from PyQt5.QtCore import QThread, QMutex, QWaitCondition, QRect, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
import cv2
import threading
from src.core.translation import TranslationThread
from src.core.image_utils import qimage_to_cv
from src.config.settings import SettingsManager
from src.gui.result_window_webview import ResultWindowWebview
from src.server.image_server import ImageServer
from src.gui.preset_dialog import PresetDialog
from src.i18n.language_manager import LanguageManager
from PyQt5.QtCore import QLocale
from src.core.web_scraper import WebScraper
import time

# 修改CrawlerWorkerThread类
class CrawlerWorkerThread(QThread):
    progress = pyqtSignal(int, int)  # current, total
    status = pyqtSignal(str, dict)   # status, data
    image_ready = pyqtSignal(object, str)  # image, description
    error = pyqtSignal(str)          # error message
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        self.is_running = True
    
    def run(self):
        try:
            def progress_callback(current, total):
                if self.is_running:
                    self.progress.emit(current, total)
            
            def status_callback(status, data=None):
                if self.is_running:
                    self.status.emit(status, data or {})
            
            def image_callback(image, description):
                if self.is_running:
                    self.image_ready.emit(image, description)
            
            WebScraper.get_images_from_webpage(
                self.url,
                image_callback=image_callback,
                progress_callback=progress_callback,
                status_callback=status_callback
            )
            
        except Exception as e:
            if self.is_running:
                self.error.emit(str(e))
    
    def stop(self):
        self.is_running = False

class MangaTranslator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        self.lang_manager = LanguageManager()
        
        # 获取系统语言
        system_locale = QLocale.system().name()  # 例如: 'zh_CN', 'en_US', 'ja_JP'
        
        # 如果是第一次运行（没有保存的界面语言设置）
        if 'interface_language' not in self.settings:
            # 映射系统语言到支持的语言代码
            locale_map = {
                'zh_CN': 'zh_CN',
                'zh_TW': 'zh_TW',
                'zh_HK': 'zh_TW',
                'ko_KR': 'ko_KR',
                'ja_JP': 'ja_JP',
                'en_US': 'en_US',
                'en_GB': 'en_US',
            }
            
            # 获取匹配的语言代码，默认为中文
            interface_lang = locale_map.get(system_locale, 'zh_CN')
            self.settings['interface_language'] = interface_lang
            
            # 设置对应的目标语言
            target_lang_map = {
                'zh_CN': 'Simplified Chinese',
                'zh_TW': 'Traditional Chinese',
                'ko_KR': 'Korean',
                'ja_JP': 'Japanese',
                'en_US': 'English'
            }
            self.settings['target_lang'] = target_lang_map.get(interface_lang, 'Simplified Chinese')
            
            # 保存设置
            self.settings_manager.save_settings(self.settings)
        
        # 设置界面语言
        self.lang_manager.set_language(self.settings.get('interface_language', 'zh_CN'))
        
        # 初始化UI
        self.init_ui()
        
        # 使用新的 ResultWindowWebview
        self.result_window = ResultWindowWebview()
        self.result_window.window_closed.connect(self.handle_result_window_closed)
        self.result_window.show()
        
        self.setup_processing_queue()
        self.setup_clipboard_monitoring()
        self.setup_image_server()
        self.processing_count = 0
        self.processed_hashes = set()
        self.crawler_status_list = []
        self.max_status_records = 100  # 最大记录数量
        self.crawler_worker = None

    def setup_processing_queue(self):
        self.worker = None
        self.queue = []
        self.queue_mutex = QMutex()
        self.queue_condition = QWaitCondition()
        self.processing_thread = QThread()
        self.processing_thread.run = self.process_queue
        self.processing_thread.start()
        self.last_image_data = None

    def setup_clipboard_monitoring(self):
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)

    def setup_image_server(self):
        self.image_server = ImageServer(self)
        threading.Thread(target=self.image_server.run, daemon=True).start()

    def init_ui(self):
        self.setWindowTitle(self.lang_manager.get_text('window_title'))
        #self.setGeometry(100, 100, 800, 600)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # API Configuration Section
        api_config_label = QLabel(self.lang_manager.get_text('api_config'))
        api_config_label.original_text = 'api_config'  # 添加原始文本标识
        main_layout.addWidget(api_config_label)
        
        # Preset Selection
        preset_form = QFormLayout()
        preset_label = QLabel(self.lang_manager.get_text('preset') + ":")
        preset_label.original_text = 'preset'
        self.preset_combo = QComboBox()
        self.update_preset_list()
        self.preset_combo.currentTextChanged.connect(self.on_preset_changed)
        preset_form.addRow(preset_label, self.preset_combo)
        
        # Preset Management Buttons
        preset_buttons = QHBoxLayout()
        self.btn_add_preset = QPushButton(self.lang_manager.get_text('add_preset'))
        self.btn_edit_preset = QPushButton(self.lang_manager.get_text('edit_preset'))
        self.btn_delete_preset = QPushButton(self.lang_manager.get_text('delete_preset'))
        self.btn_copy_preset = QPushButton(self.lang_manager.get_text('copy_preset'))
        
        preset_buttons.addWidget(self.btn_add_preset)
        preset_buttons.addWidget(self.btn_edit_preset)
        preset_buttons.addWidget(self.btn_delete_preset)
        preset_buttons.addWidget(self.btn_copy_preset)
        
        # Connect preset buttons
        self.btn_add_preset.clicked.connect(self.add_preset)
        self.btn_edit_preset.clicked.connect(self.edit_preset)
        self.btn_delete_preset.clicked.connect(self.delete_preset)
        self.btn_copy_preset.clicked.connect(self.copy_preset)
        
        # Add preset management to layout
        preset_widget = QWidget()
        preset_widget.setLayout(preset_form)
        main_layout.addWidget(preset_widget)
        
        buttons_widget = QWidget()
        buttons_widget.setLayout(preset_buttons)
        main_layout.addWidget(buttons_widget)

        # Language Settings Section
        lang_settings_label = QLabel(self.lang_manager.get_text('language_settings'))
        lang_settings_label.original_text = 'language_settings'
        main_layout.addWidget(lang_settings_label)
        
        # 界面语言选择
        interface_lang_form = QFormLayout()
        interface_lang_label = QLabel(self.lang_manager.get_text('interface_language') + ":")
        interface_lang_label.original_text = 'interface_language'
        self.interface_lang_combo = QComboBox()
        self.interface_lang_combo.addItems(['简体中文', '繁體中文', '한국어', '日本語', 'English'])
        self.interface_lang_combo.currentTextChanged.connect(self.change_language)
        
        # 设置当前界面语言
        lang_map = {
            'zh_CN': '简体中文',
            'zh_TW': '繁體中文',
            'ko_KR': '한국어',
            'ja_JP': '日本語',
            'en_US': 'English'
        }
        current_lang = self.settings.get('interface_language', 'zh_CN')
        self.interface_lang_combo.setCurrentText(lang_map.get(current_lang, '简体中文'))
        interface_lang_form.addRow(interface_lang_label, self.interface_lang_combo)
        
        # 翻译语言选择
        lang_form = QFormLayout()
        
        # 源语言标签和下拉框
        source_lang_label = QLabel(self.lang_manager.get_text('source_lang') + ":")
        source_lang_label.original_text = 'source_lang'
        self.source_lang_combo = QComboBox()
        
        # 使用内部英文标识符作为数据
        source_languages = [
            ('Japanese', self.lang_manager.get_text('lang_japanese')),
            ('Korean', self.lang_manager.get_text('lang_korean')),
            ('Simplified Chinese', self.lang_manager.get_text('lang_chinese_simple')),
            ('Traditional Chinese', self.lang_manager.get_text('lang_chinese_traditional')),
            ('English', self.lang_manager.get_text('lang_english'))
        ]
        
        for internal_name, display_name in source_languages:
            self.source_lang_combo.addItem(display_name, internal_name)
        
        # 设置当前选择
        current_source = self.settings.get('source_lang', 'Japanese')
        index = self.source_lang_combo.findData(current_source)
        if index >= 0:
            self.source_lang_combo.setCurrentIndex(index)
        
        # 目标语言标签和下拉框
        target_lang_label = QLabel(self.lang_manager.get_text('target_lang') + ":")
        target_lang_label.original_text = 'target_lang'
        self.target_lang_combo = QComboBox()
        
        target_languages = [
            ('Simplified Chinese', self.lang_manager.get_text('lang_chinese_simple')),
            ('Traditional Chinese', self.lang_manager.get_text('lang_chinese_traditional')),
            ('English', self.lang_manager.get_text('lang_english')),
            ('Japanese', self.lang_manager.get_text('lang_japanese')),
            ('Korean', self.lang_manager.get_text('lang_korean'))
        ]
        
        for internal_name, display_name in target_languages:
            self.target_lang_combo.addItem(display_name, internal_name)
        
        # 设置当前选择
        current_target = self.settings.get('target_lang', 'Simplified Chinese')
        index = self.target_lang_combo.findData(current_target)
        if index >= 0:
            self.target_lang_combo.setCurrentIndex(index)

        # 添加到表单布局
        lang_form.addRow(source_lang_label, self.source_lang_combo)
        lang_form.addRow(target_lang_label, self.target_lang_combo)

        # Add language forms to main layout
        lang_widget = QWidget()
        lang_widget.setLayout(interface_lang_form)
        main_layout.addWidget(lang_widget)
        
        trans_lang_widget = QWidget()
        trans_lang_widget.setLayout(lang_form)
        main_layout.addWidget(trans_lang_widget)

        # 文字排版方向选择
        direction_form = QFormLayout()
        direction_label = QLabel(self.lang_manager.get_text('text_direction') + ":")
        direction_label.original_text = 'text_direction'
        
        self.direction_combo = QComboBox()
        direction_options = [
            ('horizontal', self.lang_manager.get_text('direction_horizontal')),
            ('vertical', self.lang_manager.get_text('direction_vertical'))
        ]
        
        for internal_name, display_name in direction_options:
            self.direction_combo.addItem(display_name, internal_name)
        
        # 设置当前选择
        current_direction = self.settings.get('text_direction', 'horizontal')
        index = self.direction_combo.findData(current_direction)
        if index >= 0:
            self.direction_combo.setCurrentIndex(index)
            
        direction_form.addRow(direction_label, self.direction_combo)
        main_layout.addLayout(direction_form)
        
        # 连接信号
        self.direction_combo.currentIndexChanged.connect(self.save_settings)

        # Operation Buttons
        main_layout.addWidget(QLabel(self.lang_manager.get_text('operations')))
        
        self.btn_open = QPushButton(self.lang_manager.get_text('open_image'))
        self.btn_paste = QPushButton(self.lang_manager.get_text('paste_clipboard'))
        self.btn_clear = QPushButton(self.lang_manager.get_text('clear_all'))
        self.btn_stop = QPushButton(self.lang_manager.get_text('stop_task'))

        self.btn_open.clicked.connect(self.open_image)
        self.btn_paste.clicked.connect(self.paste_image)
        self.btn_clear.clicked.connect(self.clear_results)
        self.btn_stop.clicked.connect(self.stop_current_task)

        main_layout.addWidget(self.btn_open)
        main_layout.addWidget(self.btn_paste)
        main_layout.addWidget(self.btn_clear)
        main_layout.addWidget(self.btn_stop)

        # Status
        main_layout.addWidget(QLabel(self.lang_manager.get_text('status')))
        self.status_label = QLabel(self.lang_manager.get_text('waiting'))
        main_layout.addWidget(self.status_label)

        # Add stretch at the bottom
        main_layout.addStretch()

        # 在上传部分创建标签页
        upload_tabs = QTabWidget()
        web_tab = QWidget()
        crawler_tab_widget = QWidget()
        
        # 网页抓取标签页
        web_layout = QVBoxLayout(web_tab)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(self.lang_manager.get_text('web_url'))
        
        fetch_button = QPushButton(self.lang_manager.get_text('fetch_process'))
        fetch_button.clicked.connect(self.fetch_from_webpage)
        
        web_layout.addWidget(self.url_input)
        web_layout.addWidget(fetch_button)
        web_layout.addStretch()
        
        # 爬虫任务标签页 - 修改布局
        crawler_layout = QVBoxLayout(crawler_tab_widget)
        
        # 创建一个滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)  # 设置最小高度
        scroll_area.setMaximumHeight(500)  # 设置最大高度
        
        # 添加状态列表显示
        self.crawler_status_text = QTextEdit()
        self.crawler_status_text.setReadOnly(True)
        self.crawler_status_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                font-family: Consolas, Monaco, monospace;
                font-size: 14px;  /* 增大字体 */
                line-height: 1.5;  /* 增加行间距 */
                padding: 10px;
            }
        """)
        
        # 将文本编辑器添加到滚动区域
        scroll_area.setWidget(self.crawler_status_text)
        crawler_layout.addWidget(scroll_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        # 清除按钮
        clear_status_button = QPushButton(self.lang_manager.get_text('clear_all'))
        clear_status_button.clicked.connect(self.clear_crawler_status)
        button_layout.addWidget(clear_status_button)
        
        # 添加按钮布局
        crawler_layout.addLayout(button_layout)
        
        # 添加标签页
        upload_tabs.addTab(web_tab, self.lang_manager.get_text('web_scraper'))
        upload_tabs.addTab(crawler_tab_widget, self.lang_manager.get_text('crawler_tasks'))
        
        # 将标签页添加到主布局
        main_layout.addWidget(upload_tabs)

        # Connect all signals
        self.connect_signals()

    def connect_signals(self):
        """连接所有信号"""
        self.preset_combo.currentTextChanged.connect(self.update_settings)
        self.source_lang_combo.currentTextChanged.connect(self.update_settings)
        self.target_lang_combo.currentTextChanged.connect(self.update_settings)

    def update_settings(self):
        """实时更新设置"""
        self.settings.update({
            'source_lang': self.source_lang_combo.currentText(),
            'target_lang': self.target_lang_combo.currentText(),
            'current_preset': self.preset_combo.currentText()
        })
        self.settings_manager.save_settings(self.settings)

    def closeEvent(self, event):
        """窗口关闭时保存设置并退出程序"""
        self.settings_manager.save_settings(self.settings)
        # 关闭结果窗口
        self.result_window.close()
        # 停止处理线程
        if self.processing_thread.isRunning():
            self.processing_thread.terminate()
            self.processing_thread.wait()
        # 停止爬虫线程
        if self.crawler_worker and self.crawler_worker.isRunning():
            self.crawler_worker.stop()
            self.crawler_worker.wait()
        # 退出程序
        QApplication.quit()
        super().closeEvent(event)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, 'Open Image', '', 
            'Image files (*.jpg *.jpeg *.png *.bmp)')
        if path:
            img = cv2.imread(path)
            self.add_to_queue(img)

    def paste_image(self):
        clipboard = QApplication.clipboard()
        img = clipboard.image()
        if not img.isNull():
            self.add_to_queue(qimage_to_cv(img))

    def add_to_queue(self, img):
        """添加图片到处理队列"""
        # 计算图片哈希值以避免重复处理
        img_data = cv2.imencode('.png', img)[1].tobytes()
        img_hash = hash(img_data)
        
        # 检查是否已经处理过这张图片
        if img_hash not in self.processed_hashes:
            # 获取当前选择的语言的内部标识符
            source_index = self.source_lang_combo.currentIndex()
            target_index = self.target_lang_combo.currentIndex()
            source_lang = self.source_lang_combo.itemData(source_index)
            target_lang = self.target_lang_combo.itemData(target_index)

            # 保存设置
            self.settings['source_lang'] = source_lang
            self.settings['target_lang'] = target_lang
            self.settings_manager.save_settings(self.settings)

            # 添加到队列
            self.queue_mutex.lock()
            self.queue.append(img)
            self.queue_mutex.unlock()
            self.queue_condition.wakeOne()
            
            # 更新状态
            self.processed_hashes.add(img_hash)
            self.update_status()

    def process_queue(self):
        """处理队列中的图片"""
        while True:
            self.queue_mutex.lock()
            if not self.queue:
                self.queue_condition.wait(self.queue_mutex)
            if self.queue:
                img = self.queue.pop(0)
                self.last_image_data = img
            self.queue_mutex.unlock()

            if img is not None:
                try:
                    # 获取当前设置
                    settings = self.settings_manager.load_settings()
                    source_lang = settings.get('source_lang', 'Japanese')
                    target_lang = settings.get('target_lang', 'Simplified Chinese')

                    # 创建并启动翻译线程
                    self.worker = TranslationThread(img, source_lang, target_lang)
                    self.worker.finished.connect(self.show_initial_result)
                    self.worker.progress.connect(self.update_translation)
                    self.worker.error.connect(self.show_error)
                    self.worker.start()

                    # 等待线程完成
                    self.worker.wait()
                    self.worker = None
                    
                except Exception as e:
                    self.status_label.setText(f"处理错误: {str(e)}")
                    self.worker = None

    def show_result(self, img, translations):
        """显示翻译结果"""
        height, width, channel = img.shape
        bytes_per_line = 3 * width
        q_img = QImage(img.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        
        # 首先添加图片，不带文本区域
        image_index = self.result_window.add_image(QPixmap.fromImage(q_img))
        
        if translations:
            # 转换translations为文本区域列表
            text_regions = []
            for rect, original_text, translated_text in translations:
                text_regions.append((rect, original_text))
            
            # 设置文本区域
            self.result_window.set_text_regions(image_index, text_regions)
            
            # 更新翻译
            translation_dict = {original: translated for _, original, translated in translations}
            self.result_window.update_translations(image_index, translation_dict)

    def on_clipboard_change(self):
        """处理剪贴板变化"""
        mime = self.clipboard.mimeData()
        if mime.hasImage():
            img = qimage_to_cv(mime.imageData())
            if img is not None:
                self.add_to_queue(img)

    def clear_results(self):
        """清除队列、结果窗口中的所有图片，并停止当前任务"""
        # 停止当前任务
        if self.worker:
            self.worker.terminate()
            self.worker.wait()
            self.worker = None

        # 清除队列
        self.queue_mutex.lock()
        self.queue.clear()
        self.last_image_data = None
        self.queue_mutex.unlock()
        
        # 清除结果
        self.result_window.clear_results()
        
        # 清除哈希值记录
        self.processed_hashes.clear()
        
        # 清除翻译上下文
        TranslationThread.clear_context()
        
        # 重置进度
        self.processing_count = 0
        
        # 更新状态
        self.status_label.setText("已清除所有内容")

    def update_status(self):
        """更新状态标签"""
        status_parts = []
        
        if len(self.queue) > 0:
            status_parts.append(
                self.lang_manager.get_text('queue_status').format(count=len(self.queue))
            )
        
        if self.worker and hasattr(self.worker, 'total_boxes') and self.processing_count > 0:
            status_parts.append(
                self.lang_manager.get_text('processing_status').format(
                    current=self.processing_count,
                    total=self.worker.total_boxes
                )
            )
        elif not self.queue:
            status_parts.append(self.lang_manager.get_text('waiting'))
            
        self.status_label.setText(" | ".join(status_parts))

    def update_progress(self, current, total):
        """更新翻译进度"""
        if self.worker:  # 添加检查
            self.processing_count = current
            self.worker.total_boxes = total
            self.update_status() 

    def stop_current_task(self):
        """终止当前任务并清空队列"""
        # 清空队列
        self.queue_mutex.lock()
        self.queue.clear()
        self.queue_mutex.unlock()

        # 如果有正在运行的任务，终止它
        if self.worker:
            self.worker.terminate()
            self.worker.wait()
            self.worker = None

        # 重置进度
        self.processing_count = 0
        
        # 更新状态
        self.status_label.setText(self.lang_manager.get_text('task_stopped'))

    def handle_error(self, error_message):
        """处理翻译线程的错误"""
        print(f"翻译错误: {error_message}")
        self.status_label.setText(
            self.lang_manager.get_text('translation_error').format(error=error_message)
        )
        # 清理当前worker
        self.processing_count = 0
        self.worker = None
        self.update_status() 

    def handle_result_window_closed(self):
        """处理结果窗口关闭事件"""
        # 清空任务队列
        if hasattr(self, 'queue'):
            self.queue.clear()
        
        # 停止当前正在进行的任务
        if hasattr(self, 'worker') and self.worker:
            self.worker.terminate()
            self.worker.wait()
            self.worker = None
        
        # 重置进度
        self.processing_count = 0
        
        # 更新状态
        self.status_label.setText(self.lang_manager.get_text('queue_cleared'))
        
        # 将结果窗口引用设为 None
        self.result_window = None

    def update_preset_list(self):
        """更新预设列表"""
        current_text = self.preset_combo.currentText()  # 保存当前选中的预设
        self.preset_combo.clear()
        for preset_name in self.settings_manager.presets.keys():
            self.preset_combo.addItem(preset_name)
        
        # 如果之前有选中的预设，尝试恢复选择
        if current_text and current_text in self.settings_manager.presets:
            self.preset_combo.setCurrentText(current_text)
        else:
            # 否则使用设置中保存的当前预设
            current_preset = self.settings.get('current_preset', 'default')
            self.preset_combo.setCurrentText(current_preset)

    def on_preset_changed(self, preset_name):
        """处理预设切换"""
        if preset_name:
            self.settings['current_preset'] = preset_name
            self.settings_manager.save_settings(self.settings)

    def add_preset(self):
        """添加新预设"""
        dialog = PresetDialog(self)
        if dialog.exec_():
            preset_data = dialog.get_preset_data()
            self.settings_manager.add_preset(preset_data)
            self.update_preset_list()
            # 切换到新添加的预设
            self.preset_combo.setCurrentText(preset_data['name'])

    def edit_preset(self):
        """编辑预设"""
        current_preset = self.preset_combo.currentText()
        if current_preset:
            preset_data = self.settings_manager.get_preset(current_preset)
            dialog = PresetDialog(self, preset_data)
            if dialog.exec_():
                updated_data = dialog.get_preset_data()
                # 如果预设名称改变了，需要删除旧的预设
                if updated_data['name'] != current_preset:
                    self.settings_manager.delete_preset(current_preset)
                self.settings_manager.add_preset(updated_data)
                self.update_preset_list()
                # 切换到更新后的预设
                self.preset_combo.setCurrentText(updated_data['name'])

    def delete_preset(self):
        """删除预设"""
        current_preset = self.preset_combo.currentText()
        if current_preset != 'default':
            self.settings_manager.delete_preset(current_preset)
            self.update_preset_list() 

    def copy_preset(self):
        """复制当前预设"""
        current_preset = self.preset_combo.currentText()
        if current_preset:
            # 获取当前预设数据
            preset_data = self.settings_manager.get_preset(current_preset)
            if preset_data:
                # 创建新的预设名称
                new_name = current_preset + "-copy"
                counter = 1
                while new_name in self.settings_manager.presets:
                    new_name = f"{current_preset}-copy({counter})"
                    counter += 1
                
                # 创建新的预设数据
                new_preset = preset_data.copy()
                new_preset['name'] = new_name
                
                # 保存新预设
                self.settings_manager.add_preset(new_preset)
                self.update_preset_list()
                # 切换到新复制的预设
                self.preset_combo.setCurrentText(new_name)

    def change_language(self, language):
        """切换界面语言"""
        # 语言名称到代码的映射
        language_codes = {
            '简体中文': 'zh_CN',
            '繁體中文': 'zh_TW',
            '한국어': 'ko_KR',
            '日本語': 'ja_JP',
            'English': 'en_US'
        }
        
        # 设置新语言
        lang_code = language_codes.get(language, 'zh_CN')
        self.lang_manager.set_language(lang_code)
        self.settings['interface_language'] = lang_code
        self.settings_manager.save_settings(self.settings)
        
        # 更新所有UI文本
        self.update_ui_texts()
        
        # 更新所有ComboBox选项
        self.update_combo_boxes()

    def update_combo_boxes(self):
        """更新所有ComboBox的选项"""
        # 保存当前选择的值
        current_source = self.source_lang_combo.currentData()
        current_target = self.target_lang_combo.currentData()
        current_direction = self.direction_combo.currentData()
        
        # 清空并重新填充语言选项
        self.source_lang_combo.clear()
        self.target_lang_combo.clear()
        
        # 添加源语言选项
        source_languages = [
            (self.lang_manager.get_text('lang_japanese'), 'Japanese'),
            (self.lang_manager.get_text('lang_english'), 'English'),
            (self.lang_manager.get_text('lang_korean'), 'Korean'),
            (self.lang_manager.get_text('lang_chinese_simple'), 'Simplified Chinese'),
            (self.lang_manager.get_text('lang_chinese_traditional'), 'Traditional Chinese')
        ]
        
        for display_name, internal_name in source_languages:
            self.source_lang_combo.addItem(display_name, internal_name)
            self.target_lang_combo.addItem(display_name, internal_name)
        
        # 恢复之前的选择
        source_index = self.source_lang_combo.findData(current_source)
        target_index = self.target_lang_combo.findData(current_target)
        if source_index >= 0:
            self.source_lang_combo.setCurrentIndex(source_index)
        if target_index >= 0:
            self.target_lang_combo.setCurrentIndex(target_index)
        
        # 更新文本方向选项
        self.direction_combo.clear()
        self.direction_combo.addItem(self.lang_manager.get_text('direction_horizontal'), 'horizontal')
        self.direction_combo.addItem(self.lang_manager.get_text('direction_vertical'), 'vertical')
        
        direction_index = self.direction_combo.findData(current_direction)
        if direction_index >= 0:
            self.direction_combo.setCurrentIndex(direction_index)

    def update_ui_texts(self):
        """更新所有UI文本"""
        self.setWindowTitle(self.lang_manager.get_text('window_title'))
        
        # 更新按钮文本
        self.btn_add_preset.setText(self.lang_manager.get_text('add_preset'))
        self.btn_edit_preset.setText(self.lang_manager.get_text('edit_preset'))
        self.btn_delete_preset.setText(self.lang_manager.get_text('delete_preset'))
        self.btn_copy_preset.setText(self.lang_manager.get_text('copy_preset'))
        
        # 更新所有标签文本
        for label in self.findChildren(QLabel):
            if hasattr(label, 'original_text'):
                key = label.original_text
                if key:  # 确保有原始文本标识
                    label.setText(self.lang_manager.get_text(key) + 
                                (":" if not label.text().endswith(":") else "")) 
        
        # 更新操作按钮文本
        self.btn_open.setText(self.lang_manager.get_text('open_image'))
        self.btn_paste.setText(self.lang_manager.get_text('paste_clipboard'))
        self.btn_clear.setText(self.lang_manager.get_text('clear_all'))
        self.btn_stop.setText(self.lang_manager.get_text('stop_task'))
        
        self.status_label.setText(self.lang_manager.get_text('waiting'))

    def save_settings(self):
        """保存设置"""
        source_index = self.source_lang_combo.currentIndex()
        target_index = self.target_lang_combo.currentIndex()
        direction_index = self.direction_combo.currentIndex()
        
        settings = {
            'source_lang': self.source_lang_combo.itemData(source_index),
            'target_lang': self.target_lang_combo.itemData(target_index),
            'text_direction': self.direction_combo.itemData(direction_index),
            # ... 其他设置 ...
        }
        
        self.settings_manager.save_settings(settings) 

    def process_translation(self, results):
        self.image_label.clear_translations()
        
        # 使用原始尺寸的坐标
        for result in results:
            rect = QRect(
                result['x'],  # 原始坐标
                result['y'], 
                result['width'], 
                result['height']
            )
            self.image_label.add_translation(
                rect,
                result['text'],
                result['translation']
            )
        
        self.image_label.update() 

    def setup_translation_thread(self):
        """设置翻译线程"""
        self.worker = TranslationThread()
        self.worker.finished.connect(self.show_initial_result)
        self.worker.progress.connect(self.update_translation)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    def show_initial_result(self, img, translations):
        """显示初始结果（原图和文本框）"""
        # 如果结果窗口被关闭，重新创建
        if self.result_window is None:
            self.result_window = ResultWindowWebview()
            self.result_window.window_closed.connect(self.handle_result_window_closed)
            self.result_window.show()

        height, width, channel = img.shape
        bytes_per_line = 3 * width
        q_img = QImage(img.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        
        # 添加图片和文本区域
        text_regions = [(rect, text) for rect, text, _ in translations]
        self.current_image_index = self.result_window.add_image(QPixmap.fromImage(q_img), text_regions)

    def update_translation(self, index, original_text, translated_text):
        """更新单个文本的翻译结果"""
        try:
            # 将新的翻译添加到结果窗口
            translations = {original_text: translated_text}
            self.result_window.update_translations(self.current_image_index, translations)
            
            # 更新状态
            if hasattr(self.worker, 'total_boxes'):
                self.status_label.setText(
                    self.lang_manager.get_text('translating_progress').format(
                        current=index + 1,
                        total=self.worker.total_boxes
                    )
                )
        except Exception as e:
            print(f"更新翻译出错: {str(e)}")

    def show_error(self, error_message):
        """显示翻译错误"""
        self.status_label.setText(
            self.lang_manager.get_text('translation_error').format(error=error_message)
        ) 

    def fetch_from_webpage(self):
        """从网页获取并处理图片"""
        url = self.url_input.text().strip()
        if not url:
            return
            
        # 如果已有正在运行的爬虫任务，先停止它
        if self.crawler_worker and self.crawler_worker.isRunning():
            self.crawler_worker.stop()
            self.crawler_worker.wait()
        
        # 创建新的爬虫工作线程
        self.crawler_worker = CrawlerWorkerThread(url)
        
        # 连接信号
        self.crawler_worker.progress.connect(self.handle_crawler_progress)
        self.crawler_worker.status.connect(self.handle_crawler_status)
        self.crawler_worker.image_ready.connect(self.handle_crawler_image)
        self.crawler_worker.error.connect(self.handle_crawler_error)
        
        # 添加初始状态记录
        self.add_crawler_status(f"开始处理URL: {url}")
        
        # 启动线程
        self.crawler_worker.start()
    
    def handle_crawler_progress(self, current, total):
        """处理爬虫进度更新"""
        status = self.lang_manager.get_text('downloading_image').format(
            current=current,
            total=total
        )
        self.status_label.setText(status)
        self.add_crawler_status(status)
    
    def handle_crawler_status(self, status, data):
        """处理爬虫状态更新"""
        if status == 'crawling_finished':
            status_text = f"爬取完成，共获取 {data['total']} 张图片"
            self.status_label.setText(status_text)
            self.add_crawler_status(status_text)
        elif status in ['configuring_browser', 'loading_webpage', 'scrolling_page', 
                     'waiting_images', 'trying_selector', 'processing_image', 
                     'found_image_url']:
            status_text = self.lang_manager.get_text(status).format(**data if data else {})
            self.status_label.setText(status_text)
            self.add_crawler_status(status_text)
        elif status == 'found_images':
            status_text = self.lang_manager.get_text('found_images').format(
                count=data['count'],
                selector=data['selector']
            )
            self.status_label.setText(status_text)
            self.add_crawler_status(status_text)
        elif status == 'no_images_found':
            status_text = self.lang_manager.get_text('no_images_found')
            self.status_label.setText(status_text)
            self.add_crawler_status(status_text, is_error=True)
        elif status == 'downloading_image':
            status_text = self.lang_manager.get_text('downloading_image').format(
                current=data['current'],
                total=data['total']
            )
            self.status_label.setText(status_text)
            self.add_crawler_status(status_text)
    
    def handle_crawler_image(self, image, description):
        """处理爬虫获取到的单张图片"""
        self.add_crawler_status(f"获取到图片: {description}")
        self.add_to_queue(image)

    def handle_crawler_error(self, error):
        """处理爬虫错误"""
        error_text = self.lang_manager.get_text('browser_error').format(error=error)
        self.status_label.setText(error_text)
        self.add_crawler_status(error_text, is_error=True)

    def add_crawler_status(self, status, is_error=False):
        """添加爬虫状态记录"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        status_text = f"[{timestamp}] {status}"
        
        self.crawler_status_list.append(status_text)
        if len(self.crawler_status_list) > self.max_status_records:
            self.crawler_status_list.pop(0)
        
        # 使用HTML格式化显示，添加样式
        html_text = "<style>p { margin: 5px 0; }</style>"  # 添加段落间距
        for text in self.crawler_status_list:
            if "error" in text.lower() or "失败" in text or "failed" in text.lower():
                html_text += f'<p style="color: #ff3333; margin: 5px 0;">{text}</p>'
            else:
                html_text += f'<p style="margin: 5px 0;">{text}</p>'
        
        self.crawler_status_text.setHtml(html_text)
        # 滚动到底部
        self.crawler_status_text.verticalScrollBar().setValue(
            self.crawler_status_text.verticalScrollBar().maximum()
        )

    def clear_crawler_status(self):
        """清除爬虫状态记录"""
        self.crawler_status_list.clear()
        self.crawler_status_text.clear() 