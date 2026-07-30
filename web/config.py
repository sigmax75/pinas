import os

# Storage paths
HOT_DIR = "/mnt/ssd"
COLD_DIR = "/mnt/archive"

# Archive script path
ARCHIVE_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "archive.sh")
ARCHIVE_CONF = os.path.join(os.path.dirname(os.path.dirname(__file__)), "archive.conf")

# Server
HOST = "0.0.0.0"
PORT = 8080

# Data file extensions (same as archive.conf)
DATA_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".heic", ".heif", ".tiff", ".tif", ".raw", ".cr2", ".nef",
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".aiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
    ".csv", ".txt", ".rtf",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bak",
}
