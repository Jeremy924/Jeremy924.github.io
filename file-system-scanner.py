import os

def get_directory_size(path: str) -> int:
    """Return total size of files in a directory (in bytes)."""
    total = 0
    for dirpath, _, filenames in os.walk(path, followlinks=False):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except (FileNotFoundError, PermissionError):
                # Skip files that can't be accessed
                continue
    print(f"{path} - {total / (1024 ** 3):.2f} GB")
    return total

def scan_directories(base_path: str, size_limit_gb: int = 5):
    """Scan directories under base_path and list those > size_limit_gb."""
    size_limit_bytes = size_limit_gb * (1024 ** 3)
    big_dirs = []

    for entry in os.scandir(base_path):
        if entry.is_dir(follow_symlinks=False):
            dir_size = get_directory_size(entry.path)
            if dir_size > size_limit_bytes:
                big_dirs.append((entry.path, dir_size))

    # Sort by size (largest first)
    big_dirs.sort(key=lambda x: x[1], reverse=True)

    print(f"\nDirectories in '{base_path}' larger than {size_limit_gb} GB:\n")
    for path, size in big_dirs:
        print(f"{path} - {size / (1024 ** 3):.2f} GB")

if __name__ == "__main__":
    folder_to_scan = "C:\\Users\\Jerem"  # change this
    scan_directories(folder_to_scan, 5)
