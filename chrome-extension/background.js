// 获取图片的MIME类型
function getMimeType(url) {
    const ext = url.split('.').pop().toLowerCase();
    const mimeTypes = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
        'gif': 'image/gif'
    };
    return mimeTypes[ext] || 'image/jpeg';
}

// 发送图片到服务器的函数
function sendImageToServer(base64Data, serverUrl = 'http://127.0.0.1:11451/translate') {
    console.log('Sending image data to:', serverUrl);
    
    // 检查 base64Data 格式
    if (!base64Data.startsWith('data:image/')) {
        console.error('Invalid base64 data format');
        return Promise.reject(new Error('Invalid image data format'));
    }

    // 添加请求头
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Origin': '*',
        'Referer': '*'
    };

    return fetch(serverUrl, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({
            image: base64Data
        })
    })
    .then(async response => {
        if (!response.ok) {
            // 尝试获取详细的错误信息
            let errorDetail = '';
            try {
                const errorJson = await response.json();
                errorDetail = JSON.stringify(errorJson);
            } catch (e) {
                errorDetail = await response.text();
            }
            
            console.error('Server error details:', {
                status: response.status,
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries()),
                error: errorDetail
            });
            
            throw new Error(`Server responded with ${response.status}: ${errorDetail}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Server response:', data);
        if (data.status === 'success') {
            return Promise.resolve();
        } else {
            throw new Error(data.error || '发送失败');
        }
    })
    .catch(error => {
        console.error('Request failed:', error);
        // 检查是否是跨域问题
        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            throw new Error('可能是跨域问题，请检查服务器CORS设置');
        }
        throw error;
    });
}

// 处理图片转换
function convertImageToBase64(img, mimeType = 'image/jpeg') {
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    
    // 对于 WebP，先在白色背景上绘制
    if (mimeType === 'image/webp') {
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    }
    
    ctx.drawImage(img, 0, 0);
    
    try {
        // 尝试保持原始格式
        return canvas.toDataURL(mimeType, 1.0);
    } catch (e) {
        console.warn('Failed to use original format, falling back to JPEG');
        return canvas.toDataURL('image/jpeg', 0.95);
    }
}

// 创建右键菜单
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "translateImage",
        title: "翻译此图片",
        contexts: ["image"]
    });
});

// 处理右键菜单点击
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "translateImage") {
        console.log('Right-click menu clicked, URL:', info.srcUrl);
        processAndSendImage(info.srcUrl);
    }
});

// 处理来自弹出页面的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'sendToServer') {
        // 使用已有的 sendImageToServer 函数处理
        sendImageToServer(request.base64Data, request.serverUrl)
            .then(() => {
                sendResponse({ success: true });
            })
            .catch(error => {
                sendResponse({ error: error.message });
            });
        
        return true; // 保持消息通道开放
    }
});

// 处理单个图片
async function processAndSendImage(url, serverUrl) {
    try {
        console.log('Processing image:', url);
        const response = await fetch(url);
        const blob = await response.blob();
        const base64Data = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
        await sendImageToServer(base64Data, serverUrl);
        
        chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icon48.png',
            title: '图片已发送',
            message: '图片已成功发送到翻译服务器'
        });
        
        return true;
    } catch (error) {
        console.error('Error processing image:', url, error);
        throw error;
    }
}

// 按顺序处理多个图片
async function processImagesSequentially(images, serverUrl) {
    console.log(`Starting to process ${images.length} images to ${serverUrl}`);
    for (const url of images) {
        try {
            await processAndSendImage(url, serverUrl);
            await new Promise(resolve => setTimeout(resolve, 500));
        } catch (error) {
            console.error('Failed to process image:', url);
            throw error;
        }
    }
} 