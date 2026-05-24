import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageTk
import qrcode
import requests

SERVER_URL = "http://192.168.0.28:8000"

class QRGeneratorApp:
    def __init__(self, root, back_callback=None):
        self.root = root
        self.back_callback = back_callback
        self.root.title("QR Generator")
        self.root.geometry("420x520")
        self.root.resizable(False, False)

        self.qr_image = None
        self.qr_preview = None
        self.locations = []

        self.create_widgets()
        self.load_locations()

    def create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="Item 등록 및 QR 생성",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=15)

        back_frame = tk.Frame(self.root)
        back_frame.pack(fill="x", padx=10, pady=(10,0))

        tk.Button(
            back_frame,
            text="뒤로가기",
            command=self.go_back
        ).pack(side="left")

        guide_label = tk.Label(
            self.root,
            text="DB에 없는 item을 서버 DB에 등록하고 QR 코드를 생성합니다.",
            font=("Arial", 10)
        )
        guide_label.pack()

        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=15)

        tk.Label(input_frame, text="Item 이름").grid(
            row=0, column=0, padx=5, pady=5, sticky="e"
        )

        self.item_entry = tk.Entry(input_frame, width=28, font=("Arial", 12))
        self.item_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(input_frame, text="목적지").grid(
            row=1, column=0, padx=5, pady=5, sticky="e"
        )

        self.location_combo = ttk.Combobox(input_frame, width=26, state="readonly")
        self.location_combo.grid(row=1, column=1, padx=5, pady=5)

        refresh_button = tk.Button(
            input_frame,
            text="목적지 새로고침",
            command=self.load_locations
        )
        refresh_button.grid(row=2, column=1, padx=5, pady=5, sticky="e")

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        register_button = tk.Button(
            button_frame,
            text="DB 저장 + QR 생성",
            width=18,
            command=self.register_item_and_generate_qr
        )
        register_button.grid(row=0, column=0, padx=5)

        clear_button = tk.Button(
            button_frame,
            text="초기화",
            width=12,
            command=self.clear_qr
        )
        clear_button.grid(row=0, column=1, padx=5)

        self.preview_label = tk.Label(
            self.root,
            text="QR 미리보기",
            width=300,
            height=300,
            bg="white",
            relief="solid"
        )
        self.preview_label.pack(pady=20)

        self.status_label = tk.Label(
            self.root,
            text="라즈베리파이 서버가 실행 중이어야 합니다.",
            font=("Arial", 9),
            fg="gray"
        )
        self.status_label.pack(pady=5)

        info_label = tk.Label(
            self.root,
            text="※ QR 내부 값은 서버 DB의 items.qr_code 값과 동일하게 저장됩니다.",
            font=("Arial", 9),
            fg="gray"
        )
        info_label.pack(pady=5)

    def load_locations(self):
        try:
            response = requests.get(f"{SERVER_URL}/locations", timeout=3)

            if response.status_code != 200:
                messagebox.showerror(
                    "서버 오류",
                    f"목적지 목록 조회 실패\nstatus code: {response.status_code}\n{response.text}"
                )
                return

            self.locations = response.json()

            combo_values = [
                f"{loc['id']} - {loc['zone_name']} ({loc['x']}, {loc['y']})"
                for loc in self.locations
            ]

            self.location_combo["values"] = combo_values

            if combo_values:
                self.location_combo.current(0)
                self.status_label.config(
                    text="목적지 목록을 서버에서 불러왔습니다.",
                    fg="gray"
                )
            else:
                self.status_label.config(
                    text="등록된 목적지가 없습니다. 먼저 /locations에 목적지를 추가하세요.",
                    fg="red"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결하지 못했습니다.\n\n{e}"
            )

    def register_item_and_generate_qr(self):
        item_name = self.item_entry.get().strip()
        selected_location = self.location_combo.get()

        if not item_name:
            messagebox.showwarning("입력 오류", "item 이름을 입력하세요.")
            return

        if not selected_location:
            messagebox.showwarning("입력 오류", "목적지를 선택하세요.")
            return

        if "/" in item_name:
            messagebox.showwarning("입력 오류", "item 이름에는 '/' 문자를 사용할 수 없습니다.")
            return

        destination_id = int(selected_location.split(" - ")[0])

        # 현재 테스트 규칙: item 이름과 qr_code 값을 동일하게 사용
        qr_code = item_name

        try:
            response = requests.post(
                f"{SERVER_URL}/items",
                params={
                    "name": item_name,
                    "qr_code": qr_code,
                    "destination_id": destination_id
                },
                timeout=3
            )

            if response.status_code != 200:
                messagebox.showerror(
                    "저장 오류",
                    f"서버 DB 저장 실패\nstatus code: {response.status_code}\n{response.text}"
                )
                return

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"아이템 저장 요청 실패\n\n{e}"
            )
            return

        self.generate_qr_image(qr_code)

        self.status_label.config(
            text=f"서버 DB 저장 완료 / QR 생성 완료: {qr_code}",
            fg="green"
        )

        messagebox.showinfo(
            "완료",
            f"아이템이 라즈베리파이 서버 DB에 저장되고 QR 코드가 생성되었습니다.\n\n"
            f"item: {item_name}\nqr_code: {qr_code}"
        )

    def generate_qr_image(self, qr_text):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )

        qr.add_data(qr_text)
        qr.make(fit=True)

        self.qr_image = qr.make_image(
            fill_color="black",
            back_color="white"
        ).convert("RGB")

        preview_image = self.qr_image.resize((280, 280))
        self.qr_preview = ImageTk.PhotoImage(preview_image)

        self.preview_label.config(image=self.qr_preview, text="")

    def clear_qr(self):
        self.item_entry.delete(0, tk.END)
        self.qr_image = None
        self.qr_preview = None
        self.preview_label.config(image="", text="QR 미리보기")
        self.status_label.config(text="입력값이 초기화되었습니다.", fg="gray")

    def go_back(self):
        if self.back_callback:
            self.back_callback()
        else:
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()