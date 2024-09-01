# POLLISAVER

**POLLISAVER** is a Python-based image viewer application that retrieves, upscales, and displays images based on prompts using the Pollinations AI service.

![POLLISAVER_v1](https://github.com/user-attachments/assets/5b9c77a0-3923-4a84-95ad-092d7625a722)

## Features:
- Prompt-Based Image Retrieval: Fetches images from Pollinations AI based on the user's input prompt.
- Automatic Interval-Based Image Updates: Regularly updates the displayed image at user-defined intervals.
- Fullscreen Display Option: View images in fullscreen mode for an immersive experience.
- Always on Top: Keep the POLLISAVER window above all other windows with the "Always on Top" option.
- Enhanced Image Generation: Optionally enhance images with the "Enhance" checkbox for better quality.
- Upscaling: Images are automatically upscaled for improved quality using OpenCV's `INTER_LANCZOS4` method.
- Image Saving: Both the original and upscaled versions of images are saved locally in the `POLLISAVER_IMAGES` directory.
- Right-Click Context Menu: Easily copy the upscaled image to the clipboard with a right-click.

## Requirements:
- Python 3.x
- `requests`, `Pillow`, `opencv-python`, `pywin32`, `numpy`

## How to Use:
1. Enter a prompt in the "Prompt" field to guide the image retrieval.
2. Set the interval time in minutes for automatic updates.
3. Optionally, select "Enhance" to improve image quality through upscaling.
4. Click "Start" to begin fetching images.
5. Use the "Fullscreen" button or left-click on the image to view it in fullscreen mode. Press `Esc` to exit fullscreen.
6. Right-click on the image to copy the upscaled version to the clipboard.

## License
This project is licensed under the MIT License.
