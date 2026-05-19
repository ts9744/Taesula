import tkinter as tk
from tkinter import messagebox
import threading
import time
import cv2
import requests
import platform

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None


SERVER_URL = "http://127.0.0.1:8000"


class ItemScanGUI:
    def __init__(self, root, back_callback=None):
        self.root = root
        self.back_callback = back_callback

        self.root.title("Item Scan GUI")
        self.root.geometry("700x500")

        self.camera_running = False
        self.picam2 = None
        self.last_qr = None
        self.last_detect_time = 0

        self.create_widgets()

    def create_widgets(self):
        back_frame = tk.Frame(self.root)
        back_frame.pack(fill="x", padx=10, pady=(10, 0))

        tk.Button(
            back_frame,
            text="뒤로가기",
            command=self.go_back
        ).pack(side="left")

        title_label = tk.Label(
            self.root,
            text="물품 인식",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=15)

        guide_label = tk.Label(
            self.root,
            text="라즈베리파이 카메라로 QR 코드를 인식합니다.",
            font=("Arial", 11)
        )
        guide_label.pack(pady=5)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="인식 시작",
            width=15,
            height=2,
            command=self.start_scan
        ).grid(row=0, column=0, padx=8)

        tk.Button(
            button_frame,
            text="인식 중지",
            width=15,
            height=2,
            command=self.stop_scan
        ).grid(row=0, column=1, padx=8)

        self.status_label = tk.Label(
            self.root,
            text="상태: 대기 중",
            font=("Arial", 11)
        )
        self.status_label.pack(pady=5)

        self.result_text = tk.Text(
            self.root,
            width=75,
            height=14
        )
        self.result_text.pack(padx=10, pady=10)

        self.result_text.insert(
            tk.END,
            "인식 시작 버튼을 누른 뒤 QR 코드를 카메라에 비추세요.\n"
        )

    def start_scan(self):
        if self.camera_running:
            return

        if platform.system() != "Linux" or Picamera2 is None:
            messagebox.showinfo(
                "안내",
                "현재 환경에서는 라즈베리파이 카메라를 사용할 수 없습니다.\n"
                "Windows에서는 GUI 화면 전환만 테스트하고,\n"
                "실제 QR 인식은 라즈베리파이에서 실행해야 합니다."
            )
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, "Windows 테스트 모드입니다.\n")
            self.result_text.insert(tk.END, "라즈베리파이에서 실행하면 카메라 인식이 동작합니다.\n")
            return

        self.camera_running = True
        self.status_label.config(text="상태: 카메라 실행 중")

        thread = threading.Thread(target=self.scan_loop)
        thread.daemon = True
        thread.start()

    def scan_loop(self):
        try:
            self.picam2 = Picamera2()

            config = self.picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            self.picam2.configure(config)
            self.picam2.start()

            detector = cv2.QRCodeDetector()

            while self.camera_running:
                frame = self.picam2.capture_array()

                qr_data, points, _ = detector.detectAndDecode(frame)

                if qr_data:
                    now = time.time()

                    if qr_data != self.last_qr or now - self.last_detect_time > 3:
                        item_info = self.get_item_info(qr_data)
                        self.show_result(qr_data, item_info)

                        self.last_qr = qr_data
                        self.last_detect_time = now

                time.sleep(0.05)

        except Exception as e:
            self.show_error(e)

        finally:
            self.close_camera()

    def get_item_info(self, qr_code):
        try:
            url = f"{SERVER_URL}/items/{qr_code}"
            response = requests.get(url, timeout=3)

            if response.status_code == 200:
                return response.json()

            return None

        except requests.exceptions.RequestException:
            return None

    def show_result(self, qr_code, item_info):
        def update_gui():
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, f"인식된 QR 코드: {qr_code}\n\n")

            if item_info is None:
                self.result_text.insert(
                    tk.END,
                    "DB에서 해당 QR 코드의 물품 정보를 찾지 못했습니다.\n"
                )
            else:
                self.result_text.insert(tk.END, "물품 정보 조회 성공\n\n")
                self.result_text.insert(tk.END, f"{item_info}\n")

        self.root.after(0, update_gui)

    def show_error(self, error):
        def update_gui():
            messagebox.showerror("카메라 오류", str(error))
            self.status_label.config(text="상태: 오류 발생")

        self.root.after(0, update_gui)

    def stop_scan(self):
        self.camera_running = False
        self.status_label.config(text="상태: 인식 중지")

    def close_camera(self):
        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except:
                pass

            self.picam2 = None

    def go_back(self):
        self.stop_scan()
        self.close_camera()

        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title("Smart Logistics Robot")
        self.root.geometry("350x250")

        if self.back_callback:
            self.back_callback()