from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFontMetrics

class TranslationOverlay(QWidget):
    def __init__(self, parent, regions, translations=None):
        """
        parent: 父级widget（图片标签）
        regions: 待翻译区域列表 [(rect, text, translated_text), ...]
        translations: 翻译结果字典 {text: translated_text} 或 None
        """
        super().__init__(parent)
        self.parent = parent
        # 将regions转换为我们需要的格式
        self.regions = [(r[0], r[1]) for r in regions]  # 只保留rect和原文
        self.translations = translations or {}  # 如果没有翻译结果，使用空字典
        self.current_hover = None
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        # 调整大小以匹配父部件
        self.resize(parent.size())
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        for rect, original_text in self.regions:
            # 绘制半透明背景
            painter.setPen(Qt.NoPen)
            if original_text in self.translations:
                # 已翻译的区域使用蓝色
                painter.setBrush(QColor(0, 120, 215, 40))
            else:
                # 待翻译的区域使用灰色
                painter.setBrush(QColor(128, 128, 128, 40))
            painter.drawRect(rect)

            # 绘制边框
            painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            # 如果鼠标悬停在此区域，显示文本
            if self.current_hover and self.current_hover[0] == rect:
                self.draw_text_bubble(painter, rect, original_text)

    def draw_text_bubble(self, painter, rect, original_text):
        translated_text = self.translations.get(original_text, "翻译中...")
        
        # 计算气泡位置和大小
        font = painter.font()
        font_metrics = QFontMetrics(font)
        text_width = max(font_metrics.width(original_text), 
                        font_metrics.width(translated_text))
        text_height = font_metrics.height() * 2 + 10  # 两行文字加间距
        
        # 使用int()转换浮点数为整数
        x = int(rect.center().x() - text_width/2 - 10)
        y = rect.top() - text_height - 10
        width = text_width + 20
        height = text_height + 10
        
        bubble_rect = QRect(x, y, width, height)
        
        # 确保气泡在窗口内
        if bubble_rect.top() < 0:
            bubble_rect.moveTop(rect.bottom() + 10)
        
        # 绘制气泡背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 200))
        painter.drawRoundedRect(bubble_rect, 5, 5)
        
        # 绘制文字
        painter.setPen(Qt.white)
        painter.drawText(bubble_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                        f"{original_text}\n{translated_text}")

    def update_translations(self, translations):
        """更新翻译结果"""
        self.translations = translations
        self.update()

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        pos = event.pos()
        for rect, original_text in self.regions:
            if rect.contains(pos):
                self.current_hover = (rect, original_text)
                self.update()
                return
        self.current_hover = None
        self.update()

    def resizeEvent(self, event):
        """处理大小变化事件"""
        self.resize(self.parent.size()) 