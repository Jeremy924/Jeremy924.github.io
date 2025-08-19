#!/bin/python

import argparse
import sys
import time
import json
import urllib.request
from urllib.error import URLError
import ctypes
import re

import serial
from serial.serialutil import SerialException
from serial.tools import list_ports


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

def _get_text_from_internet(url):
    return list(map(lambda b: b.decode(), urllib.request.urlopen(url)))

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

def parse_app_info(data_string: str) -> dict | None:
    """
    Parses a string containing application information in a specific format.

    Args:
        data_string: A string containing the application information.
                     Expected format:
                     App Name: [Name] v. [Major].[Minor]
                     App Publisher: [Publisher]
                     Publish Date: [Month]/[Day]/20[Year]

    Returns:
        A dictionary containing the parsed information if the format matches,
        otherwise returns None. The dictionary includes:
        - 'app_name' (str)
        - 'version_major' (int)
        - 'version_minor' (int)
        - 'app_publisher' (str)
        - 'published_month' (int)
        - 'published_day' (int)
        - 'published_year' (int)
    """
    # Regex pattern to capture the named groups from the input string.
    # It's designed to be specific to the format provided.
    pattern = re.compile(
        r"App Name: (?P<app_name>.*?) v\. (?P<version_major>\d+)\.(?P<version_minor>\d+)\n"
        r"App Publisher: (?P<app_publisher>.*?)\n"
        r"Publish Date: (?P<published_month>\d+)/(?P<published_day>\d+)/20(?P<published_year>\d+)"
    )

    # Search the input string for a match
    match = pattern.search(data_string)

    # If a match is found, extract the data
    if match:
        # Get all the captured groups as a dictionary
        app_data = match.groupdict()

        # Convert numeric fields from string to integer
        try:
            app_data['version_major'] = int(app_data['version_major'])
            app_data['version_minor'] = int(app_data['version_minor'])
            app_data['published_month'] = int(app_data['published_month'])
            app_data['published_day'] = int(app_data['published_day'])
            app_data['published_year'] = int(app_data['published_year'])
            return app_data
        except (ValueError, TypeError):
            # This handles cases where conversion fails, though the regex
            # should prevent non-digit characters from being matched.
            return None

    # Return None if the pattern does not match
    return None

def get_latest_app_version(app_name):    
    try:
        result = _get_text_from_internet(f"https://Jeremy924.github.io/rp42/downloads/{app_name.lower()}.json")
        js = json.loads(''.join(result))
        return js
    except Exception:
        print("App not found. Check your network connection.")
        return None

def handle_updatable(args):
    ser = _get_serial_connection(args.port)

    if not ser:
        return
    
    print("Checking app versions")
    ser.write('echo off\napplist\n'.encode())
    time.sleep(0.2)
    app_strings = ser.read(ser.in_waiting).decode().split('\n\n')

    firmware_version = ""
    parsed_apps = []
    print("\n\033[4mCurrently installed\033[0m")
    for app_string in app_strings:
        parsed = parse_app_info(app_string)
        if not parsed:
            continue

        parsed_apps.append(parsed)
        print(f"{parsed['app_name']} = {parsed['version_major']}.{parsed['version_minor']}")
        if parsed['app_name'] == "firmware": firmware_version = str(parsed["version_major"]) + "." + str(parsed["version_minor"])

    if firmware_version == "":
        print("\033[1;31mError: firmware version unknown. Command will not work on firmware older than v. 0.11\033[0m")
        print("\033[1;31mError: firmware version unknown. Command will not work on firmware older than v. 0.11\033[0m")
        ser.write('echo on\n'.encode())
        return

    print("\n\033[4mChecking latest versions\033[0m")
    # check target
    for app in parsed_apps:
        latest_info = get_latest_app_version(app['app_name'])

        if latest_info is None:
            continue

        if app["app_name"] == "firmware":
            print("firmware latest:", latest_info[0]["version"])
            continue

        latest_compatible_version = None

        for entry in latest_info:
            if firmware_version in entry['target']:
                latest_compatible_version = entry
                break

        not_compatible_with_latest = latest_compatible_version != latest_info[0]
        if not_compatible_with_latest:
            print(f"\033[1;33mWarning: Current firmware is not compatible with the latest {app['app_name']}.\nUse '{sys.argv[0]} upgrade' to upgrade firmware to latest version.\033[0m")

        print(app['app_name'], "latest compatible:" if not_compatible_with_latest else "latest:", latest_compatible_version["version"])
    ser.write("echo on\n".encode())

