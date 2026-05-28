import tkinter as tk
import threading
import time
import requests
from PIL import Image, ImageTk
import io
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from config import SERVER_URL

class ItemScanGUI:
    def __init__(self, root, back_callback=None):
        self.root = root
        self.back_callback = back_callback

        self.root.title("Item Scan GUI")
        self.root.geometry("800x720")

        self.camera_running = False
        self.last_qr = None
        self.last_detect_time = 0

        self.latest_image_data = None
        self.frame_lock = threading.Lock()
        self.video_rendering = False

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
        title_label.pack(pady=10)

        guide_label = tk.Label(
            self.root,
            text="라즈베리파이 카메라로 QR 코드를 인식합니다.",
            font=("Arial", 11)
        )
        guide_label.pack(pady=5)

        self.video_label = tk.Label(
            self.root,
            text="카메라 화면 대기 중",
            bg="black",
            fg="white"
        )
        self.video_label.pack(pady=10)

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
            width=90,
            height=10
        )
        self.result_text.pack(padx=10, pady=10)

        self.result_text.insert(
            tk.END,
            "인식 시작 버튼을 누른 뒤 QR 코드를 라즈베리파이 카메라에 비추세요.\n"
        )

    def start_scan(self):
        if self.camera_running:
            return

        self.camera_running = True
        self.last_qr = None
        self.last_detect_time = 0

        self.status_label.config(text="상태: 라즈베리파이 카메라 연결 중")

        video_thread = threading.Thread(target=self.video_read_loop)
        video_thread.daemon = True
        video_thread.start()

        qr_thread = threading.Thread(target=self.scan_loop)
        qr_thread.daemon = True
        qr_thread.start()

        if not self.video_rendering:
            self.video_rendering = True
            self.render_video_frame()

    def video_read_loop(self):
        stream_url = f"{SERVER_URL}/camera/stream"

        try:
            response = requests.get(stream_url, stream=True, timeout=5)
            bytes_data = b""

            for chunk in response.iter_content(chunk_size=4096):
                if not self.camera_running:
                    break

                bytes_data += chunk

                start = bytes_data.find(b"\xff\xd8")
                end = bytes_data.find(b"\xff\xd9")

                if start != -1 and end != -1:
                    jpg = bytes_data[start:end + 2]
                    bytes_data = bytes_data[end + 2:]

                    with self.frame_lock:
                        self.latest_image_data = jpg

        except requests.exceptions.RequestException as e:
            self.show_message(f"카메라 스트림 연결 실패\n{e}")
            self.camera_running = False

    def render_video_frame(self):
        if not self.camera_running:
            self.video_rendering = False
            return

        jpg = None

        with self.frame_lock:
            if self.latest_image_data is not None:
                jpg = self.latest_image_data

        if jpg is not None:
            try:
                image = Image.open(io.BytesIO(jpg))
                image = image.resize((480, 360))

                photo = ImageTk.PhotoImage(image)

                self.video_label.config(image=photo, text="")
                self.video_label.image = photo

            except Exception:
                pass

        self.root.after(33, self.render_video_frame)

    def scan_loop(self):
        while self.camera_running:
            try:
                response = requests.get(f"{SERVER_URL}/camera/qr", timeout=3)

                if response.status_code != 200:
                    self.show_message("QR 인식 API 호출 실패")
                    time.sleep(1.5)
                    continue

                data = response.json()

                if data.get("detected"):
                    qr_code = data.get("qr_code")

                    if qr_code == self.last_qr:
                        time.sleep(1.5)
                        continue

                    route_info = self.create_route_by_qr(qr_code)
                    self.show_result(qr_code, route_info)

                    self.last_qr = qr_code
                    self.last_detect_time = time.time()

                    self.camera_running = False
                    self.root.after(0, lambda: self.status_label.config(text="상태: QR 인식 완료"))
                    break

                time.sleep(1.5)

            except requests.exceptions.RequestException as e:
                self.show_message(f"라즈베리파이 서버 연결 실패\n{e}")
                time.sleep(1.5)

    def create_route_by_qr(self, qr_code):
        try:
            response = requests.get(f"{SERVER_URL}/route/{qr_code}", timeout=3)

            if response.status_code == 200:
                return response.json()

            return {
                "message" : "route api error",
                "status_code": response.status_code
            }

        except requests.exceptions.RequestException as e:
            return {
                "message" : "server connection error",
                "detail" : str(e)
            }

    def show_result(self, qr_code, route_info):
        def update_gui():
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, f"인식된 QR 코드: {qr_code}\n\n")

            if route_info is None:
                self.result_text.insert(
                    tk.END,
                    "경로 생성 요청에 실패했습니다.\n"
                )
                self.status_label.config(text="상태: 경로 생성 실패")
                return

            if route_info.get("message") != "route found":
                self.result_text.insert(tk.END, "경로 생성 실패\n\n")
                self.result_text.insert(tk.END, f"응답 메시지: {route_info.get('message')}\n")

                if "detail" in route_info:
                    self.result_text.insert(tk.END, f"상세 정보: {route_info.get('detail')}\n")

                self.status_label.config(text="상태: 경로 생성 실패")
                return

            item = route_info.get("item", {})
            robot = route_info.get("robot", {})
            destination = route_info.get("destination", {})
            path = route_info.get("path", [])
            command_path = route_info.get("command_path", [])

            self.result_text.insert(tk.END, "경로 생성 성공\n\n")
            self.result_text.insert(tk.END, f"물품명: {item.get('name')}\n")
            self.result_text.insert(tk.END, f"물품 상태: {item.get('status')}\n\n")

            self.result_text.insert(
                tk.END,
                f"현재 로봇 위치: ({robot.get('current_x')}, {robot.get('current_y')})\n"
            )

            self.result_text.insert(
                tk.END,
                f"목적지: {destination.get('zone_name')} "
                f"({destination.get('x')}, {destination.get('y')})\n\n"
            )

            self.result_text.insert(tk.END, f"좌표 경로 개수: {len(path)}개\n")
            self.result_text.insert(tk.END, f"명령 개수: {len(command_path)}개\n")
            self.result_text.insert(tk.END, f"명령 경로: {command_path}\n\n")
            self.result_text.insert(
                tk.END,
                "ESP32가 /next-command API를 호출하면 위 명령을 순서대로 받아갑니다.\n"
            )

            self.status_label.config(text="상태: 경로 생성 완료")

        self.root.after(0, update_gui)

    def show_message(self, msg):
        def update_gui():
            self.status_label.config(text="상태: 연결 확인 필요")
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, msg + "\n")

        self.root.after(0, update_gui)

    def stop_scan(self):
        self.camera_running = False
        self.video_rendering = False
        self.status_label.config(text="상태: 인식 중지")

    def go_back(self):
        self.stop_scan()

        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title("Smart Logistics Robot")
        self.root.geometry("350x250")

        if self.back_callback:
            self.back_callback()