from PyQt5.QtCore import QObject, pyqtSignal, QByteArray, QBuffer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
import json
import os
import base64
from PIL import Image
import io

class ResultWindowWebview(QMainWindow):
    window_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Translation Results')
        #set to center primary screen, primary screen height - 200 and 1/3 of width
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        height = screen_geometry.height() - 200
        width = screen_geometry.width() / 3
        self.setGeometry((int)(screen_geometry.center().x() - width / 2), (int)(screen_geometry.center().y() - height / 2), (int)(width), (int)(height))

        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 创建WebEngine视图
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)

        # 存储当前显示的图片信息
        self.current_images = []

        # 创建HTML文件路径
        self.html_path = os.path.join(os.path.dirname(__file__), 'templates', 'viewer.html')
        
        # 确保templates目录存在
        os.makedirs(os.path.dirname(self.html_path), exist_ok=True)
        
        # 创建并加载HTML模板
        self._create_html_template()
        self.web_view.setUrl(QUrl.fromLocalFile(self.html_path))

    def _create_html_template(self):
        """创建基础HTML模板"""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { 
                    margin: 0; 
                    background: #1a1a1a; 
                    color: white;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    font-size: 18px;  /* 增大字体 */
                }
                #images {
                    width: 100%;
                    max-width: 100vw;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }
                .image-container { 
                    position: relative;
                    margin: 10px;
                    width: 95%;  /* 留一些边距 */
                    display: flex;
                    justify-content: center;
                }
                .image-wrapper {
                    position: relative;
                    width: 100%;
                    height: 100%;
                }
                .image-container img { 
                    width: 100%;
                    height: auto;
                    display: block;
                }
                .text-region {
                    position: absolute;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    background: rgba(128, 128, 128, 0.2);
                    cursor: pointer;
                    transform-origin: top left;
                }
                .text-region:hover {
                    background: rgba(0, 120, 215, 0.3);
                }
                .translation-bubble {
                    position: absolute;
                    background: rgba(0, 0, 0, 0.8);
                    padding: 8px;
                    border-radius: 4px;
                    pointer-events: none;
                    display: none;
                    color: white;
                    max-width: 540px;
                    text-align: center;
                    z-index: 1000;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }
                .original-text { color: #cccccc; margin-bottom: 4px; }
                .translated-text { color: white; }
            </style>
        </head>
        <body>
            <div id="images"></div>
            <script>
                function updateRegionPositions() {
                    document.querySelectorAll('.image-container').forEach(container => {
                        const wrapper = container.querySelector('.image-wrapper');
                        const img = wrapper.querySelector('img');
                        const regions = wrapper.querySelectorAll('.text-region');
                        
                        // 计算缩放比例
                        const scaleX = wrapper.clientWidth / img.naturalWidth;
                        const scaleY = wrapper.clientHeight / img.naturalHeight;
                        
                        regions.forEach(region => {
                            const originalX = parseFloat(region.dataset.x);
                            const originalY = parseFloat(region.dataset.y);
                            const originalWidth = parseFloat(region.dataset.width);
                            const originalHeight = parseFloat(region.dataset.height);
                            
                            region.style.left = (originalX * scaleX) + 'px';
                            region.style.top = (originalY * scaleY) + 'px';
                            region.style.width = (originalWidth * scaleX) + 'px';
                            region.style.height = (originalHeight * scaleY) + 'px';
                        });
                    });
                }

                function showTranslation(element, original, translated) {
                    const bubble = element.querySelector('.translation-bubble');
                    bubble.style.display = 'block';
                    
                    // 调整气泡位置
                    const rect = element.getBoundingClientRect();
                    const bubbleRect = bubble.getBoundingClientRect();
                    
                    let top = -bubbleRect.height - 10;
                    if (rect.top + top < 0) {
                        top = rect.height + 10;
                    }
                    
                    bubble.style.top = `${top}px`;
                    bubble.style.left = `${(rect.width - bubbleRect.width) / 2}px`;
                }

                function hideTranslation(element) {
                    const bubble = element.querySelector('.translation-bubble');
                    bubble.style.display = 'none';
                }

                // 监听窗口大小变化
                window.addEventListener('resize', updateRegionPositions);
                
                // 监听图片加载完成
                document.addEventListener('DOMContentLoaded', function() {
                    const images = document.querySelectorAll('.image-container img');
                    images.forEach(img => {
                        img.addEventListener('load', updateRegionPositions);
                    });
                    // 初始更新位置
                    updateRegionPositions();
                });
            </script>
        </body>
        </html>
        '''
        with open(self.html_path, 'w', encoding='utf-8') as f:
            f.write(html)

    def add_image(self, pixmap, text_regions=None):
        """添加新图片到查看器"""
        image_data = self._pixmap_to_base64(pixmap)
        
        image_info = {
            'image': image_data,
            'regions': [],
            'translations': {}
        }
        
        if text_regions:
            for rect, text in text_regions:
                image_info['regions'].append({
                    'x': rect.x(),
                    'y': rect.y(),
                    'width': rect.width(),
                    'height': rect.height(),
                    'text': text
                })
        
        self.current_images.append(image_info)
        image_index = len(self.current_images) - 1
        self._update_webpage()
        return image_index

    def set_text_regions(self, image_index, text_regions):
        """设置图片的文本区域"""
        if 0 <= image_index < len(self.current_images):
            self.current_images[image_index]['regions'] = [
                {
                    'x': rect.x(),
                    'y': rect.y(),
                    'width': rect.width(),
                    'height': rect.height(),
                    'text': text
                }
                for rect, text in text_regions
            ]
            self._update_webpage()

    def update_translations(self, image_index, translations):
        """更新翻译结果"""
        if 0 <= image_index < len(self.current_images):
            # 合并新的翻译结果到现有的翻译字典中
            self.current_images[image_index]['translations'].update(translations)
            self._update_webpage()

    def _pixmap_to_base64(self, pixmap):
        """将QPixmap转换为base64字符串"""
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QBuffer.WriteOnly)
        pixmap.save(buffer, "PNG")
        return base64.b64encode(byte_array.data()).decode()

    def _escape_text(self, text):
        """转义文本，避免 JavaScript 注入"""
        if not text:
            return ''
        return (text.replace('\\', '\\\\')
                   .replace('"', '\\"')
                   .replace("'", "\\'")
                   .replace('\n', '\\n')
                   .replace('\r', '\\r')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;'))

    def _update_webpage(self):
        """更新网页内容"""
        html_content = ''
        for img_info in self.current_images:
            html_content += f'''
                <div class="image-container">
                    <div class="image-wrapper">
                        <img src="data:image/png;base64,{img_info['image']}">
            '''
            
            translations = img_info['translations']
            
            for region in img_info['regions']:
                original = self._escape_text(region['text'])
                translation = self._escape_text(translations.get(region['text'], '翻译中...'))
                
                html_content += f'''
                    <div class="text-region" 
                         data-x="{region['x']}" 
                         data-y="{region['y']}"
                         data-width="{region['width']}"
                         data-height="{region['height']}"
                         data-original="{original}"
                         data-translation="{translation}">
                        <div class="translation-bubble">
                            <div class="original-text"></div>
                            <div class="translated-text"></div>
                        </div>
                    </div>
                '''
            
            html_content += '</div></div>'
        
        # 更新 JavaScript 代码，从 data 属性读取文本
        script = '''
            document.getElementById("images").innerHTML = `''' + html_content + '''`;
            document.querySelectorAll('.text-region').forEach(region => {
                const bubble = region.querySelector('.translation-bubble');
                const originalText = region.querySelector('.original-text');
                const translatedText = region.querySelector('.translated-text');
                
                originalText.textContent = region.dataset.original;
                translatedText.textContent = region.dataset.translation;
                
                region.onmouseover = () => {
                    bubble.style.display = 'block';
                    const rect = region.getBoundingClientRect();
                    const bubbleRect = bubble.getBoundingClientRect();
                    
                    let top = -bubbleRect.height - 10;
                    if (rect.top + top < 0) {
                        top = rect.height + 10;
                    }
                    
                    bubble.style.top = `${top}px`;
                    bubble.style.left = `${(rect.width - bubbleRect.width) / 2}px`;
                };
                
                region.onmouseout = () => {
                    bubble.style.display = 'none';
                };
            });
            updateRegionPositions();
        '''
        self.web_view.page().runJavaScript(script)

    def clear_results(self):
        """清除所有结果"""
        self.current_images.clear()
        self._update_webpage()

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.window_closed.emit()
        super().closeEvent(event) 