def handle_news(args):
    print(''.join(_get_text_from_internet('https://jeremy924.github.io/rp42/downloads/news.txt')))

def handle_terminal(args):
    """Handles the logic for the 'terminal' command."""
    ser = _get_serial_connection(args.port)
    if not ser:
        return

    print("Connected to terminal. Type 'exit' or press Ctrl+C to quit.")
    ser.write('clear\n'.encode())
    time.sleep(0.2)
    ser.read(ser.in_waiting).decode()
    while True:
        command = input()
        if command.lower() == 'exit':
            break
        ser.write((command + '\n').encode())
        read_data = ''
        time.sleep(0.1)  # Give device time to respond
        while '$' not in read_data:
            response = ser.read(ser.in_waiting).decode()
            if response:
                read_data += response
                print(response, end='')
                time.sleep(0.1)
            else:
                break
    ser.close()
    print("\nTerminal session ended.")


def _show_progress(block_num, block_size, total_size):
    """Helper function to display download progress."""
    downloaded = block_num * block_size
    if total_size > 0:
        percent = downloaded * 100 / total_size
        percent = min(percent, 100)
        bar_length = 40
        filled_len = int(round(bar_length * downloaded / float(total_size)))
        bar = '█' * filled_len + '-' * (bar_length - filled_len)
        sys.stdout.write(f'\r  Progress: [{bar}] {percent:.1f}%')
        if downloaded >= total_size:
            sys.stdout.write('\n')
        sys.stdout.flush()


def _get_data_from_url(json_url, item_name, item_version='latest'):
    """Generic helper to fetch binary data from a JSON descriptor URL."""
    try:
        with urllib.request.urlopen(json_url) as response:
            data_list = json.loads(response.read().decode('utf-8'))

        target_item_info = None
        if item_version.lower() == 'latest':
            target_item_info = data_list[0]
        else:
            target_item_info = next((item for item in data_list if item['version'] == item_version), None)

        if not target_item_info:
            print(f"Error: Version '{item_version}' for '{item_name}' not found.")
            print("Available versions:", ", ".join([v['version'] for v in data_list]))
            return None, None, None

        publisher     = target_item_info["publisher"] if "publisher" in target_item_info else "."
        publish_date  = target_item_info['publish_date'] if "publish_date" in target_item_info else "7/21/2025"
        final_version = target_item_info['version']
        download_url  = target_item_info['url']

        print(f"Downloading '{item_name}' version {final_version} from: {download_url}")
        temp_filename, _ = urllib.request.urlretrieve(download_url, reporthook=_show_progress)
        with open(temp_filename, 'rb') as f:
            data = f.read()
        return data, final_version, publisher, publish_date
    except URLError as e:
        print(f"\nAn error occurred while fetching data: {e.reason}")
        return None, None, None, None
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return None, None, None, None


def _get_app_data(app_name, app_version='latest', download=True):
    """Fetches app metadata and returns the binary data and final version string."""
    APPS_LIST_URL = "https://jeremy924.github.io/rp42/downloads/apps.json"
    app_name = app_name.capitalize()
    try:
        with urllib.request.urlopen(APPS_LIST_URL) as response:
            apps_data = json.loads(response.read().decode('utf-8'))
        app_info_url = next((d[app_name] for d in apps_data if app_name in d), None)
        if not app_info_url:
            print(f"\033[1;31mError: '{app_name}' application binary not available for download.\033[0m")
            exit()
        if download:
            return _get_data_from_url(app_info_url, app_name, app_version)
        else: return (app_name, app_version)
    except URLError as e:
        print(f"\n\033[1;31mAn error occurred while fetching the app list: {e.reason}\033[0m")
        exit()


