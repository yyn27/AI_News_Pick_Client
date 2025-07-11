# main.py

import sys
import os
import multiprocessing

def patch_konlpy_java_path():
    # 只在PyInstaller打包环境下生效
    if hasattr(sys, '_MEIPASS'):
        konlpy_java_dir = os.path.join(sys._MEIPASS, 'konlpy', 'java')
        if os.path.exists(konlpy_java_dir):
            os.environ['KONLPY_JAVA_PATH'] = konlpy_java_dir

patch_konlpy_java_path()

from gui.app_gui import run_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from gui.app_gui import run_gui
    run_gui()
