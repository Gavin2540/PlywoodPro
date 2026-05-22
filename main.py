import sys
import os

# Ensure the root folder is on the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from views.app_window import AppWindow

def main():
    try:
        app = AppWindow()
        app.mainloop()
    except Exception as e:
        import tkinter as tk
        from tkinter import messagebox
        # Fallback dialog if initialization fails before window loop starts
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Fatal Launch Error",
            f"PlywoodPro failed to initialize or launch:\n\n{e}\n\nPlease check your Python installation and packages."
        )

if __name__ == "__main__":
    main()