def handle_download(args):
    """Handles downloading a binary to a local file."""
    print(f"Command: download software '{args.name}'")
    data, version, publisher, publish_date = _get_app_data(args.name, args.version or 'latest')
    if data:
        output_file = args.output if args.output else f"{args.name}-{version}.bin"
        with open(output_file, 'wb') as f:
            f.write(data)
        print(f"\nDownload completed successfully! Saved as {output_file}")


def compute_checksum(data: bytes) -> int:
    """Computes the device-specific checksum for a block of data."""
    checksum_obj = ctypes.c_int32(0)
    for b_val in data:
        if b_val != 255:
            checksum_obj.value += b_val
    return int(checksum_obj.value)


def install_binary(data: bytes, ser: serial.Serial, offset: int = 0, erase_command: str = 'flashec',
                   legacy_firmware: bool = False) -> bool:
    """The core binary installation logic for apps and firmware."""

    def _print_status(current, total):
        ser.write(f'progress {int(current / total * 256)}\n'.encode())

    ser.read(ser.in_waiting)

    ser.write('echo off\nmscn\nunlock 532326\n'.encode())
    ser.read(ser.in_waiting)

    print("Erasing target memory...")
    ser.write(f'alert\nERASING\n{erase_command}\n'.encode())
    while ser.in_waiting == 0:
        time.sleep(0.1)
    ser.read(ser.in_waiting)

    print("Writing data to device...")
    ser.write('alert\nDOWNLOADING\n'.encode())

    size = 1024
    status_update_count = 0
    total_len = len(data)

    for i in range(0, total_len, size):
        if status_update_count >= 5:
            _print_status(i, total_len)
            status_update_count = 0
        chunk = data[i:i + size]
        if len(chunk) < size: chunk += b'\xFF' * (size - len(chunk))
        ser.write(f'flashw {i + offset} {size} \n'.encode())
        ser.write(chunk)
        while True:
            time.sleep(0.01)

            if ser.in_waiting != 0 and 'done'.encode() in ser.read(ser.in_waiting):
                break
        status_update_count += 1
        _show_progress(i + size, 1, total_len)
    _show_progress(1, 1, 1)

    print("\nVerifying checksum...")
    ser.read(ser.in_waiting)
    ser.write('flashcheck\n'.encode())
    while ser.in_waiting == 0: time.sleep(0.1)

    calculated_checksum = 0
    try:
        calculated_checksum = int(ser.read(ser.in_waiting).decode().strip())
    except (ValueError, IndexError):
        print("Warning: Could not read checksum from device.")

    actual_sum = compute_checksum(data)
    if calculated_checksum != actual_sum:
        # The check is performed, but a mismatch will only print a warning and not stop the process.
        print(
            f'Warning: Checksum mismatch! Expected {actual_sum}, got {calculated_checksum}. Proceeding with installation anyway.')
    else:
        print("Checksum OK.")

    if erase_command == 'flashef':  # Firmware specific finalization
        if legacy_firmware:
            # Legacy firmware requires manual button press to finalize
            ser.write("progress 0\nalert\nHold down button 1\n".encode())
            input(
                "--> Please hold down the top-left button on your calculator until it resets, then press Enter on your PC.")
        else: 
            if legacy_firmware:
                ser.write("bootmode 1\n".encode())
            else:
                ser.write("bootmode 0\n".encode())
        # Both methods end with the pfirm command
        ser.write('progress 0 \nalert\nINSTALLING\npfirm\n'.encode())
        print("Finalizing firmware installation, please wait...")
        time.sleep(5)
    else:  # App specific finalization
        ser.write('progress 0 \nalert\nDone! Resetting...\nlock\necho on\n'.encode())
        time.sleep(2)
        ser.write('bootmode 0\nreset\n'.encode())

    ser.close()
    print("Installation complete. Device is resetting.")
    return True


