import tkinter as tk
from tkinter import messagebox, filedialog
import json
import sqlite3
import os
import sys
import requests

SERVER_URL = "http://taesula.local:8000" 

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
        self.goal = None
        self.grid = []

        self.db_path = self.get_db_path()

        self.colors = {
            0: "white",        # 이동 가능
            1: "black",        # 장애물
            2: "lightblue",    # 시작점
            3: "lightgreen",   # 목적지
            4: "orange"        # 위험구역 / 주의구역
        }

        self.create_widgets()
        self.create_grid()

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
        tk.Button(mode_frame, text="목적지", command=lambda: self.set_mode("goal")).grid(row=0, column=3, padx=5)

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
        self.root.geometry("350x250")

        if self.back_callback:
            self.back_callback()
    
    def create_grid(self):
        self.grid = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.start = None
        self.goal = None
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
                    text=f"{r},{c}",
                    font=("Arial", 8)
                )

    def set_mode(self, mode):
        self.mode = mode

        mode_text = {
            "free": "이동 가능",
            "obstacle": "장애물",
            "start": "시작점",
            "goal": "목적지",
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
            if self.goal == (row, col):
                self.goal = None
            self.grid[row][col] = 0

        elif self.mode == "obstacle":
            if self.start == (row, col):
                self.start = None
            if self.goal == (row, col):
                self.goal = None
            self.grid[row][col] = 1

        elif self.mode == "start":
            if self.start is not None:
                old_r, old_c = self.start
                self.grid[old_r][old_c] = 0

            if self.goal == (row, col):
                self.goal = None

            self.start = (row, col)
            self.grid[row][col] = 2

        elif self.mode == "goal":
            if self.goal is not None:
                old_r, old_c = self.goal
                self.grid[old_r][old_c] = 0

            if self.start == (row, col):
                self.start = None

            self.goal = (row, col)
            self.grid[row][col] = 3

        elif self.mode == "danger":
            if self.start == (row, col):
                self.start = None
            if self.goal == (row, col):
                self.goal = None
            self.grid[row][col] = 4

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
    
    def get_db_path(self):
        if getattr(sys, 'frozen', False):
            # exe로 실행될 때 기준
            base_dir = os.path.dirname(sys.executable)
        else:
            # python gridMap.py / client.py로 실행될 때 기준
            base_dir = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(os.path.join(base_dir, "..", "SIDA_system.db"))

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
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            cur.execute("SELECT rows, cols, raw_grid FROM grid_map WHERE id = 1")
            row = cur.fetchone()

            conn.close()

            if row is None:
                messagebox.showinfo("DB 불러오기", "DB에 저장된 격자 지도가 없습니다.")
                return

            rows, cols, raw_grid_json = row

            self.rows = rows
            self.cols = cols
            self.grid = json.loads(raw_grid_json)

            self.start = None
            self.goal = None

            for r in range(self.rows):
                for c in range(self.cols):
                    if self.grid[r][c] == 2:
                        self.start = (r, c)
                    elif self.grid[r][c] == 3:
                        self.goal = (r, c)

            self.row_entry.delete(0, tk.END)
            self.row_entry.insert(0, str(self.rows))

            self.col_entry.delete(0, tk.END)
            self.col_entry.insert(0, str(self.cols))

            self.draw_grid()

            messagebox.showinfo("DB 불러오기 완료", "DB에서 격자 지도를 불러왔습니다.")

        except Exception as e:
            messagebox.showerror("DB 불러오기 오류", f"DB에서 격자 지도를 불러오는 중 오류가 발생했습니다.\n{e}")