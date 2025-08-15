# VIDEO TOOL - NguenChang (Gộp xử lý audio + video đồng thời, Fix 16:9)

import os
import sys
import cv2
import numpy as np
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, TextClip, AudioFileClip
from pydub import AudioSegment
import tempfile

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
VIDEO_CODEC = "libx265"
AUDIO_CODEC = "aac"
FPS = 60
EPSILON = 0.05

if getattr(sys, 'frozen', False):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(sys._MEIPASS, "ffmpeg.exe")

for folder in [OVERLAY_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# ==== VIDEO EFFECTS ====
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
    cv2.line(frame, (0, y_center), (frame.shape[1], y_center), (255, 255, 255), 3)
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

# ==== AUDIO EFFECTS ====
def pydub_effects_on_audio(audio_clip):
    temp_wav = tempfile.mktemp(suffix=".wav")
    audio_clip.write_audiofile(temp_wav, fps=44100, verbose=False, logger=None)
    sound = AudioSegment.from_file(temp_wav).set_channels(2)
    echo = sound - 6
    sound = sound.overlay(echo, position=80)
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * random.uniform(0.97, 1.03))
    }).set_frame_rate(sound.frame_rate)
    processed_wav = tempfile.mktemp(suffix=".wav")
    sound.export(processed_wav, format="wav")
    return AudioFileClip(processed_wav)

# ==== CUT ====
def save_segments(final_clip, output_path):
    segment_start = 0
    ep_index = 1
    while segment_start < final_clip.duration - EPSILON:
        segment_end = min(segment_start + random.uniform(60, 75), final_clip.duration - EPSILON)
        subclip = final_clip.subclip(segment_start, segment_end)
        text = TextClip(f"Ep{ep_index}", fontsize=30, color='white')
        text = text.set_position((10, 10)).set_duration(subclip.duration)
        subclip = CompositeVideoClip([subclip, text])
        out_path = os.path.join(output_path, f"segment_{ep_index}.mp4")
        subclip.write_videofile(out_path, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k", verbose=False, logger=None)
        segment_start = segment_end
        ep_index += 1

# ==== MAIN ====
def process_video(input_path, output_path):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h

    if aspect >= 1.3:
        # Resize chỉ chiều ngang về 720
        main_clip = clip.resize(width=FINAL_RES[0])
        main_clip = main_clip.set_position("center")
        bg_clip = create_blurred_bg(main_clip)
    else:
        crop_w = w * 0.97
        crop_h = h * 0.97
        scaled_clip = clip.crop(width=crop_w, height=crop_h, x_center=w/2, y_center=h/2)
        main_clip = scaled_clip.resize(height=FINAL_RES[1])
        bg_clip = create_blurred_bg(main_clip)

    overlay_clips = []
    for file in OVERLAY_FILES:
        ov_path = os.path.join(OVERLAY_FOLDER, file)
        if os.path.exists(ov_path):
            ov = VideoFileClip(ov_path).resize(FINAL_RES).set_opacity(OVERLAY_OPACITY)
            if ov.duration < clip.duration:
                repeat = int(clip.duration / ov.duration) + 1
                ov = CompositeVideoClip([ov] * repeat).set_duration(clip.duration)
            else:
                ov = ov.subclip(0, clip.duration - EPSILON)
            overlay_clips.append(ov)

    main_clip = main_clip.fl_image(apply_hdr_and_color)
    main_clip = main_clip.fl_image(add_white_line)
    main_clip = main_clip.fl_image(add_watermark)

    final = CompositeVideoClip([bg_clip.resize(FINAL_RES), main_clip] + overlay_clips, size=FINAL_RES)
    final = final.fx(vfx.speedx, random.uniform(0.90, 1.10))

    if final.audio:
        final = final.set_audio(pydub_effects_on_audio(final.audio))

    temp_out = tempfile.mktemp(suffix=".mp4")
    final.write_videofile(temp_out, fps=FPS, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k")

    metadata_flags = (
        f'-metadata title="Processed by NguenChang" '
        f'-metadata author="NguenChang" '
        f'-metadata comment="Edited on iPhone 12 Pro Max using CapCut" '
        f'-metadata location="USA" '
    )
    final_out_path = os.path.join(output_path, "final_output.mp4")
    os.system(f'ffmpeg -i "{temp_out}" -map_metadata -1 {metadata_flags} -c:v copy -c:a copy "{final_out_path}" -y')
    save_segments(VideoFileClip(final_out_path), output_path)

# ==== GUI ====
def run_processing():
    filepaths = filedialog.askopenfilenames(title="Chọn video để xử lý", filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv")])
    if not filepaths:
        messagebox.showinfo("Thông báo", "Bạn chưa chọn video nào!")
        return

    for in_path in filepaths:
        run_id = len(os.listdir(OUTPUT_FOLDER)) + 1
        output_dir = os.path.join(OUTPUT_FOLDER, f"run_{run_id}")
        os.makedirs(output_dir, exist_ok=True)

        def process():
            status_var.set(f"Đang xử lý: {os.path.basename(in_path)}")
            process_video(in_path, output_dir)
            status_var.set("Sẵn sàng.")

        threading.Thread(target=process, daemon=True).start()

root = tk.Tk()
root.title("Video Tool - NguenChang (Gộp Audio+Video)")
root.geometry("400x200")
root.resizable(False, False)

status_var = tk.StringVar(value="Sẵn sàng.")

tk.Label(root, text="Tool xử lý video Reels/TikTok", font=("Arial", 12)).pack(pady=10)
tk.Button(root, text="Chọn & Bắt đầu xử lý", font=("Arial", 12), command=run_processing).pack(pady=10)
tk.Label(root, textvariable=status_var, font=("Arial", 10)).pack(pady=5)

root.mainloop()
