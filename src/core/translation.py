import numpy as np
import requests
import json
import cv2
from PyQt5.QtCore import QThread, pyqtSignal, QRect
from urllib.request import urlretrieve
import os
from PIL import ImageFont, ImageDraw, Image
from sklearn.cluster import OPTICS
from .ocr import ocr_through_UmiOCR, preprocess_image
from ..config.settings import SettingsManager
import threading
from ..i18n.language_manager import LanguageManager

class TranslationThread(QThread):
    finished = pyqtSignal(object, list)  # 发送原始图片和翻译信息
    progress = pyqtSignal(int, str, str)  # 发送翻译进度：文本索引、原文、译文
    error = pyqtSignal(str)

    # 语言映射字典
    lang_name_map = {
        '英文': 'English',
        '韩文': 'Korean',
        '日文': 'Japanese',
        '中文': 'Chinese'
    }

    # 类级别的上下文存储
    _shared_context = []  # 存储最近的翻译上下文
    _context_lock = threading.Lock()  # 用于线程安全的上下文访问
    MAX_CONTEXT_ITEMS = 10  # 保留最近10个文本框的上下文

    def __init__(self, image, source_lang, target_lang, parent=None):
        super().__init__(parent)
        self.lang_manager = LanguageManager()
        
        # 本地化语言名称到内部名称的映射
        self.lang_name_map = {
            # 从本地化名称映射到内部名称
            self.lang_manager.get_text('lang_english'): 'English',
            self.lang_manager.get_text('lang_korean'): 'Korean',
            self.lang_manager.get_text('lang_japanese'): 'Japanese',
            self.lang_manager.get_text('lang_chinese_simple'): 'Simplified Chinese',
            self.lang_manager.get_text('lang_chinese_traditional'): 'Traditional Chinese',
            # 添加内部名称的自映射，避免重复转换
            'English': 'English',
            'Korean': 'Korean',
            'Japanese': 'Japanese',
            'Simplified Chinese': 'Simplified Chinese',
            'Traditional Chinese': 'Traditional Chinese'
        }
        
        self.image = image
        self.source_lang = source_lang  # 已经是英文标识符
        self.target_lang = target_lang  # 已经是英文标识符
        self.total_boxes = 0
        font_path = 'fonts/NotoSansCJK-Regular.ttc'
        if not os.path.exists(font_path):
            os.makedirs('fonts', exist_ok=True)
            urlretrieve('https://github.com/notofonts/noto-cjk/raw/main/Sans/OTC/NotoSansCJK-Regular.ttc', font_path)
        self.font_path = font_path

    def run(self):
        try:
            img = self.image
            img = preprocess_image(img)

            # OCR识别
            result = ocr_through_UmiOCR(img, self.source_lang)
            if result['code'] != 100:
                self.error.emit("OCR failed: " + str(result))
                return

            # 合并文本框
            result = self.merge_ocr_results(result)
            if not result['data']:
                self.error.emit("No text detected")
                return

            # 设置总文本框数量
            self.total_boxes = len(result['data'])

            # 准备翻译区域信息
            translations = []
            context = ''
            
            # 首先收集所有文本区域
            for line in result['data']:
                text = line['text'].strip()
                points = line['box']
                
                # 计算文本框的矩形区域
                x_coords = [points[i] for i in range(0, len(points), 2)]
                y_coords = [points[i+1] for i in range(0, len(points), 2)]
                x, y = min(x_coords), min(y_coords)
                w = max(x_coords) - x
                h = max(y_coords) - y
                rect = QRect(x, y, w, h)
                
                # 添加到翻译列表，初始没有翻译结果
                translations.append((rect, text, None))

            # 发送原始图片和文本区域信息，开始显示界面
            self.finished.emit(img, translations)

            # 逐个翻译文本
            for i, (rect, text, _) in enumerate(translations):
                try:
                    translated = self.translate_text(text, context)
                    # 更新上下文
                    if translated:
                        context += f"{text} -> {translated}\n"
                    else:
                        context += f"{text}\n"
                    # 发送翻译进度
                    self.progress.emit(i, text, translated or text)  # 如果翻译为空，使用原文
                except Exception as e:
                    print(f"Translation error for text '{text}': {str(e)}")
                    self.progress.emit(i, text, "翻译错误")

        except Exception as e:
            self.error.emit(str(e))

    def merge_ocr_results(self, result):
        """合并OCR结果"""
        result_data = result['data']
        if not result_data:
            return {'data': []}
        
        # 获取当前文本方向设置
        settings_manager = SettingsManager()
        text_direction = settings_manager.load_settings().get('text_direction', 'horizontal')
        
        # 提取文本块基本信息
        text_blocks = []
        for line in result_data:
            if line['score'] < 0.5:
                continue
                
            box = line['box']
            # 处理不同格式的边界框
            try:
                if isinstance(box[0], (int, float)):  # 如果第一个元素是数字
                    if len(box) == 8:  # x1,y1,x2,y2,x3,y3,x4,y4 格式
                        center_x = sum(box[::2]) / 4  # 取所有x坐标的平均值
                        center_y = sum(box[1::2]) / 4  # 取所有y坐标的平均值
                    elif len(box) == 4:  # x,y,w,h 格式
                        x, y, w, h = box
                        center_x = x + w/2
                        center_y = y + h/2
                        # 转换为8点格式
                        box = [x, y, x+w, y, x+w, y+h, x, y+h]
                    else:
                        print(f"Warning: Unexpected box length: {len(box)}")
                        continue
                elif isinstance(box[0], list):  # 如果是点的列表格式 [[x1,y1], [x2,y2], ...]
                    if len(box) == 4:  # 四个角点
                        center_x = sum(p[0] for p in box) / 4
                        center_y = sum(p[1] for p in box) / 4
                        # 转换为8点格式
                        box = [p for point in box for p in point]
                    else:
                        print(f"Warning: Unexpected number of points: {len(box)}")
                        continue
                else:
                    print(f"Warning: Unexpected box format: {box}")
                    continue
                    
                text_blocks.append({
                    'text': line['text'],
                    'box': box,
                    'center': (center_x, center_y)
                })
            except Exception as e:
                print(f"Error processing box {box}: {str(e)}")
                continue

        if not text_blocks:
            return {'data': []}

        x_weight = 1.0
        y_weight = 1.0

        # 根据文本方向调整聚类参数
        if text_direction == 'vertical':
            # 竖排文本：增加x轴距离权重，减小y轴距离权重
            x_weight = 1.5
            y_weight = 0.75
        else:
            # 横排文本：增加y轴距离权重，减小x轴距离权重
            x_weight = 0.75
            y_weight = 1.5

        # 准备聚类数据
        centers = np.array([block['center'] for block in text_blocks])

        def custom_metric(a, b):
            dx = abs(a[0] - b[0])
            dy = abs(a[1] - b[1])
            
            return dx * x_weight + dy * y_weight

        # 使用OPTICS聚类
        if len(text_blocks) > 1:
            try:
                clustering = OPTICS(
                    min_samples=2,  # 修改为2，满足OPTICS要求
                    metric= custom_metric,
                    max_eps=100,
                    xi = 0.05
                    # cluster_method='dbscan',  # 使用DBSCAN方法
                    # eps=50  # 设置eps阈值
                ).fit(centers)  # 使用中心点坐标进行聚类
                
                labels = clustering.labels_
            except Exception as e:
                print(f"Clustering failed: {str(e)}")
                # 如果聚类失败，将所有文本块视为一个簇
                labels = [0] * len(text_blocks)
        else:
            labels = [0] * len(text_blocks)

        # 合并聚类结果
        merged_results = []
        for label in set(labels):
            if label == -1:  # 跳过噪声点
                # 将噪声点作为单独的文本块
                for i, block in enumerate(text_blocks):
                    if labels[i] == -1:
                        merged_results.append({
                            'text': block['text'],
                            'box': block['box']
                        })
                continue
            
            cluster = [block for i, block in enumerate(text_blocks) if labels[i] == label]
            
            # 根据文本方向排序
            if text_direction == 'vertical': #从上到下，从右到左
                cluster.sort(key=lambda x: (x['center'][1], -x['center'][0]))
            else: #从上到下，从左到右
                cluster.sort(key=lambda x: (x['center'][1], x['center'][0]))
            
            # 合并文本和边界框
            merged_text = '\n'.join(block['text'] for block in cluster)
            
            # 合并边界框
            try:
                all_points = []
                for block in cluster:
                    box = block['box']
                    if len(box) == 8:  # 确保是8点格式
                        points = [(box[i], box[i+1]) for i in range(0, 8, 2)]
                        all_points.extend(points)
                
                if all_points:
                    # 计算边界多边形
                    hull = cv2.convexHull(np.array(all_points))
                    merged_box = hull.flatten().tolist()
                else:
                    # 如果没有有效点，使用第一个文本块的边界框
                    merged_box = cluster[0]['box']
            except Exception as e:
                print(f"Error merging boxes: {str(e)}")
                merged_box = cluster[0]['box']
            
            merged_results.append({
                'text': merged_text,
                'box': merged_box
            })

        return {'data': merged_results}

    def translate_text(self, text, current_context):
        try:
            # 获取当前预设
            settings_manager = SettingsManager()
            current_preset = settings_manager.get_current_preset()
            
            # 获取源语言和目标语言的内部名称
            src_name = self.source_lang  # 已经是英文标识符
            target_name = self.target_lang  # 已经是英文标识符
            
            # 获取共享上下文
            with self._context_lock:
                shared_context = "\n".join(self._shared_context)
                if shared_context:
                    #current_context = f"{shared_context}\n{current_context}"
                    current_context = f"Shared Context:\n{shared_context}\n\nCurrent page:\n{text}"

            system_prompt = """
                                You are a professional comic translation expert specializing in adapting content between Chinese (zh), English (en), Japanese (ja), and Korean (ko). Your task is to provide accurate and culturally appropriate translations while preserving the original meaning and style.

                                Key Requirements:
                                1. Always translate into the specified target language
                                2. Maintain semantic accuracy and emotional tone
                                3. Adapt cultural expressions appropriately for the target language
                                4. Preserve dialogue characteristics and speech patterns specific to the target language
                                5. Keep translations concise to fit speech bubbles
                                6. Be creative with wordplay and humor adaptation
                                7. If this line is already translated in the context, return empty translation

                                Language-Specific Guidelines:
                                - Chinese: Use appropriate measure words, particles (了,的,啊), and maintain natural Chinese expression patterns
                                - Japanese: Use proper keigo levels, sentence-ending particles (ね,よ,か), and natural Japanese word order
                                - Korean: Maintain appropriate honorific levels, sentence-ending particles (요,죠,네), and Korean syntax
                                - English: Use appropriate colloquialisms and natural English expressions

                                Example Translations:

                                1. Korean to Chinese:
                                Input: "빌런이나타났을때거기서만나는거로?"
                                {
                                    "translation": "要是出现反派就在那里碰面吗？",
                                    "original": "빌런이나타났을때거기서만나는거로?",
                                    "remarks": "",
                                    "src_lang": "korean",
                                    "tgt_lang": "chinese"
                                }

                                2. Japanese to Chinese:
                                Input: "明日の天気はどうですか？"
                                {
                                    "translation": "明天天气怎么样？",
                                    "original": "明日の天気はどうですか？",
                                    "remarks": "",
                                    "src_lang": "japanese",
                                    "tgt_lang": "chinese"
                                }

                                3. English to Chinese:
                                Input: "What should we do next?"
                                {
                                    "translation": "我们接下来该做什么？",
                                    "original": "What should we do next?",
                                    "remarks": "",
                                    "src_lang": "english",
                                    "tgt_lang": "chinese"
                                }

                                4. Chinese to Japanese:
                                Input: "你今天过得怎么样？"
                                {
                                    "translation": "今日はどうでしたか？",
                                    "original": "你今天过得怎么样？",
                                    "remarks": "",
                                    "src_lang": "chinese",
                                    "tgt_lang": "japanese"
                                }

                                5. Chinese to Korean:
                                Input: "等一下，我马上来！"
                                {
                                    "translation": "잠깐만요, 금방 갈게요!",
                                    "original": "等一下，我马上来！",
                                    "remarks": "",
                                    "src_lang": "chinese",
                                    "tgt_lang": "korean"
                                }
                                
                                6. Korean to Japanese:
                                Input: "밑어도되는거에요?\n계속일하게하려고아무말이나\n지어내고있는거아니죠?"
                                {
                                    "translation": "本当に大丈夫ですか？ ずっと働かせようとして、適当なことを言っているんじゃないですか？",
                                    "original": "밑어도되는거에요?\n계속일하게하려고아무말이나\n지어내고있는거아니죠?",
                                    "remarks": "",
                                    "src_lang": "korean",
                                    "tgt_lang": "japanese"
                                }

                                When translating:
                                - Fix any OCR-related errors in the source text
                                - Keep untranslatable elements (like "-" or "...") in their original form
                                - If the source text is a single character or word and cannot be translated, keep it as is
                                - Focus only on translating the provided content, not the context
                                - Maintain the same line break format as the source
                                - IMPORTANT: Always output the translation in the specified target language (tgt_lang)

                                Provide your translation in this JSON format without any additional commentary:
                                {
                                    "translation": string,     // Must be in the specified target language
                                    "original": string,        // The original text (corrected if needed)
                                    "remarks": string,         // Leave empty unless critical issues need noting
                                    "src_lang": string,        // Source language code (chinese/english/japanese/korean)
                                    "tgt_lang": string        // Target language code (chinese/english/japanese/korean)
                                }
                                """

            # 构建用户提示
            user_prompt = (
                f'{{"src_lang":"{src_name}","tgt_lang":"{target_name}",'
                f'"reference":"{current_context}","original":"{text}"}}'
            )
            #print("user_prompt:", user_prompt)

            # 根据预设类型选择处理器
            if current_preset['type'] == 'Ollama':
                response = self.ollama_handler(system_prompt, user_prompt, current_preset)
                print("Ollama response:", response)
            else:  # Remote API
                response = self.openai_handler(system_prompt, user_prompt, current_preset)
                print("OpenAI response:", response)

            # 尝试多种方式提取翻译内容
            try:
                # 1. 尝试直接解析 JSON
                result = json.loads(response)
                translated = result.get('translation', '')
            except json.JSONDecodeError:
                try:
                    # 2. 尝试使用正则表达式匹配 JSON 格式的翻译
                    import re
                    json_pattern = r'\{[^}]*"translation"\s*:\s*"([^"]+)"[^}]*\}'
                    match = re.search(json_pattern, response)
                    if match:
                        translated = match.group(1)
                    else:
                        # 3. 尝试匹配引号内的任何内容
                        quote_pattern = r'"([^"]+)"'
                        matches = re.findall(quote_pattern, response)
                        # 选择最长的匹配作为翻译结果
                        translated = max(matches, key=len) if matches else text
                except Exception as e:
                    print(f"正则提取失败: {e}")
                    translated = text

            translated = translated.strip().replace('">', '').replace('</', '')

            # 更新共享上下文
            if translated and translated != text:  # 只有成功翻译且内容不同时才添加到上下文
                with self._context_lock:
                    context_entry = f"{text} -> {translated}"
                    self._shared_context.append(context_entry)
                    # 保持上下文在限定大小内
                    if len(self._shared_context) > self.MAX_CONTEXT_ITEMS:
                        self._shared_context.pop(0)

            return translated or text  # 如果翻译为空则返回原文

        except Exception as e:
            import traceback
            print(f"翻译异常: {str(e)}")
            print("详细异常信息:")
            traceback.print_exc()
            return text

    def ollama_handler(self, system_prompt, user_prompt, preset):
        """Ollama API 处理器"""
        url = preset['api_url']
        model = preset['model']
        
        data = {
            'model': model,
            'messages': [
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': user_prompt
                }
            ],
            'options': {
                'num_predict': 2048
            },
            'stream': False,
            'format': {
                'type': 'object',
                'properties': {
                    'translation': {'type': 'string'},
                    'original': {'type': 'string'},
                    'remarks': {'type': 'string'},
                    'src_lang': {'type': 'string'},
                    'tgt_lang': {'type': 'string'}
                },
                'required': ['translation', 'original', 'src_lang', 'tgt_lang']
            }
        }
        
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()['message']['content']

    def openai_handler(self, system_prompt, user_prompt, preset):
        """OpenAI 兼容 API 处理器"""
        url = preset['api_url']
        model = preset['model']
        bearer_token = preset['bearer_token']
        
        headers = {
            'Content-Type': 'application/json'
        }
        if bearer_token:
            headers['Authorization'] = f'Bearer {bearer_token}'

        data = {
            'model': model,
            'messages': [
                {
                    'role': 'system',
                    'content': system_prompt
                },
                {
                    'role': 'user',
                    'content': user_prompt
                }
            ],
            'stream': False,
            'max_tokens': 2048,
            'temperature': 0.4,
            'top_p': 0.9,
            'top_k': 50,
            'frequency_penalty': 1.0,
            'n': 1,
            'response_format': {
                'type': 'json_schema',
                "json_schema": {
                    "name": "translation_schema",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "translation": {"type": "string"},
                            "original": {"type": "string"},
                            "remarks": {"type": "string"},
                            "src_lang": {"type": "string"},
                            "tgt_lang": {"type": "string"}
                        },
                        "required": ["translation", "original", "src_lang", "tgt_lang"],
                        "additionalProperties": False
                    }
                }
            }
        }

        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']

    def replace_text(self, img, points, translated_text):
        """替换图像中的文本"""
        try:
            # 获取文本方向设置
            settings_manager = SettingsManager()
            text_direction = settings_manager.load_settings().get('text_direction', 'horizontal')

            img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(img_pil)

            # 计算文本框的尺寸
            x_coords = [points[i] for i in range(0, len(points), 2)]
            y_coords = [points[i+1] for i in range(0, len(points), 2)]
            x, y = min(x_coords), min(y_coords)
            w = max(x_coords) - x
            h = max(y_coords) - y

            # 根据文本方向调整文本框和渲染参数
            if text_direction == 'vertical':
                # 竖排文本：将文本分成多列
                min_font_size = 12
                line_spacing_ratio = 0.2
                column_spacing_ratio = 0.5
                # 将文本分成多列，每列从上到下排列
                lines = translated_text.split('\n')
                columns = []
                for line in lines:
                    # 每列字符从上到下排列
                    columns.append(list(line))
                # 列从右到左排列
                columns.reverse()
            else:
                # 横排文本：正常分行
                min_font_size = 12
                line_spacing_ratio = 0.1
                lines = None

            # 分割文本为多行（横排）或多列（竖排）
            def split_text(text, font, max_width):
                if text_direction == 'vertical':
                    # 计算每列最大字符数
                    char_width = font.getlength('あ')  # 使用标准字符宽度
                    max_chars_per_column = int(h / (char_width * (1 + line_spacing_ratio)))
                    
                    # 将文本分成多列
                    columns = []
                    current_column = []
                    for line in text.split('\n'):
                        chars = list(line)
                        if not current_column:
                            current_column.extend(chars)
                        elif len(current_column) + len(chars) <= max_chars_per_column:
                            current_column.extend(chars)
                        else:
                            columns.append(current_column)
                            current_column = list(chars)
                    
                    if current_column:
                        columns.append(current_column)
                    
                    # 列从右到左排列
                    columns.reverse()
                    return columns
                else:
                    # 横排文本的正常分行逻辑
                    lines = []
                    current_line = []
                    current_width = 0

                    for char in text:
                        char_width = font.getlength(char)
                        if char == '\n':
                            if current_line:
                                lines.append(''.join(current_line))
                            current_line = []
                            current_width = 0
                        elif current_width + char_width <= max_width:
                            current_line.append(char)
                            current_width += char_width
                        else:
                            if current_line:
                                lines.append(''.join(current_line))
                            current_line = [char]
                            current_width = char_width

                    if current_line:
                        lines.append(''.join(current_line))
                    return lines

            # 尝试不同字体大小
            selected_font = None
            best_columns = []
            for font_size in range(min(72, max(h, w)), min_font_size-1, -1):
                try:
                    test_font = ImageFont.truetype(self.font_path, font_size)
                except IOError:
                    continue

                if text_direction == 'vertical':
                    # 竖排时，计算总宽度和每列高度
                    columns = split_text(translated_text, test_font, w)
                    char_width = test_font.getlength('あ')
                    total_width = len(columns) * char_width * (1 + column_spacing_ratio)
                    max_height = max(len(col) * char_width * (1 + line_spacing_ratio) for col in columns)
                    
                    if total_width <= w and max_height <= h:
                        selected_font = test_font
                        best_columns = columns
                        break
                else:
                    # 横排文本的逻辑保持不变
                    lines = split_text(translated_text, test_font, w)
                    if not lines:
                        continue

                    line_heights = [draw.textbbox((0,0), line, font=test_font)[3] for line in lines]
                    total_height = sum(line_heights) * (1 + line_spacing_ratio)
                    if total_height <= h:
                        selected_font = test_font
                        best_columns = lines
                        break

            if not selected_font:
                selected_font = ImageFont.truetype(self.font_path, min_font_size)
                best_columns = split_text(translated_text, selected_font, w)

            # 绘制白色背景
            draw.polygon([(points[i], points[i+1]) for i in range(0, len(points), 2)], fill=(255, 255, 255))

            # 计算文本位置并绘制
            if text_direction == 'vertical':
                # 竖排文本渲染
                char_width = selected_font.getlength('あ')
                total_width = len(best_columns) * char_width * (1 + column_spacing_ratio)
                start_x = x + w - char_width  # 从右边开始

                for column in best_columns:
                    # 从上边开始，不再垂直居中
                    start_y = y + char_width * 0.5  # 留出少许上边距

                    # 从上到下绘制每个字符
                    for i, char in enumerate(column):
                        current_y = start_y + i * char_width * (1 + line_spacing_ratio)
                        draw.text((start_x, current_y), char, fill=(0, 0, 0), font=selected_font)

                    # 移动到下一列（向左移动）
                    start_x -= char_width * (1 + column_spacing_ratio)
            else:
                # 横排文本渲染（保持不变）
                line_heights = [draw.textbbox((0,0), line, font=selected_font)[3] for line in best_columns]
                total_height = sum(line_heights) * (1 + line_spacing_ratio)
                current_y = y + (h - total_height) / 2

                for line in best_columns:
                    bbox = draw.textbbox((0,0), line, font=selected_font)
                    text_w = bbox[2] - bbox[0]
                    text_x = x + (w - text_w) / 2
                    draw.text((text_x, current_y), line, fill=(0, 0, 0), font=selected_font)
                    current_y += draw.textbbox((0,0), line, font=selected_font)[3] * (1 + line_spacing_ratio)

            return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        except Exception as e:
            print(f"文本渲染异常: {str(e)}")
            return img

    @classmethod
    def clear_context(cls):
        """清除所有共享上下文"""
        with cls._context_lock:
            cls._shared_context.clear() 

    def run_sync(self):
        """同步运行翻译（用于 Streamlit）"""
        img = cv2.imread(self.image) if isinstance(self.image, str) else self.image
        img = preprocess_image(img)

        result = ocr_through_UmiOCR(img, self.source_lang)
        if result['code'] != 100:
            raise Exception("OCR failed: " + str(result))

        result = self.merge_ocr_results(result)
        context = ''
        translation_dict = {}
        total_boxes = len(result['data'])
        
        for line in result['data']:
            translation_dict[line['text']] = ''

        for i, line in enumerate(result['data'], 1):
            text = line['text'].strip()
            points = line['box']
            translated = self.translate_text(text, context)
            translation_dict[text] = translated
            
            # 更新当前图片的上下文
            for key, value in translation_dict.items():
                if value:
                    context += f"{key} -> {value}\n"
                else:
                    context += f"{key}\n"
                    
            img = self.replace_text(img, points, translated)
            self.progress.emit(i, text, translated)  # 发送进度信号

        return img 