import socket
import threading
import zlib
import cv2
import numpy as np
from mss import mss
import pyautogui
import traceback
import struct
import time
import win32api
import win32con
import ctypes
import win32gui
from PIL import Image, ImageDraw

class ScreenCapture:
    def __init__(self):
        self.monitor = {'top': 0, 'left': 0, 'width': 1920, 'height': 1080}
        self.is_controlling = False
        self._thread_local = threading.local()
    
    @property
    def sct(self):
        if not hasattr(self._thread_local, 'sct_instance'):
            self._thread_local.sct_instance = mss()
        return self._thread_local.sct_instance
        
    def capture_screen_with_cursor(self):
        try:
            with mss() as sct:
                monitors = sct.monitors
                monitor = monitors[1] if len(monitors) > 1 else monitors[0]
                
                self.monitor = {
                    'top': monitor['top'],
                    'left': monitor['left'],
                    'width': monitor['width'],
                    'height': monitor['height']
                }
                
                screen = sct.grab(self.monitor)
                frame = np.array(screen)
                
                if self.is_controlling:
                    cursor_pos = win32gui.GetCursorPos()
                    x = cursor_pos[0] - self.monitor['left']
                    y = cursor_pos[1] - self.monitor['top']
                    
                    pil_img = Image.fromarray(frame)
                    draw = ImageDraw.Draw(pil_img)                    
                    size = 10
                    draw.line([(x, y - size), (x, y + size)], fill='red', width=2)
                    draw.line([(x - size, y), (x + size, y)], fill='red', width=2)
                    frame = np.array(pil_img)
                
                return frame
                
        except Exception as e:
            print(f"Screen capture error: {e}")
            return np.zeros((self.monitor['height'], self.monitor['width'], 3), dtype=np.uint8)

def handle_input_message(data, screen_capture):
    try:
        msg_type, length = struct.unpack('!BL', data[:5])
        message = data[5:5+length].decode()
        
        if msg_type == 7:
            screen_capture.is_controlling = (message == "1")
            return
        
        if not screen_capture.is_controlling:
            return
            
        if msg_type == 1:
            x, y = map(int, message.split(','))
            ctypes.windll.user32.SetCursorPos(x, y)
            
        elif msg_type in (4, 5):
            x, y, button = map(int, message.split(','))
            ctypes.windll.user32.SetCursorPos(x, y)
            event = win32con.MOUSEEVENTF_LEFTDOWN if msg_type == 4 else win32con.MOUSEEVENTF_LEFTUP
            if button == 2: event = win32con.MOUSEEVENTF_RIGHTDOWN if msg_type == 4 else win32con.MOUSEEVENTF_RIGHTUP
            if button == 3: event = win32con.MOUSEEVENTF_MIDDLEDOWN if msg_type == 4 else win32con.MOUSEEVENTF_MIDDLEUP
            win32api.mouse_event(event, x, y, 0, 0)
                    
        elif msg_type == 3:
            char = message
            if char.startswith('<') and char.endswith('>'):
                keys = char[1:-1].split('+')
                for key in keys:
                    vk = {
                        'ctrl': win32con.VK_CONTROL,
                        'alt': win32con.VK_MENU,
                        'shift': win32con.VK_SHIFT
                    }.get(key, ord(key.upper()))
                    win32api.keybd_event(vk, 0, 0, 0)
                for key in reversed(keys):
                    vk = {
                        'ctrl': win32con.VK_CONTROL,
                        'alt': win32con.VK_MENU,
                        'shift': win32con.VK_SHIFT
                    }.get(key, ord(key.upper()))
                    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
            else:
                vk = {
                    '\n': win32con.VK_RETURN,
                    '\t': win32con.VK_TAB,
                    '\b': win32con.VK_BACK,
                    '\x1b': win32con.VK_ESCAPE,
                    ' ': win32con.VK_SPACE
                }.get(char, ord(char.upper()))
                win32api.keybd_event(vk, 0, 0, 0)
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
                    
        elif msg_type == 6:
            x, y, delta = map(int, message.split(','))
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, x, y, delta, 0)
            
    except Exception as e:
        print(f"Input error: {e}")

def capture_and_stream(conn, screen_capture):
    try:
        monitor = screen_capture.monitor
        res_str = f"RES:{monitor['width']},{monitor['height']}"
        
        # Send resolution header
        header = struct.pack('!L', len(res_str))  # 4-byte length header
        conn.sendall(header + res_str.encode())
        
        # Compression settings
        jpeg_quality = 70
        zlib_level = 1
        
        while True:
            # Capture frame
            frame = screen_capture.capture_screen_with_cursor()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            # Encode and compress
            _, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
            compressed = zlib.compress(jpeg_buffer.tobytes(), level=zlib_level)
            
            # Send frame
            try:
                header = struct.pack('!L', len(compressed))  # 4-byte length header
                conn.sendall(header + compressed)
            except (BrokenPipeError, ConnectionResetError) as e:
                print(f"Connection lost: {e}")
                break
                
            time.sleep(1/30)  # Limit to ~30 FPS

    except Exception as e:
        print(f"Capture error: {str(e)}")
        traceback.print_exc()

def input_handler(conn, screen_capture):
    try:
        while True:
            header = conn.recv(5)
            if not header: break
            
            msg_type, length = struct.unpack('!BL', header)
            message = header + conn.recv(length)
            handle_input_message(message, screen_capture)
            
    except Exception as e:
        print(f"Input handler error: {e}")

def main():
    RELAY_IP = '192.168.1.137'  # Set this
    RELAY_PORT = 5000

    while True:
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((RELAY_IP, RELAY_PORT))
            conn.sendall(b"host")
            print("Connected to relay server")

            screen_capture = ScreenCapture()
            threading.Thread(target=capture_and_stream, args=(conn, screen_capture), daemon=True).start()
            threading.Thread(target=input_handler, args=(conn, screen_capture), daemon=True).start()

            while True: time.sleep(1)
            
        except Exception as e:
            print(f"Connection failed: {e}, retrying...")
            time.sleep(5)

if __name__ == "__main__":
    main()