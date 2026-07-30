# PiNAS Archive Script

SSD（ホットストレージ）から一定期間経過したデータファイルをHDD（コールドストレージ）に自動移動するスクリプト。

## Setup

### 1. HDD mount

```bash
# List connected drives
lsblk

# Create mount point
sudo mkdir -p /mnt/archive

# Mount (replace sdX1 with actual partition)
sudo mount /dev/sdX1 /mnt/archive

# Auto-mount on boot (add to /etc/fstab)
# UUID=xxxx-xxxx /mnt/archive ext4 defaults,nofail 0 2
```

### 2. Deploy script

```bash
# Copy files to Orange Pi
scp archive.sh archive.conf orangepi@192.168.94.222:~/

# Make executable
ssh orangepi@192.168.94.222 "chmod +x ~/archive.sh"
```

### 3. Test (dry run)

```bash
# DRY_RUN="yes" (default) - preview only, no files moved
./archive.sh
```

### 4. Run for real

```bash
# Edit config: set DRY_RUN="no"
nano archive.conf

# Execute
./archive.sh
```

### 5. Monthly cron

```bash
# Add to crontab (runs 1st of each month at 3:00 AM)
crontab -e
0 3 1 * * /home/orangepi/archive.sh
```

## Config (archive.conf)

| Setting | Default | Description |
|---------|---------|-------------|
| SOURCE_DIR | /mnt/ssd | Hot storage path |
| ARCHIVE_DIR | /mnt/archive | Cold storage path |
| AGE_DAYS | 365 | Move files older than N days |
| ARCHIVE_EXTENSIONS | (data files) | File types to move |
| EXCLUDE_DIRS | lost+found | Directories to skip |
| DRY_RUN | yes | Preview mode (no actual moves) |

## Safety

- Only moves data files (media, documents, archives)
- Skips scripts, configs, hidden files
- Preserves directory structure on HDD
- Dry run mode enabled by default
- Full log at /var/log/pinas-archive.log

## Web Manager

Browser-based dashboard for monitoring and managing archives.

### Start

```bash
cd web
pip3 install -r requirements.txt
./start.sh
```

Open http://192.168.94.222:8080 in your browser.

### Features

- **Storage Dashboard** - SSD/HDD usage with auto-refresh
- **File Search** - Search across hot and cold storage
- **Restore** - Move files from HDD back to SSD
- **Archive Control** - Run archive script from browser (dry run / real)
