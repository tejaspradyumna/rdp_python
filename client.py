import socket
import cv2
import zlib
import threading
import numpy as np
from pynput import mouse, keyboard
import traceback
import struct
import win32gui
import win32api
import win32con
from ctypes import windll
import tkinter as tk
from tkinter import ttk

class RemoteDesktop:
    def __init__(self, socket):
        self.socket = socket
        self.server_width = 0
        self.server_height = 0
        self.window_name = 'Remote Desktop'
        self.is_controlling = False
        self.is_minimized = False
        self.mouse_buttons = {
            win32con.WM_LBUTTONDOWN: 1,
            win32con.WM_RBUTTONDOWN: 2,
            win32con.WM_MBUTTONDOWN: 3,
        }
        self.blank_cursor = self.create_blank_cursor()
        self.create_control_window()

    def create_control_window(self):
        self.control_window = tk.Tk()
        self.control_window.title("Remote Control")
        self.control_window.geometry("200x100")
        
        style = ttk.Style()
        style.configure('Start.TButton', background='green')
        style.configure('Stop.TButton', background='red')
        
        self.start_button = ttk.Button(
            self.control_window, 
            text="Start Control",
            style='Start.TButton',
            command=self.start_control
        )
        self.start_button.pack(pady=10)
        
        self.stop_button = ttk.Button(
            self.control_window,
            text="Stop Control",
            style='Stop.TButton',
            command=self.stop_control
        )
        self.stop_button.pack(pady=10)
        self.stop_button['state'] = 'disabled'

    def start_control(self):
        self.is_controlling = True
        self.send_message(7, "1")
        self.start_button['state'] = 'disabled'
        self.stop_button['state'] = 'normal'

    def stop_control(self):
        self.is_controlling = False
        self.send_message(7, "0")
        self.start_button['state'] = 'normal'
        self.stop_button['state'] = 'disabled'

    def create_blank_cursor(self):
        try:
            POINTER = windll.user32.LoadCursorW(None, 32512)
            return POINTER
        except Exception as e:
            print(f"Error creating blank cursor: {e}")
            return None

    def hide_cursor(self):
        try:
            hwnd = win32gui.FindWindow(None, self.window_name)
            if hwnd and self.blank_cursor:
                win32gui.SetClassLong(hwnd, win32con.GCL_HCURSOR, self.blank_cursor)
        except Exception as e:
            print(f"Error hiding cursor: {e}")

    def send_message(self, msg_type, data):
        message = f"{data}".encode()
        header = struct.pack('!BL', msg_type, len(message))
        try:
            self.socket.sendall(header + message)
        except:
            pass

    def get_window_rect(self):
        hwnd = win32gui.FindWindow(None, self.window_name)
        if hwnd:
            try:
                rect = win32gui.GetWindowRect(hwnd)
                client_rect = win32gui.GetClientRect(hwnd)
                client_pos = win32gui.ClientToScreen(hwnd, (0, 0))
                
                border_width = ((rect[2] - rect[0]) - client_rect[2]) // 2
                title_height = (rect[3] - rect[1]) - client_rect[3] - border_width
                
                return (
                    client_pos[0],
                    client_pos[1],
                    client_pos[0] + client_rect[2],
                    client_pos[1] + client_rect[3]
                )
            except Exception as e:
                print(f"Error getting window rect: {e}")
                return rect
        return None

    def is_point_in_window(self, x, y):
        if self.is_minimized:
            return False
            
        rect = self.get_window_rect()
        if rect:
            left, top, right, bottom = rect
            return left <= x <= right and top <= y <= bottom
        return False

    def scale_coordinates(self, x, y):
        rect = self.get_window_rect()
        if not rect:
            return None, None
            
        left, top, right, bottom = rect
        window_width = right - left
        window_height = bottom - top
        
        rel_x = x - left
        rel_y = y - top
        
        scaled_x = int((rel_x * self.server_width) / window_width)
        scaled_y = int((rel_y * self.server_height) / window_height)
        
        return scaled_x, scaled_y

    def check_window_state(self):
        hwnd = win32gui.FindWindow(None, self.window_name)
        if hwnd:
            self.is_minimized = not win32gui.IsWindowVisible(hwnd)
        return True

    def receive_frames(self):
        try:
            header = self.socket.recv(4)
            if len(header) != 4:
                print("Invalid resolution header")
                return
                
            res_length = int.from_bytes(header, byteorder='big')
            screen_info = self.socket.recv(res_length).decode()
            
            if not screen_info.startswith("RES:"):
                print("Invalid resolution format")
                return
                
            self.server_width, self.server_height = map(int, screen_info.split(":")[1].split(","))
            print(f"Server screen resolution: {self.server_width}x{self.server_height}")
            
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, self.server_width // 2, self.server_height // 2)
            
            self.hide_cursor()
            
            while True:
                self.check_window_state()
                
                size_bytes = self.socket.recv(4)
                if not size_bytes:
                    break
                
                size = int.from_bytes(size_bytes, byteorder='big')
                data = b''
                while len(data) < size:
                    packet = self.socket.recv(min(size - len(data), 8192))
                    if not packet:
                        break
                    data += packet
                
                decompressed = zlib.decompress(data)
                frame = cv2.imdecode(np.frombuffer(decompressed, dtype=np.uint8), 1)
                
                if frame is not None:
                    cv2.imshow(self.window_name, frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key != 255 and self.is_controlling:
                        self.send_message(3, chr(key))
                
        except Exception as e:
            print(f"Receive error: {str(e)}")
            traceback.print_exc()
        finally:
            cv2.destroyAllWindows()

    def on_move(self, x, y):
        if self.is_controlling and self.is_point_in_window(x, y):
            scaled_x, scaled_y = self.scale_coordinates(x, y)
            if scaled_x is not None and scaled_y is not None:
                self.send_message(1, f"{scaled_x},{scaled_y}")

    def on_click(self, x, y, button, pressed):
        if self.is_controlling and self.is_point_in_window(x, y):
            scaled_x, scaled_y = self.scale_coordinates(x, y)
            if scaled_x is not None and scaled_y is not None:
                button_num = 1  # Left click default
                if str(button) == "Button.right":
                    button_num = 2
                elif str(button) == "Button.middle":
                    button_num = 3
                
                msg_type = 4 if pressed else 5
                self.send_message(msg_type, f"{scaled_x},{scaled_y},{button_num}")

    def on_scroll(self, x, y, dx, dy):
        if self.is_controlling and self.is_point_in_window(x, y):
            scaled_x, scaled_y = self.scale_coordinates(x, y)
            if scaled_x is not None and scaled_y is not None:
                # Convert scroll units to Windows compatible values
                scroll_amount = int(dy * 120)  # Windows uses 120 units per scroll notch
                self.send_message(6, f"{scaled_x},{scaled_y},{scroll_amount}")

    def on_press(self, key):
        if not self.is_controlling:
            return
            
        try:
            if isinstance(key, keyboard.KeyCode):
                # Handle combination keys (Ctrl, Alt, Shift)
                modifiers = []
                if win32api.GetKeyState(win32con.VK_CONTROL) & 0x8000:
                    modifiers.append('ctrl')
                if win32api.GetKeyState(win32con.VK_MENU) & 0x8000:
                    modifiers.append('alt')
                if win32api.GetKeyState(win32con.VK_SHIFT) & 0x8000:
                    modifiers.append('shift')
                
                if modifiers:
                    # Send special combination key message
                    combo = '+'.join(modifiers + [key.char])
                    self.send_message(3, f"<{combo}>")
                else:
                    self.send_message(3, key.char)
            else:
                special_keys = {
                    keyboard.Key.enter: '\n',
                    keyboard.Key.tab: '\t',
                    keyboard.Key.space: ' ',
                    keyboard.Key.backspace: '\b',
                    keyboard.Key.esc: '\x1b'
                }
                if key in special_keys:
                    self.send_message(3, special_keys[key])
        except Exception as e:
            print(f"Keyboard error: {str(e)}")

def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        server_ip = input("Enter server IP: ")
        s.connect((server_ip, 5000))
        print("Connected to server!")
        
        remote = RemoteDesktop(s)
        
        receiver_thread = threading.Thread(target=remote.receive_frames, daemon=True)
        receiver_thread.start()
        
        with mouse.Listener(
            on_move=remote.on_move,
            on_click=remote.on_click,
            on_scroll=remote.on_scroll) as mouse_listener, \
            keyboard.Listener(
                on_press=remote.on_press) as keyboard_listener:
            
            remote.control_window.mainloop()
            
    except Exception as e:
        print(f"Connection error: {str(e)}")
        traceback.print_exc()
    finally:
        s.close()

if __name__ == "__main__":
    main()