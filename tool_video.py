import os
import sys
import random
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, CompositeVideoClip, TextClip, vfx

# ==== CONFIG ====
OUTPUT_FOLDER = "output"
VIDEO_CODEC = "libx265"
AUDIO_CODEC = "aac"
FPS = 60

if getattr(sys, 'frozen', False):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(sys._MEIPASS, "ffmpeg.exe")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def save_segments(input_path, output_path):
    clip = VideoFileClip(input_path)
    segment_start = 0
    ep_index = 1

    while segment_start < clip.duration:
        segment_end = segment_start + random.uniform(61, 75)
        segment_end = min(segment_end, clip.duration)
        subclip = clip.subclip(segment_start, segment_end)

        text = TextClip(f"Ep{ep_index}", fontsize=30, color='white')
        text = text.set_position((10, 10)).set_duration(subclip.duration)
        subclip = CompositeVideoClip([subclip, text])

        temp_output = os.path.join(output_path, f"segment_{ep_index}.mp4")
        subclip.write_videofile(temp_output, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k")
        segment_start = segment_end
        ep_index += 1

def run_processing():
    filepaths = filedialog.askopenfilenames(title="Chọn video để chia nhỏ", filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv")])
    if not filepaths:
        messagebox.showinfo("Thông báo", "Bạn chưa chọn video nào!")
        return

    for i, in_path in enumerate(filepaths):
        run_id = len(os.listdir(OUTPUT_FOLDER)) + 1
        output_dir = os.path.join(OUTPUT_FOLDER, f"run_{run_id}")
        os.makedirs(output_dir, exist_ok=True)

        def process():
            status_var.set(f"Đang chia: {os.path.basename(in_path)}")
            save_segments(in_path, output_dir)
            status_var.set("Sẵn sàng.")

        threading.Thread(target=process, daemon=True).start()

# ==== GUI ====
root = tk.Tk()
root.title("Tool chia video đoạn nhỏ")
root.geometry("400x200")
root.resizable(False, False)

status_var = tk.StringVar()
status_var.set("Sẵn sàng.")

label = tk.Label(root, text="Tool chia video từ 61s đến 75s", font=("Arial", 12))
label.pack(pady=10)

button = tk.Button(root, text="Chọn & Bắt đầu chia", font=("Arial", 12), command=run_processing)
button.pack(pady=10)

status = tk.Label(root, textvariable=status_var, font=("Arial", 10))
status.pack(pady=5)

root.mainloop()