def setup_fs(ser: serial.Serial):
    """Sets up the initial filesystem structure on the device."""
    print("\nSetting up filesystem. This will take about a minute...")
    print("IMPORTANT: Do not interact with the calculator while this is running.")
    ser.write('echo off\nmscn\n'.encode())
    ser.write('unlock 532326\nalert\nCreating Filesystem\nlock\nmkfs\n'.encode())
    time.sleep(45)  # Wait for mkfs to complete

    print("Creating initial folders...")
    ser.write('unlock 532326\nalert\nSetting up Folders\nlock\n'.encode())
    ser.write('mkdir System\nmkdir Apps\nmkdir AppData\n'.encode())
    ser.write('unlock 532326\nalert\ndone\nlock\n'.encode())
    ser.write('bootmode 1\nhostnamectl RP-42\nreset\n'.encode())
    time.sleep(2)
    print("Filesystem setup complete.")

    ser.close()


def handle_install(args):
    """Handles installing an application."""
    if not ((args.name is not None) ^ (args.file is not None)):
        print("Error: You must specify either an application name or a --file path, but not both.")
        return

    app_data = None
    if args.name:
        version_to_get = args.version or 'latest'
        app_data, version, publisher, publish_date = _get_app_data(args.name, version_to_get)
    elif args.file:
        try:
            with open(args.file, 'rb') as f:
                app_data = f.read()
        except FileNotFoundError:
            print(f"Error: File not found at {args.file}"); return

    if not app_data: print("Failed to get application data. Aborting."); return

    ser = _get_serial_connection(args.port)
    if not ser: print("\033[1;31mCould not establish serial connection. Aborting.\033[0m"); return

    if args.name is not None:
        ser.write(f'mkdir /AppData/{args.name}\n'.encode())

        version_split = version.split(".")
        version_major, version_minor = version_split[0], version_split[1]
        publish_month,publish_day, publish_year = publish_date.split("/")
        ser.write(f"unlock 532326\nappinfo_update {args.name} {version_major} {version_minor} {publisher} {publish_month} {publish_day} {publish_year[2:]}\nlock\n".encode())
        ser.write("hostname RP-42\n".encode())

    install_binary(app_data, ser)


def handle_upgrade(args, legacy_mode=False):
    """Handles upgrading the device firmware."""
    if args.file is None:
        print(f"Attempting to upgrade firmware to version '{args.version}'...")
        FIRMWARE_URL = "https://jeremy924.github.io/rp42/downloads/firmware.json"
        firmware_data, version, publisher, publish_date = _get_data_from_url(FIRMWARE_URL, "Firmware", args.version)
        if not firmware_data: print("Could not download firmware. Aborting."); return
        print(f"Downloaded firmware version {version} ({len(firmware_data)} bytes).")

        ser = _get_serial_connection(args.port)
        if not ser: print("Could not establish serial connection. Aborting."); return

        version_split = version.split('.')
        vmajor = version_split[0]
        vminor = version_split[1]
        pmonth, pday, pyear = publish_date.split("/")
        ser.write(f"unlock 532326\nappinfo_update firmware {vmajor} {vminor} Jeremy924 {pmonth} {pday} {pyear[2:]}\nlock\n".encode())
    else:
        print(f"\033[1;33mWarning: Upgrading from incorrect file will make the calculator unusable.\033[0m")
        yes = input(f"\033[1;33mAre you sure you want to continue? (yes/no): \033[0m")
        if yes != 'yes':
            return
        ser = _get_serial_connection(args.port)
        if not ser: print("Could not establish serial connection. Aborting."); return
        firmware_data = open(args.file, 'rb').read()


    install_binary(firmware_data, ser, offset=0x7C0000, erase_command='flashef', legacy_firmware=legacy_mode)


