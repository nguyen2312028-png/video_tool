import os
import cv2
import numpy as np
import random
import tempfile
import threading
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, AudioFileClip
from pydub import AudioSegment
from tkinter import messagebox, filedialog
import tkinter as tk

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

if not os.path.exists(INPUT_FOLDER):
    os.makedirs(INPUT_FOLDER)

if not os.path.exists(OVERLAY_FOLDER):
    os.makedirs(OVERLAY_FOLDER)

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

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
    cv2.line(frame, (0, y_center), (frame.shape[1], y_center), (255, 255, 255), LINE_THICKNESS)
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

# ==== PART 1 - Edit Video ====
def edit_video(input_path):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h

    # Xử lý video gốc dạng 16:9 và 9:16
    if aspect >= 1.3:
        clip = clip.resize(width=w * ZOOM_X, height=h * ZOOM_Y)
        crop_width = h * 0.5625
        x_center = clip.w / 2
        clip = clip.crop(width=crop_width, height=clip.h, x_center=x_center, y_center=clip.h / 2)
    else:
        clip = clip.crop(width=w * 0.95, height=h * 0.95, x_center=w / 2, y_center=h / 2)

    # Thêm nền mờ
    bg_clip = create_blurred_bg(clip)

    # Thêm watermark, đường chỉ trắng
    clip = clip.fl_image(add_white_line)
    clip = clip.fl_image(add_watermark)

    # Thêm overlay
    overlay_clips = []
    for file in OVERLAY_FILES:
        ov_path = os.path.join(OVERLAY_FOLDER, file)
        if os.path.exists(ov_path):
            ov = VideoFileClip(ov_path).resize((720, 1280)).set_opacity(OVERLAY_OPACITY)
            overlay_clips.append(ov)

    # Áp dụng HDR và thay đổi màu sắc
    clip = clip.fl_image(apply_hdr_and_color)

    # Lưu video đã chỉnh sửa
    output_path = os.path.join(OUTPUT_FOLDER, "edited_video.mp4")
    final_clip = CompositeVideoClip([bg_clip, clip.set_position("center")] + overlay_clips)
    final_clip.write_videofile(output_path, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC)
    return output_path

# ==== PART 2 - Cắt Video Thành Các Phần Nhỏ ====
def split_video(input_path):
    clip = VideoFileClip(input_path)
    video_duration = clip.duration
    part_duration = random.randint(60, 75)  # Video part duration between 1m to 1m15s

    num_parts = int(video_duration / part_duration)
    parts = []
    for i in range(num_parts):
        start_time = i * part_duration
        end_time = (i + 1) * part_duration if (i + 1) * part_duration <= video_duration else video_duration

        part = clip.subclip(start_time, end_time)

        # Thêm chữ EpX vào video
        txt_clip = (TextClip(f"Ep{i+1}", fontsize=50, color='white')
                    .set_position(('center', 'top'))
                    .set_duration(part.duration))
        part = CompositeVideoClip([part, txt_clip])

        parts.append(part)

    return parts

def process_and_split_video(input_path):
    edited_video_path = edit_video(input_path)
    parts = split_video(edited_video_path)

    # Lưu từng phần video
    part_paths = []
    for i, part in enumerate(parts):
        part_path = os.path.join(OUTPUT_FOLDER, f"part_{i+1}.mp4")
        part.write_videofile(part_path, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC)
        part_paths.append(part_path)

    return part_paths

# ==== GUI ====
def run_processing():
    try:
        videos = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))]
        if not videos:
            messagebox.showinfo("Thông báo", "Không tìm thấy video trong thư mục input_videos")
            return

        for vid in videos:
            in_path = os.path.join(INPUT_FOLDER, vid)
            status_var.set(f"Đang xử lý: {vid}")
            part_paths = process_and_split_video(in_path)

        messagebox.showinfo("Hoàn thành", f"✅ Xử lý xong! Video nằm ở: {OUTPUT_FOLDER}")
    except Exception as e:
        messagebox.showerror("Lỗi", str(e))

def start_thread():
    threading.Thread(target=run_processing).start()

# ==== GIAO DIỆN GUI ====
root = tk.Tk()
root.title("Video Tool - NguenChang")
root.geometry("400x200")
root.resizable(False, False)

status_var = tk.StringVar()
status_var.set("Sẵn sàng.")

label = tk.Label(root, text="Tool xử lý video dạng Reels/TikTok", font=("Arial", 12))
label.pack(pady=10)

button = tk.Button(root, text="Bắt đầu xử lý", font=("Arial", 12), command=start_thread)
button.pack(pady=10)

status = tk.Label(root, textvariable=status_var, font=("Arial", 10))
status.pack(pady=5)

root.mainloop()
