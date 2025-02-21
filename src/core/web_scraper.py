from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import requests
import time
import numpy as np
import cv2

class WebScraper:
    @staticmethod
    def get_images_from_webpage(url, image_callback=None, progress_callback=None, status_callback=None):
        """
        从网页获取漫画图片
        
        Args:
            url (str): 网页URL
            image_callback (callable): 每获取到一张图片时的回调函数
            progress_callback (callable): 进度回调函数
            status_callback (callable): 状态回调函数
            
        Returns:
            tuple: (images, descriptions) 图片列表和描述列表
        """
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')

        if status_callback:
            status_callback('configuring_browser')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            if status_callback:
                status_callback('loading_webpage')
            
            driver.get(url)
            
            # 初始等待
            if status_callback:
                status_callback('scrolling_page')
            time.sleep(3)
            
            # 多次滚动以确保加载
            for _ in range(3):
                driver.execute_script(
                    "window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});"
                )
                time.sleep(1)
            
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            if status_callback:
                status_callback('waiting_images')
            time.sleep(2)

            # 图片选择器列表
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
                "img[loading='lazy']",
                "img"
            ]

            found_elements = []
            for selector in selectors:
                if status_callback:
                    status_callback('trying_selector', {'selector': selector})
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    # 过滤掉小图片和图标
                    elements = [e for e in elements if e.size['width'] > 200 and e.size['height'] > 200]
                    if elements:
                        if status_callback:
                            status_callback('found_images', {'count': len(elements), 'selector': selector})
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
                    if status_callback:
                        status_callback('found_images', {'count': len(elements), 'selector': 'javascript'})

            if not found_elements:
                if status_callback:
                    status_callback('no_images_found')
                return

            total_found = len(found_elements)
            processed_count = 0

            for i, element in enumerate(found_elements, 1):
                try:
                    if status_callback:
                        status_callback('processing_image', {'current': i, 'total': total_found})
                    
                    # 尝试不同的属性获取图片URL
                    img_url = (element.get_attribute('src') or 
                             element.get_attribute('data-src') or 
                             element.get_attribute('data-original') or
                             element.get_attribute('data-lazy-src') or
                             element.get_attribute('data-echo'))
                    
                    if img_url:
                        if status_callback:
                            status_callback('found_image_url', {'url': img_url})
                        
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
                                    processed_count += 1
                                    if image_callback:
                                        image_callback(img, f"page_{i}")
                                    if progress_callback:
                                        progress_callback(processed_count, total_found)

                except Exception as e:
                    if status_callback:
                        status_callback('image_error', {'index': i, 'error': str(e)})
                    continue

            if status_callback:
                status_callback('crawling_finished', {'total': processed_count})
                
        except Exception as e:
            if status_callback:
                status_callback('browser_error', {'error': str(e)})
            
        finally:
            try:
                driver.quit()
            except:
                pass 