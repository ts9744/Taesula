import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import qrcode


class QRGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Generator")
        self.root.geometry("420x520")
        self.root.resizable(False, False)

        self.qr_image = None
        self.qr_preview = None

        self.create_widgets()

    def create_widgets(self):
        title_label = tk.Label(
            self.root,
            text="QR 코드 생성기",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=15)

        guide_label = tk.Label(
            self.root,
            text="QR 코드를 생성할 item 이름을 입력하세요.",
            font=("Arial", 10)
        )
        guide_label.pack()

        self.qr_entry = tk.Entry(self.root, width=30, font=("Arial", 13))
        self.qr_entry.pack(pady=10)

        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        generate_button = tk.Button(
            button_frame,
            text="QR 생성",
            width=12,
            command=self.generate_qr
        )
        generate_button.grid(row=0, column=0, padx=5)

        save_button = tk.Button(
            button_frame,
            text="저장",
            width=12,
            command=self.save_qr
        )
        save_button.grid(row=0, column=1, padx=5)

        self.preview_label = tk.Label(
            self.root,
            text="QR 미리보기",
            width=300,
            height=300,
            bg="white",
            relief="solid"
        )
        self.preview_label.pack(pady=20)

        info_label = tk.Label(
            self.root,
            text="※ 입력한 item 이름은 DB의 items.qr_code 값과 같아야 합니다.",
            font=("Arial", 9),
            fg="gray"
        )
        info_label.pack(pady=5)

    def generate_qr(self):
        item_name = self.qr_entry.get().strip()

        if not item_name:
            messagebox.showwarning("입력 오류", "item 이름을 입력하세요.")
            return

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4
        )

        qr.add_data(item_name)
        qr.make(fit=True)

        self.qr_image = qr.make_image(
            fill_color="black",
            back_color="white"
        ).convert("RGB")

        preview_image = self.qr_image.resize((280, 280))
        self.qr_preview = ImageTk.PhotoImage(preview_image)

        self.preview_label.config(image=self.qr_preview, text="")

    def save_qr(self):
        if self.qr_image is None:
            messagebox.showwarning("저장 오류", "먼저 QR 코드를 생성하세요.")
            return

        item_name = self.qr_entry.get().strip()
        safe_name = item_name.replace(" ", "_")

        file_path = filedialog.asksaveasfilename(
            initialfile=f"{safe_name}.png",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png")]
        )

        if not file_path:
            return

        self.qr_image.save(file_path)
        messagebox.showinfo("저장 완료", "QR 코드 이미지가 저장되었습니다.")


if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()