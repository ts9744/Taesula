import tkinter as tk
from tkinter import messagebox, ttk
import requests
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(BASE_DIR))

from config import MAIN_GUI_SIZE, SERVER_URL


class ItemManageGUI:
    def __init__(self, root, back_callback=None):
        self.root = root
        self.back_callback = back_callback

        self.root.title("Item Manage GUI")
        self.root.geometry("950x700")

        self.locations = []
        self.selected_qr_code = None
        self.item_data_map = {}

        self.create_widgets()
        self.load_items()
        self.load_locations()

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
            text="물품 관리",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)

        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=10)

        tk.Label(input_frame, text="물품명").grid(row=0, column=0, padx=5, pady=5)
        self.name_entry = tk.Entry(input_frame, width=25)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(input_frame, text="목적지").grid(row=1, column=0, padx=5, pady=5)

        self.destination_combo = ttk.Combobox(
            input_frame,
            width=23,
            state="readonly"
        )
        self.destination_combo.grid(row=1, column=1, padx=5, pady=5)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="전체 조회",
            width=15,
            command=self.load_items
        ).grid(row=0, column=0, padx=5)

        tk.Button(
            button_frame,
            text="수정",
            width=15,
            command=self.update_item
        ).grid(row=0, column=1, padx=5)

        tk.Button(
            button_frame,
            text="삭제",
            width=15,
            command=self.delete_item
        ).grid(row=0, column=2, padx=5)

        tk.Button(
            button_frame,
            text="입력 초기화",
            width=15,
            command=self.clear_inputs
        ).grid(row=0, column=3, padx=5)

        self.status_label = tk.Label(
            self.root,
            text="상태: 대기 중",
            font=("Arial", 11)
        )
        self.status_label.pack(pady=5)

        table_frame = tk.Frame(self.root)
        table_frame.pack(padx=10, pady=10, fill="x")

        columns = ("id", "name", "destination_id")

        self.item_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=10
        )

        self.item_table.heading("id", text="ID")
        self.item_table.heading("name", text="물품명")
        self.item_table.heading("destination_id", text="목적지 ID")

        self.item_table.column("id", width=60, anchor="center")
        self.item_table.column("name", width=180, anchor="center")
        self.item_table.column("destination_id", width=100, anchor="center")

        y_scrollbar = tk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.item_table.yview
        )

        x_scrollbar = tk.Scrollbar(
            table_frame,
            orient="horizontal",
            command=self.item_table.xview
        )

        self.item_table.configure(
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        self.item_table.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.item_table.bind("<<TreeviewSelect>>", self.on_item_select)

        self.result_text = tk.Text(
            self.root,
            width=100,
            height=8
        )
        self.result_text.pack(padx=10, pady=10)

    def load_items(self):
        try:
            response = requests.get(
                f"{SERVER_URL}/items",
                timeout=5
            )

            if response.status_code != 200:
                messagebox.showerror(
                    "조회 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )
                return

            items = response.json()

            for row in self.item_table.get_children():
                self.item_table.delete(row)

            self.item_data_map = {}

            if not items:
                self.status_label.config(text="상태: 등록된 물품 없음")
                return

            for item in items:
                row_id = self.item_table.insert(
                    "",
                    tk.END,
                    values=(
                        item.get("id"),
                        item.get("name"),
                        item.get("destination_id"),
                    )
                )

                self.item_data_map[row_id] = item

            self.status_label.config(text="상태: 물품 목록 조회 완료")

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )

    def on_item_select(self, event):
        selected = self.item_table.selection()

        if not selected:
            return

        row_id = selected[0]
        item = self.item_data_map.get(row_id)

        if not item:
            return

        item_id = item.get("id")
        name = item.get("name")
        qr_code = item.get("qr_code")
        destination_id = item.get("destination_id")

        self.selected_qr_code = qr_code

        self.name_entry.config(state="normal")
        self.name_entry.delete(0, tk.END)
        self.name_entry.insert(0, name)

        for value in self.destination_combo["values"]:
            if value.startswith(f"{destination_id} - "):
                self.destination_combo.set(value)
                break

        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "선택한 물품 정보\n\n")
        self.result_text.insert(tk.END, f"ID: {item_id}\n")
        self.result_text.insert(tk.END, f"물품명: {name}\n")
        self.result_text.insert(tk.END, f"목적지 ID: {destination_id}\n")

    def update_item(self):
        qr_code = self.selected_qr_code
        name = self.name_entry.get().strip()
        selected_location = self.destination_combo.get()

        if not name:
            messagebox.showwarning("입력 오류", "물품명을 입력하세요.")
            return
        
        if not selected_location:
            messagebox.showwarning("입력 오류", "목적지를 선택하세요.")
            return

        destination_id = int(selected_location.split(" - ")[0])

        answer = messagebox.askyesno(
            "수정 확인",
            f"물품명 [{name}] 물품 정보를 수정하시겠습니까?"
        )

        if not answer:
            return

        try:
            response = requests.put(
                f"{SERVER_URL}/items/{qr_code}",
                params={
                    "name": name,
                    "destination_id": destination_id
                },
                timeout=5
            )

            if response.status_code == 200:
                self.result_text.delete("1.0", tk.END)
                self.result_text.insert(tk.END, "물품 수정 완료\n\n")
                self.result_text.insert(tk.END, f"QR 코드: {qr_code}\n")
                self.result_text.insert(tk.END, f"물품명: {name}\n")
                self.result_text.insert(tk.END, f"목적지 ID: {destination_id}\n")

                self.status_label.config(text="상태: 물품 수정 완료")
                messagebox.showinfo("수정 완료", "물품 정보가 수정되었습니다.")
                self.load_items()

            else:
                messagebox.showerror(
                    "수정 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )

    def delete_item(self):
        qr_code = self.selected_qr_code

        if not qr_code:
            messagebox.showwarning("삭제 오류", "삭제할 물품을 먼저 선택하세요.")
            return

        name = self.name_entry.get().strip()
        answer = messagebox.askyesno(
            "삭제 확인",
            f"[{name}] 물품을 삭제하시겠습니까?"
        )

        if not answer:
            return

        try:
            response = requests.delete(
                f"{SERVER_URL}/items/{qr_code}",
                timeout=5
            )

            if response.status_code == 200:
                self.result_text.delete("1.0", tk.END)
                self.result_text.insert(tk.END, "물품 삭제 완료\n\n")
                self.result_text.insert(tk.END, f"삭제된 QR 코드: {qr_code}\n")

                self.status_label.config(text="상태: 물품 삭제 완료")
                messagebox.showinfo("삭제 완료", "물품 정보가 삭제되었습니다.")

                self.clear_inputs()
                self.load_items()

            elif response.status_code == 404:
                messagebox.showwarning(
                    "삭제 실패",
                    "DB에서 해당 QR 코드의 물품을 찾지 못했습니다."
                )

            else:
                messagebox.showerror(
                    "삭제 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )

    def clear_inputs(self):
        self.selected_qr_code = None

        self.name_entry.delete(0, tk.END)

        self.destination_combo.set("")

        for selected in self.item_table.selection():
            self.item_table.selection_remove(selected)

        self.result_text.delete("1.0", tk.END)
        self.status_label.config(text="상태: 입력 초기화 완료")

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

            self.destination_combo["values"] = combo_values

            if combo_values:
                self.destination_combo.set("")
                self.status_label.config(
                    text="목적지 목록을 서버에서 불러왔습니다.",
                    fg="gray"
                )
            else:
                self.status_label.config(
                    text="등록된 목적지가 없습니다. 먼저 격자 생성에서 목적지를 추가하세요.",
                    fg="red"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결하지 못했습니다.\n\n{e}"
            )

    def go_back(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.title("Smart Logistics Robot")
        self.root.geometry(MAIN_GUI_SIZE)

        if self.back_callback:
            self.back_callback()