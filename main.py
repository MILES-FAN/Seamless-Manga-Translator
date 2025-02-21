import sys
from PyQt5.QtWidgets import QApplication
from src.gui.main_window import MangaTranslator

def main():
    # 初始化Qt应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MangaTranslator()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())

if __name__ == '__main__':
    main() 