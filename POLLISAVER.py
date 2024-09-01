import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
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
import cv2
import numpy as np

class SimpleUpscaler:
    def __init__(self, scale=2):
        self.scale = scale

    def upscale(self, img):
        print("Upscaling using OpenCV INTER_LANCZOS4...")
        img_np = np.array(img)
        height, width = img_np.shape[:2]

        # Upscale the image using INTER_LANCZOS4
        upscaled_img_np = cv2.resize(img_np, (width * self.scale, height * self.scale), interpolation=cv2.INTER_LANCZOS4)

        # Convert back to PIL Image
        upscaled_img = Image.fromarray(upscaled_img_np)

        return upscaled_img

class PollinationsViewer:
    def __init__(self, master):
        self.master = master
        master.title("POLLISAVER")
        master.geometry("800x580")
        master.resizable(False, False)

        self.always_on_top = tk.BooleanVar()
        self.enhance = tk.BooleanVar()
        self.enhance.trace_add('write', self.save_settings)  # Save settings whenever "enhance" changes
        self.interval = 60  # Default to 1 minute
        self.load_settings()

        self.prompt_history = deque(maxlen=20)
        self.setup_ui()
        self.load_history()
        
        self.is_running = False
        self.current_image = None
        self.viewer_thread = None
        self.fullscreen_window = None
        self.max_retries = 5
        self.retry_delay = 5
        self.retrying = False
        self.current_request_id = None

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.wm_attributes("-topmost", self.always_on_top.get())

        self.upscaler = SimpleUpscaler(scale=2)  # Use a simple 2x upscale with OpenCV
        
        # Directory for saving images
        self.image_dir = "POLLISAVER_IMAGES"
        os.makedirs(self.image_dir, exist_ok=True)

    def setup_ui(self):
        menubar = tk.Menu(self.master)
        options_menu = tk.Menu(menubar, tearoff=0)
        options_menu.add_checkbutton(label="Always on Top", onvalue=True, offvalue=False,
                                     variable=self.always_on_top, command=self.toggle_always_on_top)
        options_menu.add_command(label="Set Interval (min)", command=self.set_interval)  # Moved interval setting here
        menubar.add_cascade(label="Options", menu=options_menu)
        self.master.config(menu=menubar)

        self.frame = ttk.Frame(self.master, padding="10")
        self.frame.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.Frame(self.frame)
        input_frame.pack(fill=tk.X)

        prompt_label = ttk.Label(input_frame, text="Prompt:")
        prompt_label.grid(column=0, row=0, sticky=tk.W, padx=(0, 5))
        self.prompt_entry = tk.Text(input_frame, wrap=tk.WORD, height=2)
        self.prompt_entry.grid(column=1, row=0, columnspan=6, sticky=(tk.W, tk.E), padx=(0, 5))

        history_label = ttk.Label(input_frame, text="History:")
        history_label.grid(column=0, row=1, sticky=tk.W, padx=(0, 5))
        self.history_var = tk.StringVar()
        self.history_dropdown = ttk.Combobox(input_frame, textvariable=self.history_var)
        self.history_dropdown.grid(column=1, row=1, columnspan=6, sticky=(tk.W, tk.E), padx=(0, 5))
        self.history_dropdown.bind('<<ComboboxSelected>>', self.on_history_select)

        # Adjusted button layout to bring buttons closer to the prompt and history entries
        button_frame = ttk.Frame(input_frame)
        button_frame.grid(column=0, row=2, columnspan=2, sticky=tk.W, padx=(5, 5))

        self.start_stop_button = ttk.Button(button_frame, text="Start", command=self.toggle_start_stop, width=8)
        self.start_stop_button.grid(column=0, row=0, padx=(5, 5))

        self.fullscreen_button = ttk.Button(button_frame, text="Fullscreen", command=self.toggle_fullscreen, state=tk.DISABLED, width=10)
        self.fullscreen_button.grid(column=1, row=0, padx=(5, 5))

        self.enhance_checkbox = ttk.Checkbutton(button_frame, text="Enhance", variable=self.enhance)
        self.enhance_checkbox.grid(column=2, row=0, padx=(5, 5))

        input_frame.columnconfigure(1, weight=1)

        self.image_frame = ttk.Frame(self.frame, relief="flat", borderwidth=0)
        self.image_frame.pack(expand=True, fill=tk.BOTH)

        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(expand=True)

        # Bind left-click to toggle fullscreen
        self.image_label.bind("<Button-1>", self.toggle_fullscreen)
        self.image_label.bind("<Button-3>", self.show_context_menu)  # Right-click for context menu

        self.context_menu = tk.Menu(self.master, tearoff=0)
        self.context_menu.add_command(label="Copy to Clipboard", command=self.copy_to_clipboard)

    def set_interval(self):
        interval_str = simpledialog.askstring("Set Interval", "Enter interval in minutes:", initialvalue=str(self.interval / 60), parent=self.master)
        try:
            self.interval = max(0.1, float(interval_str)) * 60
            print(f"Interval set to {self.interval} seconds.")
            self.save_settings()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for the interval.")

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
        # Get the entered prompt or use the last prompt from history
        prompt = self.prompt_entry.get("1.0", tk.END).strip()
        if not prompt:  # If no prompt is entered
            if self.prompt_history:
                prompt = self.prompt_history[0]  # Use the most recent prompt from history
                self.prompt_entry.insert(tk.END, prompt)  # Display the last prompt in the entry box
            else:
                messagebox.showerror("Missing Prompt", "Please enter a prompt or ensure there is one in history.")
                return  # Exit if no prompt is available in history

        self.add_to_history(prompt)

        self.is_running = True
        self.start_stop_button.config(text="Stop")
        self.current_request_id = random.randint(1, 1000000)  # Generate a unique request ID
        
        self.viewer_thread = threading.Thread(target=self.run_viewer, args=(prompt, self.interval, self.current_request_id))
        self.viewer_thread.start()

    def stop_viewer(self):
        self.is_running = False
        self.start_stop_button.config(text="Start")
        self.current_request_id = None  # Invalidate current request ID to stop ongoing fetching

    def toggle_fullscreen(self, event=None):
        if not self.current_image:
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

        self.display_fullscreen_image()

        self.fullscreen_window.bind('<Escape>', self.exit_fullscreen)
        self.fullscreen_window.bind("<Button-1>", self.exit_fullscreen)  # Left-click to exit fullscreen
        self.fullscreen_window.bind("<Button-3>", self.show_context_menu)  # Right-click for context menu

    def exit_fullscreen(self, event=None):
        if self.fullscreen_window:
            self.fullscreen_window.destroy()
            self.fullscreen_window = None

    def run_viewer(self, prompt, interval, request_id):
        retry_count = 0
        while self.is_running and request_id == self.current_request_id:
            try:
                self.fetch_and_display_image(prompt, request_id)
                retry_count = 0  # Reset retry count after a successful fetch
            except Exception as e:
                retry_count += 1
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** (retry_count - 1)))  # Exponential backoff
                else:
                    print(f"Failed to fetch image after {retry_count} attempts: {e}")
                    break
            time.sleep(interval)

    def fetch_and_display_image(self, prompt, request_id):
        seed = random.randint(1, 1000000)
        enhance_param = "true" if self.enhance.get() else "false"
        url = f"https://image.pollinations.ai/prompt/{prompt}?nologo=true&nofeed=true&enhance={enhance_param}&seed={seed}&width=1920&height=1080"
        
        for attempt in range(self.max_retries):
            if not self.is_running or request_id != self.current_request_id:
                return
            
            try:
                print(f"Fetching image with URL: {url}")
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    print("Image fetched successfully.")
                    self.original_image = Image.open(io.BytesIO(response.content))
                    
                    # Save the original image
                    original_path = os.path.join(self.image_dir, "original_image.png")
                    self.original_image.save(original_path)
                    print(f"Original image saved to {original_path}")

                    # Process and save the upscaled image
                    self.upscaled_image = self.upscaler.upscale(self.original_image)
                    upscaled_path = os.path.join(self.image_dir, "upscaled_image.png")
                    self.upscaled_image.save(upscaled_path)
                    print(f"Upscaled image saved to {upscaled_path}")

                    self.current_image = self.upscaled_image  # Always use the upscaled image for display
                    self.master.after(0, self.display_image)
                    self.master.after(0, self.display_fullscreen_image)  # Ensure fullscreen updates
                    self.master.after(0, self.fullscreen_button.config, {'state': tk.NORMAL})
                    break
            except requests.exceptions.Timeout as e:
                print(f"Error fetching image (timeout): {e}")
            except Exception as e:
                print(f"Error fetching image: {e}")
                time.sleep(self.retry_delay)  # Wait before retrying

    def display_image(self):
        if self.current_image is None:
            print("No image to display.")
            return

        img_width, img_height = self.current_image.size
        aspect_ratio = img_width / img_height

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
            resized_image = self.current_image.resize((new_width, new_height), Image.LANCZOS)
            photo_image = ImageTk.PhotoImage(resized_image)

            self.image_label.config(image=photo_image)
            self.image_label.image = photo_image
            print("Displayed upscaled image.")
            
            self.master.update_idletasks()  # Force the GUI to update
            
        except Exception as e:
            print(f"Error displaying image: {e}")

    def display_fullscreen_image(self):
        if self.fullscreen_window is None:
            print("No fullscreen window available.")
            return

        if self.current_image is None:
            print("No image to display in fullscreen.")
            return

        screen_width = self.fullscreen_window.winfo_screenwidth()
        screen_height = self.fullscreen_window.winfo_screenheight()

        try:
            scale = min(screen_width / self.current_image.width, screen_height / self.current_image.height)
            new_width = int(self.current_image.width * scale)
            new_height = int(self.current_image.height * scale)
            resized_image = self.current_image.resize((new_width, new_height), Image.LANCZOS)
            
            fullscreen_image = ImageTk.PhotoImage(resized_image)

            self.fullscreen_image_label.config(image=fullscreen_image)
            self.fullscreen_image_label.image = fullscreen_image

            print("Displayed upscaled image in fullscreen.")
            
            self.fullscreen_window.update_idletasks()  # Force the fullscreen window to update

        except Exception as e:
            print(f"Error displaying fullscreen image: {e}")

    def show_context_menu(self, event):
        try:
            self.context_menu.post(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def copy_to_clipboard(self):
        if self.upscaled_image is None:
            messagebox.showerror("No Image", "There is no image to copy.")
            return

        output = io.BytesIO()
        # Always copy the upscaled image to the clipboard
        self.upscaled_image.convert("RGB").save(output, format="BMP")
        data = output.getvalue()[14:]  # Skip the BMP header
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        win32clipboard.CloseClipboard()
        print("Upscaled image copied to clipboard.")

    def toggle_always_on_top(self):
        self.master.wm_attributes("-topmost", self.always_on_top.get())
        self.save_settings()

    def save_settings(self, *args):  # Accept additional arguments and ignore them
        settings = {
            "always_on_top": self.always_on_top.get(),
            "enhance": self.enhance.get(),  # Save the state of the "Enhance" checkbox
            "interval": self.interval  # Save the interval setting
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)

    def load_settings(self):
        if os.path.exists('settings.json'):
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                self.always_on_top.set(settings.get("always_on_top", False))
                self.enhance.set(settings.get("enhance", False))  # Load the state of the "Enhance" checkbox
                self.interval = settings.get("interval", 60)  # Load the interval setting (default to 1 minute)

    def on_closing(self):
        self.stop_viewer()  # Ensure the viewer thread stops
        if self.viewer_thread and self.viewer_thread.is_alive():
            self.viewer_thread.join(timeout=5)  # Wait for the thread to finish
        self.master.destroy()  # Close the GUI window

if __name__ == "__main__":
    root = tk.Tk()
    app = PollinationsViewer(root)
    root.mainloop()
