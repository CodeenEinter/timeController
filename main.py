import io
import sys
import time
import ctypes
import json
import pygame
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import filedialog
from mutagen.mp3 import MP3


class LASTINPUTINFO(ctypes.Structure):  # 定义结构体
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('dwTime', ctypes.c_uint)
    ]


exit_program = False


def get_idle_duration():  # 获取空闲时间
    last_input_info = LASTINPUTINFO()
    last_input_info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input_info))
    idle_time = ctypes.windll.kernel32.GetTickCount() - last_input_info.dwTime
    return idle_time / 1000  # Convert milliseconds to seconds


def load_config():  # 读取配置文件
    try:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        return {
            "check_interval": 30,  # seconds
            "notify_locked_threshold": 1800,  # seconds
            "notify_unlocked_threshold": 7200,  # seconds
            "sound_file_path": "./sound.mp3"
        }


def save_config(config):  # 保存配置文件
    with open('config.json', 'w') as config_file:
        json.dump(config, config_file, indent=4)


class ConfigApp:  # 配置 GUI
    def __init__(self, master):
        self.master = master
        self.master.title("配置提醒时间")
        self.create_widgets()
        self.load_config()

    def create_widgets(self):  # 创建配置界面
        self.check_interval_label = tk.Label(self.master, text="检查间隔时间（秒）:")
        self.check_interval_label.pack()
        self.check_interval_entry = tk.Entry(self.master)
        self.check_interval_entry.pack()

        self.notify_locked_threshold_label = tk.Label(self.master, text="用户不在电脑前多久后发送通知（秒）:")
        self.notify_locked_threshold_label.pack()
        self.notify_locked_threshold_entry = tk.Entry(self.master)
        self.notify_locked_threshold_entry.pack()

        self.notify_unlocked_threshold_label = tk.Label(self.master, text="用户使用电脑多长时间后发送通知（秒）:")
        self.notify_unlocked_threshold_label.pack()
        self.notify_unlocked_threshold_entry = tk.Entry(self.master)
        self.notify_unlocked_threshold_entry.pack()

        self.sound_file_label = tk.Label(self.master, text="声音文件路径:")
        self.sound_file_label.pack()
        self.sound_file_entry = tk.Entry(self.master)
        self.sound_file_entry.pack()
        self.browse_button = tk.Button(self.master, text="浏览...", command=self.browse_file)
        self.browse_button.pack()

        self.save_button = tk.Button(self.master, text="保存配置", command=self.save_config)
        self.save_button.pack()

    def load_config(self):  # 加载配置
        config = load_config()
        self.check_interval_entry.insert(0, str(config['check_interval']))
        self.notify_locked_threshold_entry.insert(0, str(config['notify_locked_threshold']))
        self.notify_unlocked_threshold_entry.insert(0, str(config['notify_unlocked_threshold']))
        self.sound_file_entry.insert(0, config['sound_file_path'])

    def save_config(self):  # 保存配置
        config = {
            'check_interval': int(self.check_interval_entry.get()),
            'notify_locked_threshold': int(self.notify_locked_threshold_entry.get()),
            'notify_unlocked_threshold': int(self.notify_unlocked_threshold_entry.get()),
            'sound_file_path': self.sound_file_entry.get()
        }
        save_config(config)
        self.master.destroy()

    def browse_file(self):  # 选择音频文件
        filename = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav")])
        if filename:
            self.sound_file_entry.delete(0, tk.END)
            self.sound_file_entry.insert(0, filename)


def load_sound(file_path):  # 加载音频文件到内存中
    try:
        audio = MP3(file_path)
        with open(file_path, 'rb') as file:
            file_data = file.read()
        return file_data, audio.info.sample_rate, audio.info.bitrate, audio.info.channels
    except Exception as e:
        print(f"Error loading sound file: {e}")
        return None, None, None, None


def generate_sound(sound_data, sample_rate, sample_width, channels):  # 从内存中播放音频
    pygame.mixer.music.load(io.BytesIO(sound_data))
    pygame.mixer.music.play()


def create_image(width, height, color1, color2):  # 创建托盘图标
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle([(width // 2, height // 2), (width, height)], fill=color2)
    return image


def on_menu_exit(icon, item):  # 退出托盘图标
    global exit_program
    exit_program = True
    icon.stop()
    pygame.quit()


def open_settings(icon):  # 打开配置界面
    root = tk.Tk()
    app = ConfigApp(root)
    root.mainloop()
    # icon.stop()


def update_icon_title(icon, status, usage_time):  # 更新托盘图标标题
    if status == "locked":
        icon.title = f"电脑锁定 - 已使用 {usage_time}"
    elif status == "unlocked":
        icon.title = f"使用中 - 已使用 {usage_time}"


def main(keyboardInterrupt=None):  # 主程序
    global exit_program
    pygame.mixer.init()
    config = load_config()
    sound_data, sample_rate, sample_width, channels = load_sound(config['sound_file_path'])

    image = create_image(64, 64, 'black', 'blue')
    menu = (pystray.MenuItem('设置', open_settings), pystray.MenuItem('退出', on_menu_exit))
    icon = pystray.Icon("name", image, "电脑使用监控", menu)
    icon.run_detached()

    was_locked = False  # 新增变量，用于跟踪上次检查时屏幕是否锁定
    last_activity_time = time.time()  # 记录最后一次活动时间
    exit_program = False  # 控制程序退出的标志
    try:
        while True:
            if exit_program:
                break
            idle_duration = get_idle_duration()
            current_time = time.time()
            usage_time_seconds = current_time - last_activity_time
            usage_time_minutes = int(usage_time_seconds // 60)
            usage_time_hours = int(usage_time_seconds // 3600)

            if idle_duration > config['notify_locked_threshold']:
                if not was_locked:
                    icon.notify("电脑停止使用", "超过设定时间没有使用电脑。")
                    was_locked = True
            else:
                if was_locked and idle_duration < config['notify_locked_threshold']:
                    icon.notify("电脑重新使用", "您已重新开始使用电脑。")
                    was_locked = False

                # 检查用户连续使用电脑的时间是否超过阈值
                if current_time - last_activity_time > config['notify_unlocked_threshold'] and not was_locked:
                    generate_sound(sound_data, sample_rate, sample_width, channels)
                    icon.notify("休息提醒", "你已经使用电脑两个小时了，请注意休息。")
                    last_activity_time = current_time  # 重置活动时间

            # 更新图标标题
            usage_time_str = f"{usage_time_hours}小时{usage_time_minutes % 60}分钟"
            update_icon_title(icon, "locked" if was_locked else "unlocked", usage_time_str)
            print(f"Idle duration: {idle_duration} seconds, Usage time: {usage_time_str}")
            time.sleep(config['check_interval'])
    except KeyboardInterrupt:
        pass
    finally:
        icon.stop()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
