from DrissionPage import ChromiumPage, ChromiumOptions
import cv2
import numpy as np
import time

class WebScraperDP:
    @staticmethod
    def get_images_from_webpage(url, image_callback=None, progress_callback=None, status_callback=None):
        """使用DrissionPage从网页获取漫画图片"""
        # 配置浏览器
        if status_callback:
            status_callback('configuring_browser')
            
        co = ChromiumOptions()
        co.headless()  # 无头模式
        co.set_argument('--window-size=1920,1080')
        
        try:
            # 创建页面对象
            page = ChromiumPage(co)
            
            if status_callback:
                status_callback('loading_webpage')
            
            # 访问页面
            page.get(url)
            page.wait.doc_loaded()  # 等待文档加载
            time.sleep(2)  # 等待初始内容加载
            
            if status_callback:
                status_callback('scrolling_page')
            
            # 获取页面高度
            init_height = page.run_js('return document.documentElement.scrollHeight')
            
            # 分步滚动
            last_height = 0
            max_tries = 5
            tries = 0
            
            while tries < max_tries:
                # 滚动到当前可见区域的底部
                page.scroll.to_bottom()
                time.sleep(1)  # 等待内容加载
                
                if status_callback:
                    status_callback('scrolling_page, tries: ' + str(tries))
                
                # 获取新的页面高度
                new_height = page.run_js('return document.documentElement.scrollHeight')
                
                # 如果高度没有变化，说明已经到底或者加载完成
                if new_height == last_height:
                    break
                    
                last_height = new_height
                tries += 1
                
                # 等待新图片加载
                page.wait.ele_loaded('img', timeout=2)
            
            # 回到顶部并等待最后的图片加载
            page.scroll.to_top()
            time.sleep(1)
            
            # 等待图片加载完成
            if status_callback:
                status_callback('waiting_images')
            
            # 查找所有图片元素
            images = page.eles('img:not([src*="logo"]):not([src*="icon"]):not([src*="avatar"])')
            
            # 过滤有效图片
            valid_images = []
            for img in images:
                try:
                    if (img.is_displayed() and 
                        img.rect.size.get('width', 0) > 200 and 
                        img.rect.size.get('height', 0) > 200):
                        valid_images.append(img)
                except:
                    continue
            
            if not valid_images:
                if status_callback:
                    status_callback('no_images_found')
                return
            
            if status_callback:
                status_callback('found_images', {'count': len(valid_images)})
            
            # 处理图片
            for i, img in enumerate(valid_images, 1):
                try:
                    if status_callback:
                        status_callback('processing_image', {'current': i, 'total': len(valid_images)})
                    
                    # 直接获取图片字节数据
                    img_bytes = img.get_bytes()
                    if img_bytes:
                        file_bytes = np.asarray(bytearray(img_bytes), dtype=np.uint8)
                        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                        
                        if image is not None and image.shape[0] > 200 and image.shape[1] > 200:
                            if image_callback:
                                image_callback(image, f"page_{i}")
                            if progress_callback:
                                progress_callback(i, len(valid_images))
                
                except Exception as e:
                    if status_callback:
                        status_callback('image_error', {'index': i, 'error': str(e)})
                    continue
            
            if status_callback:
                status_callback('crawling_finished', {'total': len(valid_images)})
                
        except Exception as e:
            if status_callback:
                status_callback('browser_error', {'error': str(e)})
            
        finally:
            try:
                page.quit()
            except:
                pass