def handle_legacy_upgrade(args):
    """Performs the full legacy upgrade: firmware, filesystem, and Free42."""
    print("--- Starting Legacy Upgrade Process ---")

    # Step 1: Upgrade Firmware in legacy mode
    print("\n[Step 1 of 3] Upgrading Firmware...")
    handle_upgrade(args, legacy_mode=True)
    print("\nFirmware upgrade finished. Please wait for the device to reset...")
    time.sleep(10)  # Give device time to reset and reconnect

    # Step 2: Setup Filesystem
    print("\n[Step 2 of 3] Setting up Filesystem...")
    ser_fs = _get_serial_connection(args.port)
    if not ser_fs: print("Could not reconnect to device for FS setup. Aborting."); return
    setup_fs(ser_fs)
    print("\nFilesystem setup finished. Please wait for the device to reset...")
    time.sleep(10)

    # Step 3: Install Free42
    print("\n[Step 3 of 3] Installing Free42 Application...")
    free42_data, _ = _get_app_data("Free42", "latest")
    if not free42_data: print("Could not download Free42. Aborting."); return
    ser_install = _get_serial_connection(args.port)
    if not ser_install: print("Could not reconnect to device for app installation. Aborting."); return
    install_binary(free42_data, ser_install)

    print("\n--- Legacy Upgrade Process Complete! ---")

header_location = 'https://jeremy924.github.io/rp42/downloads/header0.3.1.txt'

def main():
    """Main function to set up and parse arguments."""
    header = ''
    try:
        header = '\n'.join(_get_text_from_internet(header_location))
    except:
        pass
    parser = argparse.ArgumentParser(
        description=f"A command-line tool for managing RP-42 applications and firmware. CLI v. 0.3. {header}",
        epilog="Example: %(prog)s install Free42 --version 0.0.5"
    )

    parser.add_argument('--port', type=str, help='Specify the connection port.')
    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

    parser_terminal = subparsers.add_parser('terminal', help='Connects to the RP-42 terminal.')
    parser_terminal.set_defaults(func=handle_terminal)

    parser_news = subparsers.add_parser('news', help='Gets the latest info about RP42.')
    parser_news.set_defaults(func=handle_news)

    parser_download = subparsers.add_parser('download', help='Downloads application binaries.')
    parser_download.add_argument('name', type=str, help='Name of the app to download.')
    parser_download.add_argument('--version', type=str, help='Version of the app to download (default: latest).')
    parser_download.add_argument('--output', '-o', type=str, help='Optional output file name.')
    parser_download.set_defaults(func=handle_download)

    parser_install = subparsers.add_parser('install',
                                           help='Installs an application. Specify an app name or a --file path.')
    parser_install.add_argument('name', nargs='?', default=None, type=str,
                                help='Name of the application to download and install.')
    parser_install.add_argument('--file', type=str, help='Path to the local .bin file to install.')
    parser_install.add_argument('--version', type=str, help='Version to install (only valid with a name).')
    parser_install.set_defaults(func=handle_install)

    parser_upgrade = subparsers.add_parser('upgrade', help='Upgrades RP-42 firmware.')
    parser_upgrade.add_argument('--version', type=str, default='latest',
                                help='Version to upgrade to (default: latest).')
    parser_upgrade.add_argument('--file', type=str, help='firmware file to install')
    parser_upgrade.set_defaults(func=handle_upgrade)

    parser_updatable = subparsers.add_parser('updatable', help='Checks if any updates are available.')
    parser_updatable.set_defaults(func=handle_updatable)

    parser_legacy_upgrade = subparsers.add_parser('legacy-upgrade',
                                                  help='Upgrades RP-42 from <0.9.1 to latest system. May also be used to fix installation errors.')
    parser_legacy_upgrade.add_argument('--version', type=str, default='latest',
                                       help='Version to upgrade to (default: latest).')
    parser_legacy_upgrade.set_defaults(func=handle_legacy_upgrade)

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
