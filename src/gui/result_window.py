from PyQt5.QtWidgets import (QDialog, QLabel, QVBoxLayout, QScrollArea, 
                            QWidget, QSizePolicy, QMenu, QFileDialog, QMainWindow,
                            QPushButton, QHBoxLayout)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QResizeEvent, QIcon, QPainter, QColor
from PIL import Image
from PyQt5.QtWidgets import QApplication
from src.gui.translation_overlay import TranslationOverlay

class ResultWindow(QMainWindow):
    window_closed = pyqtSignal()  # 添加关闭信号

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Translation Results")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(400, 300)  # 设置最小窗口大小

        # 创建主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # 创建垂直布局
        self.layout = QVBoxLayout(main_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # 创建滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动区域的内容部件
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.content_widget)
        
        self.layout.addWidget(self.scroll)
        
        # 存储图片标签和对应的翻译信息
        self.image_labels = []
        self.translation_overlays = []
        
        # 显示窗口
        self.show()

    def add_image(self, pixmap, text_regions=None):
        """
        立即添加图片并显示，可以稍后添加文本区域
        pixmap: QPixmap对象
        text_regions: [(QRect, text), ...] 文本区域列表，可以为None
        """
        # 创建图片标签
        label = ScalableImageLabel()
        label.setPixmap(pixmap)
        label.setAlignment(Qt.AlignCenter)
        
        # 将标签添加到布局中
        self.content_layout.addWidget(label)
        
        # 存储标签引用
        self.image_labels.append(label)
        
        # 如果有文本区域，创建覆盖层
        if text_regions:
            # 转换为需要的格式 [(rect, text, None), ...]
            regions = [(rect, text, None) for rect, text in text_regions]
            overlay = TranslationOverlay(label, regions)
            label.setMouseTracking(True)
            label.mouseMoveEvent = lambda e: self.handle_mouse_move(e, label, regions)
            label.leaveEvent = lambda e: self.handle_mouse_leave(e)
        else:
            overlay = None
        
        self.translation_overlays.append(overlay)
        
        # 调整窗口大小以适应新内容
        self.adjustSize()
        
        # 返回图片索引，用于后续更新
        return len(self.image_labels) - 1

    def update_translations(self, image_index, translations):
        """
        更新指定图片的翻译结果
        translations: {original_text: translated_text, ...} 翻译结果字典
        """
        if 0 <= image_index < len(self.translation_overlays):
            overlay = self.translation_overlays[image_index]
            overlay.update_translations(translations)

    def handle_mouse_move(self, event, label, regions):
        """处理鼠标移动事件"""
        pos = event.pos()
        overlay = next((o for o in self.translation_overlays 
                       if o.parent == label), None)
        if overlay:
            for rect, text, _ in regions:
                if rect.contains(pos):
                    overlay.current_hover = (rect, text)
                    overlay.update()
                    return
            overlay.current_hover = None
            overlay.update()

    def handle_mouse_leave(self, event):
        """处理鼠标离开事件"""
        for overlay in self.translation_overlays:
            overlay.current_hover = None
            overlay.update()

    def show_context_menu(self, pos, image_label):
        context_menu = QMenu(self)
        copy_action = context_menu.addAction("复制到剪贴板")
        save_action = context_menu.addAction("保存图片")
        save_all_separate_action = context_menu.addAction("保存所有图片到本地（分开）")
        save_all_combined_action = context_menu.addAction("保存所有图片到本地（长图）")
        copy_all_combined_action = context_menu.addAction("复制所有图片到剪切板（长图）")
        
        action = context_menu.exec_(image_label.mapToGlobal(pos))
        if action == copy_action:
            self.copy_to_clipboard(image_label)
        elif action == save_action:
            self.save_image(image_label)
        elif action == save_all_separate_action:
            self.save_all_images_separately()
        elif action == save_all_combined_action:
            self.save_all_images_combined()
        elif action == copy_all_combined_action:
            self.copy_all_images_combined_to_clipboard()

    def save_image(self, image_label):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", "",
            "PNG文件 (*.png);;JPEG文件 (*.jpg *.jpeg)")
        if file_path:
            image_label.pixmap().save(file_path)

    def copy_to_clipboard(self, image_label):
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(image_label.pixmap())

    def save_all_images_separately(self):
        for i in range(self.content_layout.count()):
            image_label = self.content_layout.itemAt(i).widget()
            if i == 0:
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "保存图片", "",
                    "PNG文件 (*.png);;JPEG文件 (*.jpg *.jpeg)")
                if file_path:
                    base_name, ext = file_path.rsplit('.', 1)
                    if not base_name[-1].isdigit():
                        base_name += "_1"
                    file_path = f"{base_name}.{ext}"
            else:
                base_name, ext = file_path.rsplit('.', 1)
                num = int(base_name.split('_')[-1]) + 1 if '_' in base_name and base_name.split('_')[-1].isdigit() else 1
                base_name = '_'.join(base_name.split('_')[:-1]) if '_' in base_name and base_name.split('_')[-1].isdigit() else base_name
                file_path = f"{base_name}_{num}.{ext}"
            image_label.pixmap().save(file_path)

    def create_combined_image(self):
        total_height = sum(self.content_layout.itemAt(i).widget().pixmap().height() for i in range(self.content_layout.count()))
        width = max(self.content_layout.itemAt(i).widget().pixmap().width() for i in range(self.content_layout.count()))
        
        combined_image = Image.new('RGB', (width, total_height))
        y_offset = 0
        for i in range(self.content_layout.count()):
            pixmap = self.content_layout.itemAt(i).widget().pixmap()
            # Convert QPixmap to QImage
            qimage = pixmap.toImage()
            # Convert QImage to bytes
            bits = qimage.bits()
            bits.setsize(qimage.height() * qimage.width() * 4)  # 4 for RGBA
            # Convert to PIL Image
            img = Image.frombytes('RGBA', (qimage.width(), qimage.height()), bits, 'raw', 'BGRA')
            # Convert to RGB mode
            img = img.convert('RGB')
            combined_image.paste(img, (0, y_offset))
            y_offset += pixmap.height()
        
        return combined_image

    def save_all_images_combined(self):
        combined_image = self.create_combined_image()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存所有图片（长图）", "",
            "PNG文件 (*.png);;JPEG文件 (*.jpg *.jpeg)")
        if file_path:
            combined_image.save(file_path)

    def copy_all_images_combined_to_clipboard(self):
        combined_image = self.create_combined_image()
        # Convert PIL Image to QImage
        data = combined_image.tobytes("raw", "RGB")
        qimage = QImage(data, combined_image.width, combined_image.height, QImage.Format_RGB888)
        clipboard = QApplication.clipboard()
        clipboard.setImage(qimage)

    def clear_results(self):
        """清除所有结果"""
        # 清除所有覆盖层
        for overlay in self.translation_overlays:
            if overlay:
                overlay.deleteLater()
        self.translation_overlays.clear()
        
        # 清除所有图片标签
        for label in self.image_labels:
            label.deleteLater()
        self.image_labels.clear()
        
        # 刷新界面
        self.content_widget.update()

    def resizeEvent(self, event: QResizeEvent):
        """窗口大小改变时调整所有图片"""
        super().resizeEvent(event)
        self.resize_images()

    def resize_images(self):
        """调整所有图片大小以适应窗口宽度"""
        available_width = self.scroll.width() - 30  # 减去滚动条宽度和边距
        for label in self.image_labels:
            label.resize_image(available_width)

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.clear_and_stop()
        self.window_closed.emit()
        event.accept()

    def clear_and_stop(self):
        """清空结果并停止当前任务"""
        self.clear_results()
        # 发送信号通知主程序停止当前任务
        self.window_closed.emit()

    def set_text_regions(self, image_index, text_regions):
        """
        为已添加的图片设置文本区域
        image_index: 图片索引
        text_regions: [(QRect, text), ...] 文本区域列表
        """
        if 0 <= image_index < len(self.image_labels):
            label = self.image_labels[image_index]
            
            # 如果已经有overlay，先移除
            if self.translation_overlays[image_index]:
                self.translation_overlays[image_index].deleteLater()
            
            # 转换为需要的格式 [(rect, text, None), ...]
            regions = [(rect, text, None) for rect, text in text_regions]
            overlay = TranslationOverlay(label, regions)
            
            # 设置鼠标追踪
            label.setMouseTracking(True)
            label.mouseMoveEvent = lambda e: self.handle_mouse_move(e, label, regions)
            label.leaveEvent = lambda e: self.handle_mouse_leave(e)
            
            self.translation_overlays[image_index] = overlay

class ScalableImageLabel(QLabel):
    def __init__(self):
        super().__init__()
        self.original_pixmap = None

    def setPixmap(self, pixmap):
        """设置图片并保存原始图片"""
        self.original_pixmap = pixmap
        super().setPixmap(pixmap)

    def resize_image(self, target_width):
        """调整图片大小以适应目标宽度"""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaledToWidth(
                target_width,
                Qt.SmoothTransformation
            )
            super().setPixmap(scaled_pixmap)