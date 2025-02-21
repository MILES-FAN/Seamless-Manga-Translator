# Seamless Manga Translator

[English](#english) | [中文](#中文) | [日本語](#日本語)

![Translator](https://github.com/user-attachments/assets/08ad11f1-d536-41c3-a37c-9d5e0ffe670c)
![Result](https://github.com/user-attachments/assets/978cf9a8-6550-4229-a8ec-53736a8d19f7)


# English

## Overview
Seamless Manga Translator is a powerful tool designed to translate manga and comics between multiple languages. It supports OCR text detection and translation between English, Chinese, Japanese, and Korean.

### Features
- Multiple language support (English, Chinese, Japanese, Korean)
- OCR text detection using UmiOCR
- Multiple translation backends (Ollama, Remote API)
- Browser extension for easy image translation
- Customizable text direction (horizontal/vertical)
- Translation context preservation

### Installation
1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Umi-OCR and set HTTP service to ON


Go to https://github.com/hiroi-sora/Umi-OCR

Download the latest [release](https://github.com/hiroi-sora/Umi-OCR/releases)

Turn on the HTTP service in advanced settings (Detailed instructions can be found in the Umi-OCR README)


### Usage
#### GUI Application

```bash
python main.py
```

#### Configuration
- API settings can be configured through the interface
- Supports multiple translation presets
- Settings are automatically saved

---

# 中文

## 概述
Seamless Manga Translator 是一个功能强大的漫画翻译工具，支持多语言之间的翻译。它可以识别和翻译英文、中文、日文和韩文等多种语言的漫画文本。

### 功能特点
- 多语言支持（英文、中文、日文、韩文）
- 使用 UmiOCR 进行文字识别
- 多种翻译后端（Ollama、远程API）
- 浏览器扩展支持
- 可自定义文字方向（横排/竖排）
- 保持翻译上下文

### 安装方法
1. 克隆仓库
2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 安装 Umi-OCR 并设置 HTTP 服务为 ON

前往 https://github.com/hiroi-sora/Umi-OCR

下载最新 [release](https://github.com/hiroi-sora/Umi-OCR/releases)

在高级设置中开启 HTTP 服务（详细说明请参考 Umi-OCR README）


### 使用方法
#### GUI 应用程序

```bash
python main.py
```

#### 设置
- API 设置可以通过界面配置
- 支持多种翻译预设
- 设置会自动保存

# 日本語

## 概要
Seamless Manga Translator は、マンガやコミックを多言語間で翻訳するための便利なツールで、英語、中国語、日本語、韓国語間のテキスト検出と翻訳を機能している。

### 特徴
- 多言語サポート（英語、中国語、日本語、韓国語）
- UmiOCR を使用したテキスト検出
- 複数の翻訳バックエンド（Ollama、リモートAPI）
- ブラウザ拡張機能
- カスタマイズ可能なテキスト方向（水平/垂直）
- コンテキストに応じた翻訳

### インストール方法
1. リポジトリをクローン

2. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```
3. Umi-OCR をインストールし、HTTP サービスを有効にする

https://github.com/hiroi-sora/Umi-OCR　から最新のリリースを[ダウンロード](https://github.com/hiroi-sora/Umi-OCR/releases)

高級設定で HTTP サービスを有効にする（Umi-OCR READMEに参照）


### 利用方法
#### GUI アプリケーション

```bash
python main.py
```

#### 設定
- API 設定はインターフェースで設定できる
- 複数の翻訳プリセットをサポート
- 設定は自動保存される



