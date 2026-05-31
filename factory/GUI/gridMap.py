import tkinter as tk
from tkinter import messagebox
import requests
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from config import SERVER_URL

class GridControlGUI:
    def __init__(self, root, back_callback=None):
        self.root = root
        self.back_callback = back_callback
        self.root.title("Factory Grid Control GUI")
        self.root.geometry("850x800")

        self.rows = 10
        self.cols = 10
        self.cell_size = 45

        self.mode = "obstacle"
        self.start = None
        self.grid = []

        self.colors = {
            0: "white",        # 이동 가능
            1: "black",        # 장애물
            2: "lightblue",    # 시작점
            3: "lightgreen",   # 등록된 목적지
        }

        self.create_widgets()
        self.create_grid()
        self.load_grid_from_db()

    def create_widgets(self):
        back_frame = tk.Frame(self.root)
        back_frame.pack(fill="x", padx=10, pady=(10,0))

        tk.Button(
            back_frame,
            text="뒤로가기",
            command=self.go_back
        ).pack(side="left")

        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10)

        tk.Label(top_frame, text="Rows:").grid(row=0, column=0)
        self.row_entry = tk.Entry(top_frame, width=5)
        self.row_entry.insert(0, str(self.rows))
        self.row_entry.grid(row=0, column=1, padx=5)

        tk.Label(top_frame, text="Cols:").grid(row=0, column=2)
        self.col_entry = tk.Entry(top_frame, width=5)
        self.col_entry.insert(0, str(self.cols))
        self.col_entry.grid(row=0, column=3, padx=5)

        tk.Button(top_frame, text="격자 생성", command=self.reset_grid).grid(row=0, column=4, padx=10)
        tk.Button(top_frame, text="초기화", command=self.clear_grid).grid(row=0, column=5, padx=5)

        mode_frame = tk.Frame(self.root)
        mode_frame.pack(pady=5)

        tk.Button(mode_frame, text="이동 가능", command=lambda: self.set_mode("free")).grid(row=0, column=0, padx=5)
        tk.Button(mode_frame, text="장애물", command=lambda: self.set_mode("obstacle")).grid(row=0, column=1, padx=5)
        tk.Button(mode_frame, text="시작점", command=lambda: self.set_mode("start")).grid(row=0, column=2, padx=5)
        tk.Button(mode_frame, text="목적지 등록", command=lambda: self.set_mode("location")).grid(row=0, column=3, padx=5)

        self.status_label = tk.Label(self.root, text="현재 모드: 장애물", font=("Arial", 11))
        self.status_label.pack(pady=5)

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_cell_click)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(pady=5)
        


        tk.Button(bottom_frame, text="DB 저장", command=self.save_grid_to_db).grid(row=0, column=0, padx=5)
        tk.Button(bottom_frame, text="DB 불러오기", command=self.load_grid_from_db).grid(row=0, column=1, padx=5)

    def go_back(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        self.root.title("Smart Logistics Robot")
        self.root.geometry("450x350")

        if self.back_callback:
            self.back_callback()
    
    def create_grid(self):
        self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.start = None
        self.draw_grid()

    def reset_grid(self):
        try:
            rows = int(self.row_entry.get())
            cols = int(self.col_entry.get())

            if rows <= 0 or cols <= 0:
                raise ValueError

            self.rows = rows
            self.cols = cols
            self.create_grid()

        except ValueError:
            messagebox.showerror("입력 오류", "행과 열은 1 이상의 정수로 입력해야 합니다.")

    def clear_grid(self):
        self.create_grid()
        self.output_text.delete("1.0", tk.END)

    def draw_grid(self):
        self.canvas.delete("all")

        canvas_width = self.cols * self.cell_size
        canvas_height = self.rows * self.cell_size
        self.canvas.config(width=canvas_width, height=canvas_height)

        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * self.cell_size
                y1 = r * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size

                value = self.grid[r][c]
                color = self.colors.get(value, "white")

                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=color,
                    outline="gray"
                )

                self.canvas.create_text(
                    x1 + self.cell_size / 2,
                    y1 + self.cell_size / 2,
                    text=f"{r+1},{c+1}",
                    font=("Arial", 8)
                )

    def set_mode(self, mode):
        self.mode = mode

        mode_text = {
            "free": "이동 가능",
            "obstacle": "장애물",
            "start": "시작점",
            "location": "목적지 등록",
        }

        self.status_label.config(text=f"현재 모드: {mode_text[mode]}")

    def on_cell_click(self, event):
        col = event.x // self.cell_size
        row = event.y // self.cell_size

        if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
            return

        if self.mode == "free":
            if self.start == (row, col):
                self.start = None
            self.grid[row][col] = 0

        elif self.mode == "obstacle":
            if self.start == (row, col):
                self.start = None
            self.grid[row][col] = 1

        elif self.mode == "start":
            if self.start is not None:
                old_r, old_c = self.start
                self.grid[old_r][old_c] = 0

            self.start = (row, col)
            self.grid[row][col] = 2

        elif self.mode == "location":
            self.register_location_by_cell(row, col)
            return 

        self.draw_grid()

    def get_pathfinding_grid(self):
        """
        A* / D* Lite에 넣기 쉬운 형태로 변환한다.
        0 = 이동 가능
        1 = 이동 불가능

        시작점과 목적지는 이동 가능 칸으로 처리한다.
        위험구역은 일단 이동 가능으로 두되, 나중에 cost를 높이는 방식으로 확장 가능하다.
        """
        path_grid = []

        for r in range(self.rows):
            row_data = []
            for c in range(self.cols):
                if self.grid[r][c] == 1:
                    row_data.append(1)
                else:
                    row_data.append(0)
            path_grid.append(row_data)

        return path_grid

    def save_grid_to_db(self):
        data = {
            "rows": self.rows,
            "cols": self.cols,
            "raw_grid": self.grid,
            "pathfinding_grid": self.get_pathfinding_grid()
        }

        try:
            response = requests.post(
                f"{SERVER_URL}/grid-map",
                json=data,
                timeout=5
            )

            if response.status_code == 200:
                messagebox.showinfo(
                    "DB 저장 완료",
                    "격자 지도가 서버 DB에 저장되었습니다."
                )
            else:
                messagebox.showerror(
                    "DB 저장 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )
        
    def load_grid_from_db(self):
        try:
            response = requests.get(
                f"{SERVER_URL}/grid-map",
                timeout=5
            )

            if response.status_code != 200:
                messagebox.showerror(
                    "DB 불러오기 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )
                return

            data = response.json()

            if data.get("message") == "grid map not found":
                messagebox.showinfo(
                    "DB 불러오기",
                    "DB에 저장된 격자 지도가 없습니다."
                )
                return

            self.rows = data["rows"]
            self.cols = data["cols"]
            self.grid = data["raw_grid"]

            self.start = None

            for r in range(self.rows):
                for c in range(self.cols):
                    if self.grid[r][c] == 2:
                        self.start = (r, c)

            self.apply_locations_to_grid()

            self.row_entry.delete(0, tk.END)
            self.row_entry.insert(0, str(self.rows))

            self.col_entry.delete(0, tk.END)
            self.col_entry.insert(0, str(self.cols))

            self.draw_grid()

            messagebox.showinfo(
                "DB 불러오기 완료",
                "서버 DB에서 격자 지도를 불러왔습니다."
            )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )

        except Exception as e:
            messagebox.showerror(
                "DB 불러오기 오류",
                f"격자 지도를 불러오는 중 오류가 발생했습니다.\n{e}"
            )
    
    def register_location_by_cell(self, row, col):
        # 장애물 칸에는 목적지 등록 불가
        if self.grid[row][col] == 1:
            messagebox.showwarning(
                "목적지 등록 불가",
                "장애물 칸에는 목적지를 등록할 수 없습니다."
            )
            return

        # 시작점 칸에도 목적지 등록 막기
        if self.start == (row, col):
            messagebox.showwarning(
                "목적지 등록 불가",
                "시작점으로 지정된 칸에는 목적지를 등록할 수 없습니다."
            )
            return

        # 이미 목적지로 표시된 칸이면 중복 등록 방지
        if self.grid[row][col] == 3:
            messagebox.showwarning(
                "목적지 등록 불가",
                "이미 목적지로 등록된 칸입니다."
            )
            return

        # 화면 표시 기준 좌표: 1부터 시작
        x = row + 1
        y = col + 1

        zone_name = self.ask_location_name(x, y)

        if not zone_name:
            return

        zone_name = zone_name.strip()

        if not zone_name:
            messagebox.showwarning(
                "입력 오류",
                "구역 이름을 입력해야 합니다."
            )
            return

        try:
            response = requests.post(
                f"{SERVER_URL}/locations",
                params={
                    "zone_name": zone_name,
                    "x": x,
                    "y": y
                },
                timeout=5
            )

            if response.status_code == 200:
                self.grid[row][col] = 3
                self.draw_grid()

                messagebox.showinfo(
                    "목적지 등록 완료",
                    f"{zone_name} 위치가 저장되었습니다.\n좌표: ({x}, {y})"
                )

            else:
                messagebox.showerror(
                    "목적지 등록 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"라즈베리파이 서버에 연결할 수 없습니다.\n{e}"
            )

    def apply_locations_to_grid(self):
        try:
            response = requests.get(
                f"{SERVER_URL}/locations",
                timeout=5
            )

            if response.status_code != 200:
                messagebox.showerror(
                    "목적지 불러오기 오류",
                    f"서버 응답 오류\n상태 코드: {response.status_code}\n{response.text}"
                )
                return

            locations = response.json()

            for location in locations:
                x = location.get("x")
                y = location.get("y")

                if x is None or y is None:
                    continue

                # DB에는 1,1 기준으로 저장되어 있으므로
                # 파이썬 grid 인덱스 기준으로 -1 변환
                row = x - 1
                col = y - 1

                if row < 0 or row >= self.rows or col < 0 or col >= self.cols:
                    continue

                # 장애물이나 시작점은 덮어쓰지 않음
                if self.grid[row][col] == 1:
                    continue

                if self.grid[row][col] == 2:
                    continue

                self.grid[row][col] = 3

        except requests.exceptions.RequestException as e:
            messagebox.showerror(
                "서버 연결 오류",
                f"목적지 목록을 불러올 수 없습니다.\n{e}"
            )

    def ask_location_name(self, x, y):
        dialog = tk.Toplevel(self.root)
        dialog.title("목적지 등록")
        dialog.geometry("420x230")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        result = {"value": None}

        main_frame = tk.Frame(dialog)
        main_frame.pack(expand=True, fill="both", padx=30, pady=20)

        coord_label = tk.Label(
            main_frame,
            text=f"선택한 좌표\nx: {x}\ny: {y}",
            font=("Arial", 11),
            justify="left"
        )
        coord_label.pack(anchor="w", pady=(0, 15))

        input_label = tk.Label(
            main_frame,
            text="구역 이름을 입력하세요.",
            font=("Arial", 11)
        )
        input_label.pack(anchor="w")

        entry = tk.Entry(main_frame, width=28, font=("Arial", 11))
        entry.pack(anchor="w", pady=(5, 15))
        entry.focus_set()

        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=5)

        def on_ok():
            value = entry.get().strip()

            if not value:
                messagebox.showwarning(
                    "입력 오류",
                    "구역 이름을 입력해야 합니다.",
                    parent=dialog
                )
                return

            result["value"] = value
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        tk.Button(
            button_frame,
            text="OK",
            width=12,
            command=on_ok
        ).grid(row=0, column=0, padx=8)

        tk.Button(
            button_frame,
            text="Cancel",
            width=12,
            command=on_cancel
        ).grid(row=0, column=1, padx=8)

        dialog.bind("<Return>", lambda event: on_ok())
        dialog.bind("<Escape>", lambda event: on_cancel())

        self.root.wait_window(dialog)

        return result["value"]