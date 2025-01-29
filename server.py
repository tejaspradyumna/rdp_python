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
        self._sct = None
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
                if len(monitors) > 1:
                    monitor = monitors[1]
                else:
                    monitor = monitors[0]
                
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
                    color = 'red'
                    draw.line([(x, y - size), (x, y + size)], fill=color, width=2)
                    draw.line([(x - size, y), (x + size, y)], fill=color, width=2)
                    
                    frame = np.array(pil_img)
                
                return frame
                
        except Exception as e:
            print(f"Error in screen capture: {e}")
            traceback.print_exc()
            return np.zeros((self.monitor['height'], self.monitor['width'], 3), dtype=np.uint8)

def handle_input_message(data, screen_capture):
    try:
        msg_type, length = struct.unpack('!BL', data[:5])
        message = data[5:5+length].decode()
        
        if msg_type == 7:  # Control state
            screen_capture.is_controlling = (message == "1")
            return
        
        if not screen_capture.is_controlling:
            return
            
        if msg_type == 1:  # Mouse move
            x, y = map(int, message.split(','))
            ctypes.windll.user32.SetCursorPos(x, y)
            
        elif msg_type in (4, 5):  # Mouse down/up
            x, y, button = map(int, message.split(','))
            ctypes.windll.user32.SetCursorPos(x, y)
            
            if msg_type == 4:
                if button == 1:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
                elif button == 2:
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
                elif button == 3:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, x, y, 0, 0)
            else:
                if button == 1:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
                elif button == 2:
                    win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
                elif button == 3:
                    win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, x, y, 0, 0)
                    
        elif msg_type == 3:  # Keyboard
            char = message
            if char.startswith('<') and char.endswith('>'):
                keys = char[1:-1].split('+')
                for key in keys:
                    if key == 'ctrl':
                        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
                    elif key == 'alt':
                        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                    elif key == 'shift':
                        win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
                    else:
                        win32api.keybd_event(ord(key.upper()), 0, 0, 0)
                        win32api.keybd_event(ord(key.upper()), 0, win32con.KEYEVENTF_KEYUP, 0)
                
                for key in reversed(keys):
                    if key == 'ctrl':
                        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif key == 'alt':
                        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                    elif key == 'shift':
                        win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            else:
                special_keys = {
                    '\n': win32con.VK_RETURN,
                    '\t': win32con.VK_TAB,
                    '\b': win32con.VK_BACK,
                    '\x1b': win32con.VK_ESCAPE,
                    ' ': win32con.VK_SPACE
                }
                
                if char in special_keys:
                    key_code = special_keys[char]
                    win32api.keybd_event(key_code, 0, 0, 0)
                    win32api.keybd_event(key_code, 0, win32con.KEYEVENTF_KEYUP, 0)
                elif len(char) == 1:
                    win32api.keybd_event(ord(char.upper()), 0, 0, 0)
                    win32api.keybd_event(ord(char.upper()), 0, win32con.KEYEVENTF_KEYUP, 0)
                    
        elif msg_type == 6:  # Mouse wheel
            x, y, delta = map(int, message.split(','))
            win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, x, y, delta, 0)
            
    except Exception as e:
        print(f"Error handling input: {e}")
        traceback.print_exc()

def capture_and_stream(conn, screen_capture):
    try:
        monitor = screen_capture.monitor
        screen_width = monitor["width"]
        screen_height = monitor["height"]
        
        res_str = f"RES:{screen_width},{screen_height}"
        header = len(res_str).to_bytes(4, byteorder='big')
        conn.sendall(header + res_str.encode())
        
        print(f"Capturing screen: {screen_width}x{screen_height}")
        
        frame_interval = 1/30
        last_frame_time = 0
        
        while True:
            current_time = time.time()
            if current_time - last_frame_time < frame_interval:
                time.sleep(0.001)
                continue
            
            frame = screen_capture.capture_screen_with_cursor()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            compressed = zlib.compress(buffer.tobytes(), level=1)
            
            try:
                size = len(compressed)
                conn.sendall(size.to_bytes(4, byteorder='big'))
                conn.sendall(compressed)
                last_frame_time = current_time
            except Exception as e:
                print(f"Send error: {str(e)}")
                break
                
    except Exception as e:
        print(f"Capture error: {str(e)}")
        traceback.print_exc()

def input_handler(conn, screen_capture):
    try:
        header_size = 5
        while True:
            header = conn.recv(header_size)
            if not header or len(header) != header_size:
                break
                
            msg_type, length = struct.unpack('!BL', header)
            
            message = header
            while len(message) < header_size + length:
                chunk = conn.recv(header_size + length - len(message))
                if not chunk:
                    return
                message += chunk
            
            handle_input_message(message, screen_capture)
            
    except Exception as e:
        print(f"Input error: {str(e)}")
        traceback.print_exc()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', 5000))
    server_socket.listen(5)
    print("Server started. Waiting for connections...")
    
    try:
        while True:
            conn, addr = server_socket.accept()
            print(f"New connection from {addr}")
            screen_capture = ScreenCapture()
            threading.Thread(target=capture_and_stream, args=(conn, screen_capture), daemon=True).start()
            threading.Thread(target=input_handler, args=(conn, screen_capture), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()