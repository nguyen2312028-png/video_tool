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
INPUT_FOLDER = "input_videos"
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

if getattr(sys, 'frozen', False):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(sys._MEIPASS, "ffmpeg.exe")

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

status_var = None
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
    cv2.line(frame, (0, y_center), (frame.shape[1], y_center), (255, 255, 255), 1)
    return frame

def add_watermark(frame):
    h, w, _ = frame.shape
    text_size = cv2.getTextSize(WATERMARK_TEXT, WATERMARK_FONT, WATERMARK_SCALE, WATERMARK_THICKNESS)[0]
    positions = [
        (10, text_size[1] + 10),
        (w - text_size[0] - 10, text_size[1] + 10),
        (10, h - 10),
        (w - text_size[0] - 10, h - 10)
    ]
    pos = random.choice(positions)
    overlay = frame.copy()
    cv2.putText(overlay, WATERMARK_TEXT, pos, WATERMARK_FONT, WATERMARK_SCALE, WATERMARK_COLOR, WATERMARK_THICKNESS)
    return cv2.addWeighted(overlay, WATERMARK_ALPHA, frame, 1 - WATERMARK_ALPHA, 0)

def add_echo_and_pitch(audio_path):
    sound = AudioSegment.from_file(audio_path)
    echo = sound - 6
    sound = sound.overlay(echo, position=80)
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * random.uniform(0.97, 1.03))
    }).set_frame_rate(sound.frame_rate)
    temp_path = tempfile.mktemp(suffix=".wav")
    sound.export(temp_path, format="wav")
    return temp_path

def split_and_process(final_clip, base_output_path):
    duration = final_clip.duration
    t = 0
    part = 1
    while t < duration:
        part_len = random.uniform(60, 75)
        end = min(t + part_len, duration)
        subclip = final_clip.subclip(t, end)
        ep_txt = TextClip(f"Ep{part}", fontsize=40, color='white')
        ep_txt = ep_txt.set_duration(subclip.duration).set_position(('right', 'bottom'))
        final_part = CompositeVideoClip([subclip, ep_txt.set_opacity(0.5)])
        out_path = f"{base_output_path}_Ep{part}.mp4"
        final_part.write_videofile(out_path, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC)
        t = end
        part += 1

def process_video(input_path, output_path_base):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h

    if aspect >= 1.3:
        scaled_clip = clip.resize(width=w * 1.15, height=h * 1.40)
        crop_width = h * 0.5625
        x_center = scaled_clip.w / 2
        cropped = scaled_clip.crop(width=crop_width, height=scaled_clip.h, x_center=x_center, y_center=scaled_clip.h / 2)
    else:
        cropped = clip.crop(width=w * 0.97, height=h * 0.97, x_center=w / 2, y_center=h / 2)

    main_clip = cropped.resize(height=FINAL_RES[1])
    bg_clip = create_blurred_bg(cropped)

    overlay_clips = []
    for file in OVERLAY_FILES:
        ov_path = os.path.join(OVERLAY_FOLDER, file)
        if os.path.exists(ov_path):
            ov = VideoFileClip(ov_path).resize(FINAL_RES).set_opacity(OVERLAY_OPACITY)
            if ov.duration < clip.duration:
                repeat = int(clip.duration / ov.duration) + 1
                ov = CompositeVideoClip([ov] * repeat).set_duration(clip.duration)
            else:
                ov = ov.subclip(0, clip.duration)
            overlay_clips.append(ov)

    main_clip = main_clip.fl_image(apply_hdr_and_color)
    main_clip = main_clip.fl_image(add_white_line)
    main_clip = main_clip.fl_image(add_watermark)

    final = CompositeVideoClip([
        bg_clip.resize(FINAL_RES),
        main_clip.set_position("center")
    ] + overlay_clips, size=FINAL_RES)

    speed = random.uniform(0.90, 1.10)
    final = final.fx(vfx.speedx, speed)

    if final.audio:
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        final.audio.write_audiofile(temp_audio_path, fps=44100)
        processed_audio_path = add_echo_and_pitch(temp_audio_path)
        audio_clip = AudioFileClip(processed_audio_path).set_duration(final.duration)
        final = final.set_audio(audio_clip)

    split_and_process(final, output_path_base)

def choose_video():
    global video_path
    file = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4;*.mov;*.avi;*.mkv")])
    if file:
        video_path = file
        status_var.set(f"Đã chọn: {os.path.basename(file)}")

def run_processing():
    try:
        if not video_path:
            messagebox.showinfo("Thông báo", "Vui lòng chọn video trước!")
            return

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        out_base = os.path.join(OUTPUT_FOLDER, base_name)
        process_video(video_path, out_base)

        messagebox.showinfo("Hoàn thành", f"✅ Đã xử lý video thành công!")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

def start_thread():
    threading.Thread(target=run_processing, daemon=True).start()

# ==== GIAO DIỆN GUI ====
root = tk.Tk()
root.title("Video Tool - NguenChang")
root.geometry("400x200")
root.resizable(False, False)

status_var = tk.StringVar()
status_var.set("Sẵn sàng.")

label = tk.Label(root, text="Tool xử lý video dạng Reels/TikTok", font=("Arial", 12))
label.pack(pady=10)

choose_btn = tk.Button(root, text="Chọn video", font=("Arial", 12), command=choose_video)
choose_btn.pack(pady=5)

start_btn = tk.Button(root, text="Bắt đầu xử lý", font=("Arial", 12), command=start_thread)
start_btn.pack(pady=5)

status = tk.Label(root, textvariable=status_var, font=("Arial", 10))
status.pack(pady=5)

root.mainloop()
