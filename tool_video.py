import os
import sys
import cv2
import numpy as np
import random
import tempfile
from moviepy.editor import VideoFileClip, CompositeVideoClip, vfx, AudioFileClip
from pydub import AudioSegment

# ==== CONFIG ====
INPUT_FOLDER = "input_videos"
OVERLAY_FOLDER = "overlays"
OUTPUT_FOLDER = "output"
OVERLAY_FILES = ["line_sang.mp4", "line_trang.mp4"]

ZOOM_X, ZOOM_Y = 1.15, 1.40  # Tỷ lệ scale nền với video gốc ngang
CROP_PERCENT = 0.05
OVERLAY_OPACITY = 0.05
FINAL_RES = (720, 1280)  # Tỉ lệ 9:16

WATERMARK_TEXT = "NguenChang"
WATERMARK_FONT = cv2.FONT_HERSHEY_SIMPLEX
WATERMARK_SCALE = 0.6
WATERMARK_COLOR = (255, 255, 255)
WATERMARK_THICKNESS = 1
WATERMARK_ALPHA = 0.3

LINE_THICKNESS = 2
VIDEO_CODEC = "libx265"
AUDIO_CODEC = "aac"

if getattr(sys, 'frozen', False):
    os.environ["IMAGEIO_FFMPEG_EXE"] = os.path.join(sys._MEIPASS, "ffmpeg.exe")

for folder in [INPUT_FOLDER, OVERLAY_FOLDER, OUTPUT_FOLDER]:
    os.makedirs(folder, exist_ok=True)

run_id = len(os.listdir(OUTPUT_FOLDER)) + 1
current_output_path = os.path.join(OUTPUT_FOLDER, str(run_id))
os.makedirs(current_output_path, exist_ok=True)

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
        lambda img: cv2.GaussianBlur(img, (51, 51), 0)
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
    sound = sound.overlay(sound - 6, position=80)
    sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * random.uniform(0.98, 1.02))
    }).set_frame_rate(sound.frame_rate)
    temp_path = tempfile.mktemp(suffix=".wav")
    sound.export(temp_path, format="wav")
    return temp_path

def loop_or_trim_overlay(clip, duration):
    if clip.duration > duration:
        return clip.subclip(0, duration)
    elif clip.duration < duration:
        loops = int(duration // clip.duration) + 1
        return concatenate_videoclips([clip] * loops).subclip(0, duration)
    return clip

def process_video(input_path, output_path):
    clip = VideoFileClip(input_path)
    w, h = clip.size
    aspect = w / h

    if aspect >= 1.3:  # Landscape → scale nhỏ lại cho vừa khung 9:16
        scaled = clip.resize(width=clip.w * ZOOM_X, height=clip.h * ZOOM_Y)
        main_clip = clip.resize(height=FINAL_RES[1])
        bg_clip = create_blurred_bg(scaled)
    else:  # Portrait → crop nhẹ và làm nền
        cropped = clip.crop(width=w * (1 - CROP_PERCENT), height=h * (1 - CROP_PERCENT), x_center=w/2, y_center=h/2)
        main_clip = cropped.resize(height=FINAL_RES[1])
        bg_clip = create_blurred_bg(cropped)

    overlay_clips = []
    for file in OVERLAY_FILES:
        ov_path = os.path.join(OVERLAY_FOLDER, file)
        if os.path.exists(ov_path):
            ov = VideoFileClip(ov_path).resize(FINAL_RES).set_opacity(OVERLAY_OPACITY)
            ov = loop_or_trim_overlay(ov, clip.duration)
            overlay_clips.append(ov)

    main_clip = main_clip.fl_image(apply_hdr_and_color)
    main_clip = main_clip.fl_image(add_white_line)
    main_clip = main_clip.fl_image(add_watermark)

    final = CompositeVideoClip([bg_clip.resize(FINAL_RES), main_clip.set_position("center")] + overlay_clips, size=FINAL_RES)

    speed_factor = random.uniform(0.95, 1.12)
    final = final.fx(vfx.speedx, speed_factor)

    if final.audio:
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        final.audio.write_audiofile(temp_audio_path, fps=44100)
        processed_audio_path = add_echo_and_pitch(temp_audio_path)
        final = final.set_audio(AudioFileClip(processed_audio_path).set_duration(final.duration))

    final.write_videofile(output_path, fps=60, codec=VIDEO_CODEC, audio_codec=AUDIO_CODEC, bitrate="8000k")

videos = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))]
for i, vid in enumerate(videos, start=1):
    in_path = os.path.join(INPUT_FOLDER, vid)
    out_path = os.path.join(current_output_path, f"video_{i}.mp4")
    print(f"🔹 Processing: {vid} -> {out_path}")
    process_video(in_path, out_path)

print(f"\n✅ Completed! Videos saved in: {current_output_path}")
