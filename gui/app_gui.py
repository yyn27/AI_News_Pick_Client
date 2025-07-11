# ✅ gui/app_gui.py

import sys
import os

import threading
import time
import importlib
import traceback
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QFileDialog, QMessageBox, QTextEdit,
    QProgressBar, QHBoxLayout, QComboBox, QGroupBox, QFormLayout
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QTimer,pyqtSignal

def resource_path(relative_path):
    """兼容PyInstaller和源码运行的资源路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# ==== 경로 설정 ====
LOG_DIR = resource_path("data/log")

VALID_USERS = {"gm": "pyk202020", "test": "test"}

def run_gui():
    app = QApplication(sys.argv)
    login = LoginWindow()
    login.show()
    app.exec_()
    # 强制退出，防止残留线程阻塞
    os._exit(0)

class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI News Pick 로그인")
        self.setGeometry(100, 100, 350, 250)
        self.setStyleSheet("background-color: #f4f7fb; font-family: 'Segoe UI'; font-size: 14px;")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        logo_label = QLabel(self)
        pixmap = QPixmap(resource_path("resources/companyLogo.png"))
        logo_label.setPixmap(pixmap.scaledToWidth(180, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        self.setWindowIcon(QIcon(resource_path("resources/companyLogo2.png")))

        form_group = QGroupBox()
        form_group.setStyleSheet("QGroupBox { border: none; margin-top: 10px; }")
        form_layout = QFormLayout()

        self.user_input = QLineEdit(self)
        self.user_input.setPlaceholderText("아이디")
        self.pass_input = QLineEdit(self)
        self.pass_input.setPlaceholderText("비밀번호")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.style_inputs([self.user_input, self.pass_input])

        form_layout.addRow(QLabel("ID"), self.user_input)
        form_layout.addRow(QLabel("Password"), self.pass_input)
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)

        login_btn = QPushButton("로그인", self)
        login_btn.setStyleSheet("background-color: #2e8bff; color: white; padding: 10px; border-radius: 6px;")
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)

        self.setLayout(layout)

    def style_inputs(self, inputs):
        for widget in inputs:
            widget.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 8px;
                    background-color: #fff;
                }
            """)

    def handle_login(self):
        user = self.user_input.text()
        pwd = self.pass_input.text()
        if VALID_USERS.get(user) == pwd:
            self.main_window = MainApp()
            self.main_window.show()
            self.close()
        else:
            QMessageBox.warning(self, "오류", "아이디 또는 비밀번호가 잘못되었습니다.")

