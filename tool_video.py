import os
import sys
import cv2
import threading
import numpy as np
import tempfile
import random
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, AudioFileClip
from pydub import AudioSegment

# === CONFIG ===
OVERLAY_FOLDER = "overlays"
OUTPUT_FOLDER = "output"
FINAL_RES = (720, 1280)
OVERLAY_OPACITY = 0.05
ZOOM_X, ZOOM_Y = 1.15, 1.40
FPS = 60
VIDEO_CODEC = "libx265"
AUDIO_CODEC = "aac"

video_path = None

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
        lambda img: cv2.GaussianBlur(img, (25, 25), 0)
    )

def add_white_line(frame):
    y_center = frame.shape[0] // 2
    cv2.line(frame, (0, y_center), (frame.shape[1], y_center), (255, 255, 255), 2)
    return frame

def process_video(input_path, output_path):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h

    if aspect >= 1.3:
        scaled = clip.resize(width=w * ZOOM_X, height=h * ZOOM_Y)
        main_clip = scaled
    else:
        main_clip = clip.crop(width=w * 0.97, height=h * 0.97, x_center=w/2, y_center=h/2)

    main_clip = main_clip.resize(height=FINAL_RES[1])
    bg_clip = create_blurred_bg(main_clip)

    overlay_clips = []
    for file in os.listdir(OVERLAY_FOLDER):
        if file.endswith(".mp4"):
            ov_path = os.path.join(OVERLAY_FOLDER, file)
            ov = VideoFileClip(ov_path).resize(FINAL_RES).set_opacity(OVERLAY_OPACITY)
            if ov.duration < clip.duration:
                repeat = int(clip.duration / ov.duration) + 1
                ov = CompositeVideoClip([ov] * repeat).set_duration(clip.duration)
            else:
                ov = ov.subclip(0, clip.duration)
            overlay_clips.append(ov)

    main_clip = main_clip.fl_image(apply_hdr_and_color)
    main_clip = main_clip.fl_image(add_white_line)

    final = CompositeVideoClip(
        [bg_clip.resize(FINAL_RES), main_clip.set_position("center")] + overlay_clips,
        size=FINAL_RES
    )

    final = final.fx(vfx.speedx, random.uniform(0.90, 1.10))

    if final.audio:
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        final.audio.write_audiofile(temp_audio_path, fps=44100)
        sound = AudioSegment.from_file(temp_audio_path)
        sound = sound.overlay(sound - 6, position=80)
        sound = sound._spawn(sound.raw_data, overrides={
            "frame_rate": int(sound.frame_rate * random.uniform(0.97, 1.03))
        }).set_frame_rate(sound.frame_rate)
        processed_audio_path = tempfile.mktemp(suffix=".wav")
        sound.export(processed_audio_path, format="wav")
        final = final.set_audio(AudioFileClip(processed_audio_path).set_duration(final.duration))

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    out_path = os.path.join(OUTPUT_FOLDER, os.path.basename(input_path))
    final.write_videofile(out_path, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k")

# ==== GUI ====
def select_video():
    global video_path
    file = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv")])
    if file:
        video_path = file
        status_var.set(f"Đã chọn: {os.path.basename(file)}")

def start_processing():
    if not video_path:
        messagebox.showwarning("Chưa chọn video", "Vui lòng chọn video trước.")
        return

    status_var.set("Đang xử lý...")
    threading.Thread(target=process_and_notify, daemon=True).start()

def process_and_notify():
    try:
        process_video(video_path, OUTPUT_FOLDER)
        status_var.set("✅ Xử lý xong! Xem thư mục output.")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))
        status_var.set("❌ Lỗi xảy ra.")

# ==== TKINTER ====
root = tk.Tk()
root.title("Video Tool - NguenChang")
root.geometry("420x200")
root.resizable(False, False)

status_var = tk.StringVar()
status_var.set("Sẵn sàng.")

tk.Label(root, text="Tool xử lý video dạng Reels/TikTok", font=("Arial", 12)).pack(pady=10)
tk.Button(root, text="Chọn video", font=("Arial", 12), command=select_video).pack(pady=5)
tk.Button(root, text="Bắt đầu xử lý", font=("Arial", 12), command=start_processing).pack(pady=5)
tk.Label(root, textvariable=status_var, font=("Arial", 10)).pack(pady=5)

root.mainloop()
