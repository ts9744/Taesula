import sys
from pathlib import Path
import tkinter as tk
from gridMap import GridControlGUI
from item.itemScan import ItemScanGUI
from item.itemRegister import ItemRegisterGUI
from item.itemManage import ItemManageGUI

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parents[1]

GUI_DIR = BASE_DIR / "GUI"

sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(GUI_DIR))

from config import MAIN_GUI_SIZE


class FactoryGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Logistics Robot")
        self.root.geometry(MAIN_GUI_SIZE)

        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="Taesula",
            font=("Arial", 40, "bold")
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

        delete_button = tk.Button(
            self.root,
            text="물품 관리",
            width=20,
            height=2,
            command=self.manage_item
        )
        delete_button.pack(pady=8)

        grid_button = tk.Button(
            self.root,
            text="격자 생성",
            width=20,
            height=2,
            command=self.create_grid
        )
        grid_button.pack(pady=8)

    def recognize_item(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        ItemScanGUI(self.root, back_callback=self.create_widgets)

    def register_item(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        ItemRegisterGUI(self.root, back_callback=self.create_widgets)

    def create_grid(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        GridControlGUI(self.root, back_callback=self.create_widgets)

    def manage_item(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        ItemManageGUI(self.root, back_callback=self.create_widgets)

if __name__ == "__main__":
    root = tk.Tk()
    app = FactoryGUI(root)
    root.mainloop()