class MainApp(QWidget):
    success_signal = pyqtSignal(str)
    fail_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI News Pick")
        self.setGeometry(100, 100, 640, 520)
        self.setWindowIcon(QIcon(resource_path("resources/companyLogo2.png")))
        self.setStyleSheet("background-color: #f4f7fb; font-family: 'Segoe UI'; font-size: 14px;")
        self.init_ui()
        
        self.stop_event = threading.Event()
        self.worker_thread = None

        self.success_signal.connect(self.show_success_popup)
        self.fail_signal.connect(self.show_failure_popup)
        
        self.user_stopped = False  # 是否用户主动中止

    def init_ui(self):
        layout = QVBoxLayout()

        logo_label = QLabel(self)
        pixmap = QPixmap(resource_path("resources/companyLogo.png"))
        logo_label.setPixmap(pixmap.scaledToWidth(160, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        top_row = QHBoxLayout()

        mode_group = QGroupBox("🛠 기능 선택")
        mode_layout = QVBoxLayout()
        self.mode_select = QComboBox()
        self.mode_select.addItems(["네이버 원문 매칭", "블로그 데이터 전처리"])
        self.mode_select.setStyleSheet("padding: 5px; border-radius: 4px; background-color: white;")
        mode_layout.addWidget(self.mode_select)
        mode_group.setLayout(mode_layout)
        top_row.addWidget(mode_group)

        api_group = QGroupBox("NAVER API")
        api_layout = QFormLayout()
        self.cid_input = QLineEdit()
        self.cid_input.setPlaceholderText("NAVER_CLIENT_ID")
        self.secret_input = QLineEdit()
        self.secret_input.setPlaceholderText("NAVER_CLIENT_SECRET")
        self.style_inputs([self.cid_input, self.secret_input])
        api_layout.addRow("Client ID:", self.cid_input)
        api_layout.addRow("Client Secret:", self.secret_input)
        api_group.setLayout(api_layout)
        top_row.addWidget(api_group)

        layout.addLayout(top_row)

        io_group = QGroupBox("입출력 설정")
        io_layout = QVBoxLayout()
        self.input_label = QLabel("① 입력 파일 선택")
        io_layout.addWidget(self.input_label)
        input_btn = QPushButton("입력 파일 선택")
        input_btn.clicked.connect(self.choose_input_file)
        io_layout.addWidget(input_btn)

        io_layout.addWidget(QLabel("② 출력 파일 이름 입력 (확장자 제외)"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("예: output_filename")
        io_layout.addWidget(self.name_input)

        self.output_label = QLabel("③ 출력 폴더 선택")
        io_layout.addWidget(self.output_label)
        output_btn = QPushButton("출력 폴더 선택")
        output_btn.clicked.connect(self.choose_output_folder)
        io_layout.addWidget(output_btn)

        self.style_inputs([self.name_input])
        io_group.setLayout(io_layout)
        layout.addWidget(io_group)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶ 시작")
        self.start_btn.clicked.connect(self.start_process)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ 중지")
        self.stop_btn.clicked.connect(self.stop_process)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.progress.setTextVisible(False)
        btn_row.addWidget(self.progress)

        layout.addLayout(btn_row)

        layout.addWidget(QLabel("📜 Log"))
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #fff; border: 1px solid #ccc; border-radius: 5px;")
        layout.addWidget(self.log_view)

        self.setLayout(layout)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_log)

    def style_inputs(self, inputs):
        for widget in inputs:
            widget.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #bbb;
                    border-radius: 5px;
                    padding: 6px;
                    background-color: #ffffff;
                }
            """)

    def choose_input_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "엑셀 파일 선택", "", "Excel Files (*.xlsx)")
        if file:
            self.input_path = file
            self.input_label.setText(f"선택된 입력 파일: {os.path.basename(file)}")

    def choose_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "출력 폴더 선택")
        if folder:
            self.output_folder = folder
            self.output_label.setText(f"선택된 폴더: {folder}")

    def show_success_popup(self, output_file):
        self.timer.stop()
        self.progress.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        QMessageBox.information(self, "완료", f"작업 완료! 파일: {output_file}")
        self.input_label.setText("✅ 완료되었습니다!")

    def show_failure_popup(self, code):
        self.timer.stop()
        self.progress.setVisible(False)
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        if code == -2:
            self.input_label.setText("⏹ 중단됨")
        else:
            QMessageBox.critical(self, "실패", f"오류 발생 (코드: {code})")
            self.input_label.setText("❌ 오류 발생")

    def start_process(self):
        if not hasattr(self, "input_path") or not hasattr(self, "output_folder"):
            QMessageBox.warning(self, "입력 부족", "입력 파일과 출력 폴더를 선택하세요.")
            return

        mode = self.mode_select.currentText()
        cid = self.cid_input.text().strip()
        secret = self.secret_input.text().strip()
        output_name = self.name_input.text().strip()

        if mode == "네이버 원문 매칭" and (not cid or not secret):
            QMessageBox.warning(self, "API 필수", "NAVER_CLIENT_ID와 SECRET을 입력하세요.")
            return

        if not output_name:
            QMessageBox.warning(self, "출력 이름 없음", "결과 파일 이름을 입력하세요.")
            return

        output_file = os.path.join(self.output_folder, output_name + ".xlsx")
        self.log_file = os.path.join(LOG_DIR, f"로그_{time.strftime('%y%m%d')}.txt")
        self.output_file_path = output_file

        self.stop_event.clear()
        self.log_view.clear()
        self.progress.setVisible(True)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        def run():
            try:
                if mode == "네이버 원문 매칭":
                    mod = importlib.import_module("core.main_scripts_blog_ui_api")
                    mod.main(self.input_path, output_file, cid, secret,stop_event=self.stop_event)
                else:
                    mod = importlib.import_module("core.preprocessing")
                    mod.run_preprocessing(self.input_path, output_file, stop_event=self.stop_event)

                if self.user_stopped or self.stop_event.is_set():
                    self.user_stopped = False  # ✅ 重置标志，不弹窗
                    self.fail_signal.emit(-2)  # -2表示用户中断
                    return
                self.success_signal.emit(output_file)
            except Exception as e:
                # 写入详细异常到log文件
                with open(self.log_file, "a", encoding="utf-8", errors="replace") as f:
                    f.write(traceback.format_exc())
                self.fail_signal.emit(-1)
                
        self.timer.start(1000)
        self.worker_thread = threading.Thread(target=run, daemon=True)  # 保存线程对象
        self.worker_thread.start()

    def stop_process(self):
        self.user_stopped = True  
        self.stop_event.set()

    def closeEvent(self, event):
        # 当窗口关闭时，终止后台线程
        try:
            self.stop_event.set()
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
            if hasattr(self, "worker_thread") and self.worker_thread and self.worker_thread.is_alive():
                # 最多等3秒
                self.worker_thread.join(timeout=3)
        except Exception as e:
            pass
        event.accept()

    def update_log(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()[-100:]
                    self.log_view.setPlainText("".join(lines))
                    self.log_view.verticalScrollBar().setValue(
                        self.log_view.verticalScrollBar().maximum()
                    )
        except Exception as e:
            self.log_view.append(f"[로그 읽기 오류]: {e}")