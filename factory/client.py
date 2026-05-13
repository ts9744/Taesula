import tkinter as tk
from tkinter import messagebox
from gridMap import GridControlGUI


class FactoryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Logistics Robot")
        self.root.geometry("350x250")

        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="Taesula",
            font=("Arial", 16, "bold")
        )
        title_label.pack(pady=20)

        recognize_button = tk.Button(
            self.root,
            text="물품 인식",
            width=20,
            height=2,
            command=self.recognize_item
        )
        recognize_button.pack(pady=8)

        register_button = tk.Button(
            self.root,
            text="물품 등록",
            width=20,
            height=2,
            command=self.register_item
        )
        register_button.pack(pady=8)

        grid_button = tk.Button(
            self.root,
            text="격자 생성",
            width=20,
            height=2,
            command=self.create_grid
        )
        grid_button.pack(pady=8)

    def recognize_item(self):
        messagebox.showinfo("물품 인식", "물품 인식 기능은 추후 연결 예정입니다.")

    def register_item(self):
        messagebox.showinfo("물품 등록", "물품 등록 기능은 추후 연결 예정입니다.")

    def create_grid(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        GridControlGUI(self.root)

if __name__ == "__main__":
    root = tk.Tk()
    app = FactoryGUI(root)
    root.mainloop()