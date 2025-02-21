let foundImages = [];

// 加载保存的设置
document.addEventListener('DOMContentLoaded', () => {
    const statusElement = document.getElementById('imageCount');
    statusElement.textContent = "正在扫描图片...";

    chrome.storage.local.get(['serverUrl'], (result) => {
        if (result.serverUrl) {
            document.getElementById('serverUrl').value = result.serverUrl;
        }
    });

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs[0]) {
            statusElement.textContent = "无法访问当前页面";
            return;
        }

        chrome.scripting.executeScript({
            target: { tabId: tabs[0].id },
            function: scanImages
        })
        .then(([result]) => {
            if (!result || !result.result) {
                statusElement.textContent = "未找到图片";
                return;
            }

            foundImages = result.result;
            statusElement.textContent = `找到 ${foundImages.length} 张图片`;

            const startIndexInput = document.getElementById('startIndex');
            startIndexInput.max = foundImages.length;
            startIndexInput.min = 1;
        })
        .catch(error => {
            console.error('Scanning error:', error);
            statusElement.textContent = "扫描出错: " + error.message;
        });
    });

    document.getElementById('sendButton').addEventListener('click', () => {
        const serverUrl = document.getElementById('serverUrl').value;
        chrome.storage.local.set({ serverUrl });
        sendImages();
    });
});

document.getElementById('serverUrl').addEventListener('change', (e) => {
    chrome.storage.local.set({ serverUrl: e.target.value });
});

// 获取图片的 Base64 数据
function getImageFromPage(imgSrc) {
    return new Promise((resolve, reject) => {
        const img = document.querySelector(`img[src="${imgSrc}"]`);
        if (!img) return reject('图片元素不存在');

        // 新增：克隆图片以解除CORS限制
        const clonedImg = new Image();
        clonedImg.crossOrigin = "anonymous"; 
        clonedImg.src = img.src + (img.src.includes('?') ? '&' : '?') + 'no-cache=' + Date.now();

        clonedImg.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = clonedImg.naturalWidth;
            canvas.height = clonedImg.naturalHeight;
            
            const ctx = canvas.getContext('2d');
            ctx.drawImage(clonedImg, 0, 0);
            
            resolve(canvas.toDataURL('image/jpeg', 0.9));
        };

        clonedImg.onerror = () => reject('图片加载失败');
    });
}


// 发送图片
async function sendImages() {
    const startIndex = (parseInt(document.getElementById('startIndex').value) || 1) - 1;
    let serverUrl = document.getElementById('serverUrl').value;

    if (!serverUrl.endsWith('/translate')) {
        serverUrl = serverUrl.replace(/\/?$/, '/translate');
    }

    const statusElement = document.getElementById('status');
    const imageCountElement = document.getElementById('imageCount');

    if (!foundImages.length) {
        imageCountElement.textContent = '未找到图片';
        return;
    }
    if (!serverUrl) {
        statusElement.textContent = '请输入服务器地址';
        return;
    }

    statusElement.textContent = `开始处理 ${foundImages.length} 张图片...`;

    const imagesToProcess = foundImages.slice(startIndex);
    for (let i = 0; i < imagesToProcess.length; i++) {
        try {
            let base64Data;
            let imageUrl = imagesToProcess[i];

            statusElement.textContent = `处理第 ${i + 1}/${imagesToProcess.length} 张图片...`;

            try {
                const response = await fetch(imageUrl, {
                    cache: 'force-cache',
                    headers: { 'Cache-Control': 'max-age=31536000' }
                });

                const blob = await response.blob();
                console.log(`Image ${i + 1} Blob Type:`, blob.type);

                if (!blob.type.startsWith('image/')) {
                    throw new Error(`Invalid MIME type: ${blob.type}`);
                }

                base64Data = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                        if (!reader.result) {
                            reject(new Error('Empty reader result'));
                            return;
                        }
                        resolve(reader.result);
                    };
                    reader.onerror = reject;
                    reader.readAsDataURL(blob);
                });

            } catch (fetchError) {
                console.warn(`Fetch failed for image ${i + 1}, trying getImageFromPage:`, fetchError);

                base64Data = await new Promise((resolve, reject) => {
                    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                        if (!tabs[0]) {
                            reject(new Error('No active tab found'));
                            return;
                        }
                        chrome.scripting.executeScript({
                            target: { tabId: tabs[0].id },
                            function: getImageFromPage,
                            args: [imageUrl]
                        }).then(([result]) => {
                            if (result.result) {
                                resolve(result.result);
                            } else {
                                reject(new Error('Failed to get image from page'));
                            }
                        }).catch(reject);
                    });
                });
            }

            try {
                await new Promise((resolve, reject) => {
                    chrome.runtime.sendMessage({
                        action: 'sendToServer',
                        base64Data: base64Data,
                        serverUrl: serverUrl
                    }, response => {
                        if (chrome.runtime.lastError) {
                            reject(chrome.runtime.lastError);
                        } else if (response && response.error) {
                            reject(new Error(response.error));
                        } else {
                            resolve();
                        }
                    });
                });
            } catch (sendError) {
                console.error(`发送图片 ${i + 1} 失败:`, sendError);
                statusElement.textContent = `图片 ${i + 1} 发送失败: ${sendError.message}`;
                continue;
            }

            await new Promise(resolve => setTimeout(resolve, 500));

        } catch (error) {
            console.error(`处理图片 ${i + 1} 时出错:`, error);
            statusElement.textContent = `处理出错，已停止: ${error.message}`;
            return;
        }
    }

    statusElement.textContent = '所有图片处理完成！';
}


// 扫描页面中的图片
function scanImages() {
    const images = [];
    const processedSrcs = new Set();
    const validExtensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];

    function traverseNode(node) {
        if (node.nodeType === Node.ELEMENT_NODE && node.tagName === 'IMG' && node.src &&
            node.width > 100 && node.height > 100) {
            const cleanSrc = node.src.trim();
            const ext = cleanSrc.split('.').pop().toLowerCase();
            if ((cleanSrc.startsWith('http://') || cleanSrc.startsWith('https://')) &&
                validExtensions.includes(ext) &&
                !processedSrcs.has(cleanSrc)) {
                images.push(cleanSrc);
                processedSrcs.add(cleanSrc);
            }
        }

        for (const child of node.childNodes) {
            traverseNode(child);
        }
    }

    traverseNode(document.body);
    return images;
}