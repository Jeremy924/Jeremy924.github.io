import serial
from serial.serialutil import SerialException
from serial.tools import list_ports
import time
import keyboard
import pyperclip

def list_serial_ports():
    """ Lists serial port names and descriptions matching the device's VID and PID. """
    pid = 21156
    vid = 1155
    ports = list_ports.comports()
    if not ports:
        print("No serial ports found.")
        return []
    port_nums = []
    for _port in sorted(ports):
        if _port.vid == vid and _port.pid == pid:
            port_nums.append(_port.device)
    return port_nums

def _get_serial_connection(port_arg):
    """Gets a serial connection, prompting user if necessary."""
    port_to_use = port_arg
    if not port_to_use:
        ports = list_serial_ports()
        if not ports:
            print("\033[1;31mError: No compatible RP-42 device found. Make sure device is connected and in docked mode (hold top left button while turning on).\033[0m")
            return None
        if len(ports) > 1:
            print('Available ports:', ports)
            port_to_use = input('Enter port: ')
        else:
            port_to_use = ports[0]
            print(f"Automatically selected port: {port_to_use}")

    try:
        return serial.Serial(port_to_use, 9600, timeout=1)
    except SerialException as e:
        print(f"Failed to open port {port_to_use}: {e}")
        return None
    
serial = _get_serial_connection(None)

if serial is None:
    exit()

while True:
    if serial.in_waiting != 0:
        next_line = serial.read(serial.in_waiting).replace(b'\x18', b'').replace(b'\x17', b'<').replace(b'\x05', b'').replace(b'\x06', b'').decode().replace('***', '').strip().lower()
        print(next_line)
        if next_line == "copy":
            print(pyperclip.paste().encode())
            serial.write((pyperclip.paste().strip() + "\n").encode())
            continue

        for key in next_line:
            if key in '<^()∠':
                keyboard.press('shift')
            if key == '∠':
                keyboard.send(',')
            else: keyboard.send(key)
            if key in '<^()∠':
                keyboard.release('shift')
            time.sleep(0.03)

    time.sleep(0.1)