import tkinter as tk
from tkinter import ttk, messagebox
import requests
from PIL import Image, ImageTk
import io
import random
import threading
from collections import deque
import json
import os
import time
import win32clipboard
import win32con
from io import BytesIO

class PollinationsViewer:
    def __init__(self, master):
        self.master = master
        master.title("POLLISAVER")
        master.geometry("800x580")
        master.resizable(False, False)  # Disable resizing of the window

        self.always_on_top = tk.BooleanVar()
        self.enhance = tk.BooleanVar()  # Variable to store the state of the "Enhance" checkbox
        self.load_settings()

        self.prompt_history = deque(maxlen=20)
        self.setup_ui()
        self.load_history()
        
        self.is_running = False
        self.current_image = None
        self.viewer_thread = None
        self.fullscreen_window = None  # Window for fullscreen image display
        self.fullscreen_image = None  # Fullscreen image object
        self.max_retries = 5  # Maximum number of retry attempts
        self.retry_delay = 5  # Delay between retries in seconds
        self.retrying = False  # Indicates if retrying is in process
        self.current_request_id = None  # Track current request to allow canceling

        # Bind the closing event to ensure the thread stops
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.master.wm_attributes("-topmost", self.always_on_top.get())

    def setup_ui(self):
        # Menu bar for options
        menubar = tk.Menu(self.master)
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(label="Always on Top", onvalue=True, offvalue=False,
                                     variable=self.always_on_top, command=self.toggle_always_on_top)
        menubar.add_cascade(label="Options", menu=options_menu)
        self.master.config(menu=menubar)

        self.frame = ttk.Frame(self.master, padding="10")
        self.frame.pack(fill=tk.BOTH, expand=True)

        # Top area for input controls
        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill=tk.X)

        prompt_label = ttk.Label(input_frame, text="Prompt:")
        prompt_label.grid(column=0, row=0, sticky=tk.W, padx=(0, 10))
        self.prompt_entry = tk.Text(input_frame, wrap=tk.WORD, height=2)
        self.prompt_entry.grid(column=1, row=0, columnspan=5, sticky=(tk.W, tk.E), padx=(0, 10))

        history_label = ttk.Label(input_frame, text="History:")
        history_label.grid(column=0, row=1, sticky=tk.W, padx=(0, 10))
        self.history_var = tk.StringVar()
        self.history_dropdown = ttk.Combobox(input_frame, textvariable=self.history_var)
        self.history_dropdown.grid(column=1, row=1, columnspan=5, sticky=(tk.W, tk.E), padx=(0, 10))
        self.history_dropdown.bind('<<ComboboxSelected>>', self.on_history_select)

        interval_label = ttk.Label(input_frame, text="Interval (minutes):")
        interval_label.grid(column=0, row=2, sticky=tk.W, padx=(0, 10))
        self.interval_entry = ttk.Entry(input_frame, width=4)  # Adjusted width to 4 characters
        self.interval_entry.grid(column=1, row=2, sticky=(tk.W, tk.E), padx=(0, 10))
        self.interval_entry.insert(0, "1")

        self.start_stop_button = ttk.Button(input_frame, text="Start", command=self.toggle_start_stop)
        self.start_stop_button.grid(column=2, row=2, sticky=tk.W, padx=(10, 0))

        self.fullscreen_button = ttk.Button(input_frame, text="Fullscreen", command=self.toggle_fullscreen, state=tk.DISABLED)
        self.fullscreen_button.grid(column=3, row=2, sticky=tk.W, padx=(10, 0))

        # Enhance checkbox
        self.enhance_checkbox = ttk.Checkbutton(input_frame, text="Enhance", variable=self.enhance)
        self.enhance_checkbox.grid(column=4, row=2, sticky=tk.W, padx=(10, 0))

        # Image display area
        self.image_frame = ttk.Frame(self.frame, relief="flat", borderwidth=0)
        self.image_frame.pack(expand=True, fill=tk.BOTH)

        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(expand=True)

        # Context menu for right-click
        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Copy to Clipboard", command=self.copy_to_clipboard)

        # Bind right-click to the image label
        self.image_label.bind("<Button-3>", self.show_context_menu)

    def toggle_start_stop(self):
        if self.is_running:
            self.stop_viewer()
        else:
            self.start_viewer()

    def on_history_select(self, event):
        selected_prompt = self.history_var.get()
        self.prompt_entry.delete(1.0, tk.END)
        self.prompt_entry.insert(tk.END, selected_prompt)

    def add_to_history(self, prompt):
        if prompt and prompt not in self.prompt_history:
            self.prompt_history.appendleft(prompt)
            self.update_history_dropdown()
            self.save_history()

    def update_history_dropdown(self):
        self.history_dropdown['values'] = list(self.prompt_history)
        if self.prompt_history:
            self.history_var.set(self.prompt_history[0])

    def save_history(self):
        with open('prompt_history.json', 'w') as f:
            json.dump(list(self.prompt_history), f)

    def load_history(self):
        if os.path.exists('prompt_history.json'):
            with open('prompt_history.json', 'r') as f:
                self.prompt_history = deque(json.load(f), maxlen=20)
        self.update_history_dropdown()

    def start_viewer(self):
        prompt = self.prompt_entry.get("1.0", tk.END).strip()
        self.add_to_history(prompt)
        
        try:
            interval = max(0.1, float(self.interval_entry.get())) * 60
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the interval.")
            return
        
        if not prompt:
            messagebox.showerror("Missing Prompt", "Please enter a prompt.")
            return

        self.is_running = True
        self.start_stop_button.config(text="Stop")
        self.current_request_id = random.randint(1, 1000000)  # Generate a unique request ID
        
        self.viewer_thread = threading.Thread(target=self.run_viewer, args=(prompt, interval, self.current_request_id))
        self.viewer_thread.start()

    def stop_viewer(self):
        self.is_running = False
        self.start_stop_button.config(text="Start")
        self.current_request_id = None  # Invalidate current request ID to stop ongoing fetching

    def toggle_fullscreen(self):
        if not self.current_image:  # Prevent entering fullscreen if no image is loaded
            messagebox.showerror("No Image", "There is no image to display in fullscreen.")
            return

        if self.fullscreen_window:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self):
        self.fullscreen_window = tk.Toplevel(self.master)
        self.fullscreen_window.attributes('-fullscreen', True)
        self.fullscreen_window.configure(bg='black')

        self.fullscreen_image_label = tk.Label(self.fullscreen_window, bg='black')
        self.fullscreen_image_label.pack(expand=True, fill=tk.BOTH)

        self.display_fullscreen_image(self.current_image)

        self.fullscreen_window.bind('<Escape>', self.exit_fullscreen)
        self.fullscreen_window.bind('<space>', self.exit_fullscreen)

    def exit_fullscreen(self, event=None):
        if self.fullscreen_window:
            self.fullscreen_window.destroy()
            self.fullscreen_window = None

    def run_viewer(self, prompt, interval, request_id):
        while self.is_running and request_id == self.current_request_id:
            self.fetch_and_display_image(prompt, request_id)
            time.sleep(interval)

    def fetch_and_display_image(self, prompt, request_id):
        seed = random.randint(1, 1000000)
        enhance_param = "true" if self.enhance.get() else "false"
        url = f"https://image.pollinations.ai/prompt/{prompt}?nologo=true&nofeed=true&enhance={enhance_param}&seed={seed}&width=1920&height=1080"
        
        for attempt in range(self.max_retries):
            if not self.is_running or request_id != self.current_request_id:
                return  # Stop if the process is not running or a new request has been made
            
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    image = Image.open(io.BytesIO(response.content))
                    self.current_image = image
                    self.master.after(0, self.display_image, image)
                    self.master.after(0, self.display_fullscreen_image, image)  # Update fullscreen image as well
                    self.fullscreen_button.config(state=tk.NORMAL)  # Enable fullscreen button as soon as image is loaded
                    break  # Exit the loop on success
            except Exception as e:
                time.sleep(self.retry_delay)  # Wait before retrying

    def display_image(self, image):
        if image is None:
            return

        self.display_preview_image(image)

    def display_preview_image(self, image):
        img_width, img_height = image.size
        aspect_ratio = img_width / img_height

        # Set the frame size to maintain the aspect ratio of the image
        self.image_frame.update_idletasks()
        frame_width = self.image_frame.winfo_width()
        frame_height = int(frame_width / aspect_ratio)
        
        self.image_frame.config(height=frame_height)

        max_width = frame_width
        max_height = frame_height

        scale = min(max_width / img_width, max_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        try:
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            photo_image = ImageTk.PhotoImage(resized_image)

            self.image_label.config(image=photo_image)
            self.image_label.image = photo_image
            
        except Exception as e:
            pass

    def display_fullscreen_image(self, image):
        if self.fullscreen_window is None:
            return

        screen_width = self.fullscreen_window.winfo_screenwidth()
        screen_height = self.fullscreen_window.winfo_screenheight()

        img_width, img_height = image.size
        scale = min(screen_width / img_width, screen_height / img_height)
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        try:
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            fullscreen_image = ImageTk.PhotoImage(resized_image)

            self.fullscreen_image_label.config(image=fullscreen_image)
            self.fullscreen_image_label.image = fullscreen_image

        except Exception as e:
            pass

    def show_context_menu(self, event):
        try:
            self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_to_clipboard(self):
        if self.current_image is None:
            messagebox.showerror("No Image", "There is no image to copy.")
            return

        output = BytesIO()
        self.current_image.convert("RGB").save(output, format="BMP")
        data = output.getvalue()[14:]  # Skip the BMP header
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()

    def toggle_always_on_top(self):
        self.master.wm_attributes("-topmost", self.always_on_top.get())
        self.save_settings()

    def save_settings(self):
        settings = {
            "always_on_top": self.always_on_top.get(),
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)

    def load_settings(self):
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                self.always_on_top.set(settings.get("always_on_top", False))

    def on_closing(self):
        self.stop_viewer()  # Ensure the viewer thread stops
        self.master.destroy()  # Close the GUI window

if __name__ == "__main__":
    root = tk.Tk()
    app = PollinationsViewer(root)
    root.mainloop()
