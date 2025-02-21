from flask import Flask, request
from flask_cors import CORS
import base64
import numpy as np
import cv2

class ImageServer:
    def __init__(self, manga_translator):
        self.app = Flask(__name__)
        CORS(self.app)
        self.manga_translator = manga_translator
        
        @self.app.route('/translate', methods=['POST'])
        def translate_image():
            try:
                data = request.get_json()
                if not data or 'image' not in data:
                    return {'error': 'No image data received'}, 400
                
                img_data = base64.b64decode(data['image'].split(',')[1])
                nparr = np.frombuffer(img_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                self.manga_translator.add_to_queue(img)
                
                return {'status': 'success'}, 200
            except Exception as e:
                return {'error': str(e)}, 500
    
    def run(self):
        self.app.run(host='127.0.0.1', port=11451) 