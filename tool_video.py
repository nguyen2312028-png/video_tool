# full_tool.py
import os
import sys
import cv2
import numpy as np
import random
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, AudioFileClip, TextClip
from pydub import AudioSegment

# ==== CONFIG ====
OVERLAY_FOLDER = "overlays"
OUTPUT_FOLDER = "output"
OVERLAY_FILES = ["line_sang.mp4", "line_trang.mp4"]
ZOOM_X, ZOOM_Y = 1.15, 1.40
OVERLAY_OPACITY = 0.05
FINAL_RES = (720, 1280)
WATERMARK_TEXT = "NguenChang"
WATERMARK_FONT = cv2.FONT_HERSHEY_SIMPLEX
WATERMARK_SCALE = 0.6
WATERMARK_COLOR = (255, 255, 255)
WATERMARK_THICKNESS = 1
WATERMARK_ALPHA = 0.3
LINE_THICKNESS = 2
VIDEO_CODEC = "libx265"
AUDIO_CODEC = "aac"
FPS = 60
EP_MIN = 60
EP_MAX = 75

if getattr(sys, 'frozen', False):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(sys._MEIPASS, "ffmpeg.exe")

os.makedirs(OVERLAY_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
run_id = len(os.listdir(OUTPUT_FOLDER)) + 1
current_output_path = os.path.join(OUTPUT_FOLDER, str(run_id))
os.makedirs(current_output_path, exist_ok=True)

# ==== FUNCTIONS ====
def apply_hdr_and_color(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.equalizeHist(l)
    lab = cv2.merge((l, a, b))
    frame = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    gamma = random.uniform(0.95, 1.05)
    contrast = random.uniform(0.95, 1.05)
    frame = np.clip(((frame / 255.0) ** gamma) * contrast * 255, 0, 255).astype(np.uint8)
    return frame

def create_blurred_bg(clip):
    return clip.resize(width=clip.w * ZOOM_X, height=clip.h * ZOOM_Y).fl_image(
        lambda img: cv2.GaussianBlur(img, (25, 25), 0))

def add_white_line(frame):
    y = frame.shape[0] // 2
    cv2.line(frame, (0, y), (frame.shape[1], y), (255, 255, 255), 1)
    return frame

def add_watermark(frame):
    h, w, _ = frame.shape
    sz = cv2.getTextSize(WATERMARK_TEXT, WATERMARK_FONT, WATERMARK_SCALE, WATERMARK_THICKNESS)[0]
    pos = random.choice([(10, sz[1]+10), (w-sz[0]-10, sz[1]+10), (10, h-10), (w-sz[0]-10, h-10)])
    overlay = frame.copy()
    cv2.putText(overlay, WATERMARK_TEXT, pos, WATERMARK_FONT, WATERMARK_SCALE, WATERMARK_COLOR, WATERMARK_THICKNESS)
    return cv2.addWeighted(overlay, WATERMARK_ALPHA, frame, 1 - WATERMARK_ALPHA, 0)

def add_echo_and_pitch(audio_path):
    sound = AudioSegment.from_file(audio_path)
    echo = sound - 6
    sound = sound.overlay(echo, position=80)
    sound = sound._spawn(sound.raw_data, overrides={"frame_rate": int(sound.frame_rate * random.uniform(0.97, 1.03))})
    sound = sound.set_frame_rate(sound.frame_rate)
    temp_path = tempfile.mktemp(suffix=".wav")
    sound.export(temp_path, format="wav")
    return temp_path

def split_and_export_video(video: CompositeVideoClip, base_name: str):
    duration = video.duration
    t = 0
    idx = 1
    while t < duration:
        end = min(t + random.uniform(EP_MIN, EP_MAX), duration)
        sub = video.subclip(t, end)
        ep_text = TextClip(f"Ep{idx}", fontsize=30, color='white').set_position((10, 10)).set_duration(sub.duration)
        final = CompositeVideoClip([sub, ep_text])
        final_path = os.path.join(current_output_path, f"{base_name}_Ep{idx}.mp4")
        final.write_videofile(final_path, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k")
        idx += 1
        t = end

def process_video(input_path):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h
    name = os.path.splitext(os.path.basename(input_path))[0]

    if aspect >= 1.3:
        scaled = clip.resize(width=w * 1.15, height=h * 1.40)
        crop_width = h * (9/16)
        cropped = scaled.crop(width=crop_width, height=scaled.h, x_center=scaled.w/2, y_center=scaled.h/2)
    else:
        cropped = clip.crop(width=w * 0.97, height=h * 0.97, x_center=w/2, y_center=h/2)

    main = cropped.resize(height=FINAL_RES[1])
    bg = create_blurred_bg(cropped)

    overlays = []
    for f in OVERLAY_FILES:
        p = os.path.join(OVERLAY_FOLDER, f)
        if os.path.exists(p):
            ov = VideoFileClip(p).resize(FINAL_RES).set_opacity(OVERLAY_OPACITY)
            if ov.duration < clip.duration:
                rep = int(clip.duration / ov.duration) + 1
                ov = CompositeVideoClip([ov] * rep).set_duration(clip.duration)
            else:
                ov = ov.subclip(0, clip.duration)
            overlays.append(ov)

    main = main.fl_image(apply_hdr_and_color)
    main = main.fl_image(add_white_line)
    main = main.fl_image(add_watermark)

    final = CompositeVideoClip([bg.resize(FINAL_RES), main.set_position("center")] + overlays, size=FINAL_RES)
    final = final.fx(vfx.speedx, random.uniform(0.90, 1.10))

    if final.audio:
        temp_audio = tempfile.mktemp(suffix=".wav")
        final.audio.write_audiofile(temp_audio)
        processed_audio = add_echo_and_pitch(temp_audio)
        final = final.set_audio(AudioFileClip(processed_audio).set_duration(final.duration))

    split_and_export_video(final, name)

# ==== GUI ====
def run_processing():
    try:
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv")])
        if not path:
            return
        status_var.set("Đang xử lý...")
        process_video(path)
        messagebox.showinfo("Xong", f"✅ Video đã xử lý nằm trong: {current_output_path}")
        status_var.set("Hoàn tất!")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))
        status_var.set("Lỗi rồi!")

def start_thread():
    threading.Thread(target=run_processing, daemon=True).start()

root = tk.Tk()
root.title("Video Tool - NguenChang")
root.geometry("400x200")
status_var = tk.StringVar(value="Sẵn sàng")

label = tk.Label(root, text="Tool edit + chia đoạn video Reels/TikTok", font=("Arial", 12))
label.pack(pady=10)

btn = tk.Button(root, text="Chọn và xử lý video", font=("Arial", 12), command=start_thread)
btn.pack(pady=10)

status = tk.Label(root, textvariable=status_var)
status.pack(pady=5)

root.mainloop()
