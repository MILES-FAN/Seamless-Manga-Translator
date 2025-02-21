from time import time
import streamlit as st
import cv2
import numpy as np
from PIL import Image
import io
import base64
from ..core.translation import TranslationThread
from ..config.settings import SettingsManager

class WebMangaTranslator:
    def __init__(self):
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load_settings()
        self.init_session_state()

    def init_session_state(self):
        """初始化会话状态"""
        if 'processed_images' not in st.session_state:
            st.session_state.processed_images = []
        if 'translation_context' not in st.session_state:
            st.session_state.translation_context = []

    def run(self):
        """运行Web界面"""
        st.set_page_config(page_title="Manga Translator", layout="wide")
        st.title("Manga Translator")

        # 创建两列布局
        left_col, right_col = st.columns([1, 2])

        with left_col:
            self.show_settings()
            self.show_upload()

        with right_col:
            self.show_results()

    def show_settings(self):
        """显示设置面板"""
        with st.expander("设置", expanded=True):
            # 模式选择
            mode = st.selectbox(
                "翻译模式",
                options=['Ollama', 'Remote API'],
                index=0 if self.settings.get('trans_mode') == 'Ollama' else 1
            )

            # API设置
            if mode == 'Ollama':
                ollama_api = st.text_input(
                    "Ollama API",
                    value=self.settings.get('ollama_api', 'http://localhost:11434/api/chat')
                )
                ollama_model = st.text_input(
                    "LLM Model",
                    value=self.settings.get('ollama_model', 'qwen2.5:14b')
                )
                self.settings.update({
                    'trans_mode': mode,
                    'ollama_api': ollama_api,
                    'ollama_model': ollama_model
                })
            else:
                openai_api = st.text_input(
                    "OpenAI API",
                    value=self.settings.get('openai_api', '')
                )
                remote_model = st.text_input(
                    "Remote Model",
                    value=self.settings.get('remote_model', '')
                )
                bearer_token = st.text_input(
                    "Bearer Token",
                    value=self.settings.get('bearer_token', ''),
                    type="password"
                )
                self.settings.update({
                    'trans_mode': mode,
                    'openai_api': openai_api,
                    'remote_model': remote_model,
                    'bearer_token': bearer_token
                })

            # OCR API设置
            umiocr_api = st.text_input(
                "UmiOCR API",
                value=self.settings.get('umiocr_api', '')
            )
            self.settings.update({'umiocr_api': umiocr_api})

            # 语言设置
            source_lang = st.selectbox(
                "源语言",
                options=['日文', '韩文', '中文', '英文'],
                index=['日文', '韩文', '中文', '英文'].index(
                    self.settings.get('source_lang', '日文')
                )
            )
            target_lang = st.selectbox(
                "目标语言",
                options=['中文', '英文', '日文', '韩文'],
                index=['中文', '英文', '日文', '韩文'].index(
                    self.settings.get('target_lang', '中文')
                )
            )
            self.settings.update({
                'source_lang': source_lang,
                'target_lang': target_lang
            })

            # 保存设置
            if st.button("保存设置"):
                self.settings_manager.save_settings(self.settings)
                st.success("设置已保存")

    def process_multiple_images(self, images, descriptions):
        """批量处理图片，显示总体进度"""
        total_images = len(images)
        overall_progress = st.progress(0)
        current_status = st.empty()
        
        for i, (img, desc) in enumerate(zip(images, descriptions)):
            with st.spinner(f'处理图片 {desc} ({i+1}/{total_images})...'):
                try:
                    # 创建翻译线程
                    worker = TranslationThread(
                        img,
                        self.settings['source_lang'],
                        self.settings['target_lang']
                    )

                    # 更新进度的回调函数
                    def progress_callback(current, total):
                        if total > 0:
                            # 计算总体进度：已完成图片的进度 + 当前图片的进度/总图片数
                            overall = (i / total_images) + (current / total / total_images)
                            overall_progress.progress(overall)
                            current_status.text(
                                f"总进度: {i}/{total_images} 张图片 | "
                                f"当前图片: {current}/{total} 个文本框"
                            )

                    worker.progress.connect(progress_callback)
                    result_img = worker.run_sync()
                    st.session_state.processed_images.append(result_img)
                
                except Exception as e:
                    st.error(f'处理 {desc} 失败: {str(e)}')
                    continue

        overall_progress.progress(1.0)
        current_status.text(f"完成处理 {total_images} 张图片")
        st.success('所有图片处理完成！')

    def get_images_from_webpage(self, url):
        """使用 Selenium 从网页获取图片"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from webdriver_manager.chrome import ChromeDriverManager
        import requests
        import time

        # 设置 Chrome 选项
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')  # 设置窗口大小
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 降低自动化特征
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

        # 创建一个临时消息组件
        status_message = st.empty()
        def show_status(message, duration=10):
            status_message.info(message)
            time.sleep(duration)
            status_message.empty()

        try:
            with st.spinner("正在配置浏览器..."):
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                
            with st.spinner("正在加载网页..."):
                driver.get(url)
                
                # 初始等待
                show_status("等待页面初始加载...", 3)
                
                # 多次滚动以确保加载
                show_status("滚动页面加载图片...", 3)
                for _ in range(3):
                    driver.execute_script("""
                        window.scrollTo({
                            top: document.body.scrollHeight,
                            behavior: 'smooth'
                        });
                    """)
                    time.sleep(1)
                
                driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(1)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                show_status("等待图片加载完成...", 3)

                # 查找所有图片元素
                images = []
                descriptions = []
                
                # 更新选择器列表
                selectors = [
                    "img[class*='manga']", 
                    "img[class*='comic']",
                    "img[class*='chapter']",
                    "img[class*='page']",
                    "div[class*='manga'] img",
                    "div[class*='reader'] img",
                    ".manga-page img",
                    ".reader-page img",
                    ".comic-page img",
                    "div[role='main'] img",
                    "article img",
                    "main img",
                    "img[src*='manga']",
                    "img[src*='comic']",
                    "img[src*='chapter']",
                    "img[src*='page']",
                    "img[loading='lazy']",  # 懒加载图片
                    "img"  # 最后尝试所有图片
                ]

                found_elements = []
                for selector in selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        st.info(f"使用选择器 '{selector}' 找到 {len(elements)} 张图片")
                        # 过滤掉小图片和图标
                        elements = [e for e in elements if e.size['width'] > 200 and e.size['height'] > 200]
                        if elements:
                            found_elements = elements
                            break

                if not found_elements:
                    # 尝试使用 JavaScript 获取所有图片
                    elements = driver.execute_script("""
                        return Array.from(document.getElementsByTagName('img')).filter(img => 
                            img.offsetWidth > 200 && 
                            img.offsetHeight > 200 &&
                            !img.src.includes('avatar') &&
                            !img.src.includes('logo') &&
                            !img.src.includes('icon')
                        );
                    """)
                    if elements:
                        found_elements = elements
                        st.info(f"使用 JavaScript 找到 {len(elements)} 张图片")

                if not found_elements:
                    st.warning("未找到图片元素")
                    return [], []

                # 修改图片获取部分的提示
                progress_text = st.empty()
                total_found = len(found_elements)
                
                # 创建一个列表存储所有图片和描述
                images = []
                descriptions = []
                
                # 创建进度条
                progress_bar = st.progress(0)
                
                for i, element in enumerate(found_elements, 1):
                    try:
                        # 尝试不同的属性获取图片URL
                        img_url = (element.get_attribute('src') or 
                                 element.get_attribute('data-src') or 
                                 element.get_attribute('data-original') or
                                 element.get_attribute('data-lazy-src') or
                                 element.get_attribute('data-echo'))
                        
                        if img_url:
                            if img_url.startswith('//'):
                                img_url = 'https:' + img_url
                            elif img_url.startswith('/'):
                                img_url = '/'.join(url.split('/')[:3]) + img_url

                            if img_url.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                response = requests.get(img_url, headers={'Referer': url})
                                if response.status_code == 200:
                                    file_bytes = np.asarray(bytearray(response.content), dtype=np.uint8)
                                    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                                    if img is not None and img.shape[0] > 200 and img.shape[1] > 200:
                                        # 立即处理这张图片
                                        progress_text.info(f"正在处理第 {i}/{total_found} 张图片")
                                        
                                        # 创建翻译线程处理图片
                                        worker = TranslationThread(
                                            img,
                                            self.settings['source_lang'],
                                            self.settings['target_lang']
                                        )
                                        
                                        # 处理图片
                                        result_img = worker.run_sync()
                                        
                                        # 添加到会话状态
                                        if 'processed_images' not in st.session_state:
                                            st.session_state.processed_images = []
                                        st.session_state.processed_images.append(result_img)
                                        
                                        # 更新进度条
                                        progress_bar.progress(i/total_found)
                                        
                                        # 保存原始图片和描述以供后续使用
                                        images.append(img)
                                        descriptions.append(f"page_{i}")
                    except Exception as e:
                        progress_text.warning(f"处理第 {i} 张图片失败: {str(e)}")
                        continue

                progress_text.empty()
                progress_bar.empty()
                return images, descriptions
                
        except Exception as e:
            st.error(f"浏览器操作失败: {str(e)}")
            return [], []
            
        finally:
            try:
                driver.quit()
            except:
                pass

    def show_upload(self):
        """显示上传部分"""
        st.subheader("上传图片")
        
        # 创建两个标签页
        tab1, tab2 = st.tabs(["上传文件", "从网页获取"])
        
        # 上传文件标签页
        with tab1:
            uploaded_files = st.file_uploader(
                "选择图片文件",
                type=['png', 'jpg', 'jpeg'],
                accept_multiple_files=True
            )
            if uploaded_files and st.button("处理所有图片"):
                images = []
                descriptions = []
                for file in uploaded_files:
                    file_bytes = np.asarray(bytearray(file.read()), dtype=np.uint8)
                    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                    if img is not None:
                        images.append(img)
                        descriptions.append(file.name)
                self.process_multiple_images(images, descriptions)

        # 从网页获取标签页
        with tab2:
            url = st.text_input("输入漫画页面URL")
            if url and st.button("获取并处理"):
                images, descriptions = self.get_images_from_webpage(url)
                if images:
                    self.process_multiple_images(images, descriptions)
                else:
                    st.error("未能获取任何图片")

    @st.fragment
    def show_results(self):
        """显示处理结果"""
        st.subheader("处理结果")
        
        if not st.session_state.processed_images:
            st.info("还没有处理过的图片")
            return

        # 显示最新处理的图片
        latest_img = st.session_state.processed_images[-1]
        img_rgb = cv2.cvtColor(latest_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        st.image(pil_img, caption=f"最新处理结果", use_container_width=True)

        # 如果有多张图片，显示下载按钮
        if len(st.session_state.processed_images) > 1:
            # 下载按钮区域
            col1, col2 = st.columns(2)
            
            # 长图下载
            with col1:
                if st.button("下载长图"):
                    # 计算总高度和最大宽度
                    total_height = 0
                    max_width = 0
                    pil_images = []
                    
                    for img in st.session_state.processed_images:
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(img_rgb)
                        pil_images.append(pil_img)
                        max_width = max(max_width, pil_img.width)
                        total_height += pil_img.height

                    # 创建长图
                    long_image = Image.new('RGB', (max_width, total_height), 'white')
                    current_height = 0
                    
                    # 拼接图片
                    for pil_img in pil_images:
                        # 如果图片宽度小于最大宽度，居中放置
                        if pil_img.width < max_width:
                            x_offset = (max_width - pil_img.width) // 2
                        else:
                            x_offset = 0
                        
                        long_image.paste(pil_img, (x_offset, current_height))
                        current_height += pil_img.height

                    # 保存并提供下载
                    buf = io.BytesIO()
                    long_image.save(buf, format='PNG')
                    st.download_button(
                        label="保存长图",
                        data=buf.getvalue(),
                        file_name="combined_image.png",
                        mime="image/png"
                    )

            # ZIP打包下载
            with col2:
                if st.button("下载ZIP"):
                    import zipfile
                    from io import BytesIO
                    
                    # 创建ZIP文件
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for i, img in enumerate(st.session_state.processed_images):
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(img_rgb)
                            
                            # 将每张图片保存到ZIP
                            img_buffer = BytesIO()
                            pil_img.save(img_buffer, format='PNG')
                            zip_file.writestr(f'translated_image_{i+1}.png', img_buffer.getvalue())

                    # 提供ZIP下载
                    st.download_button(
                        label="保存ZIP",
                        data=zip_buffer.getvalue(),
                        file_name="translated_images.zip",
                        mime="application/zip"
                    )

        # 清除按钮
        if st.button("清除所有结果"):
            st.session_state.processed_images = []
            st.session_state.translation_context = []
            st.rerun() 
        
        time.sleep(3)
        st.rerun()