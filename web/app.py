"""PiNAS Web Manager"""

import os
import subprocess
import shutil
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

import config

app = FastAPI(title="PiNAS Manager")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def get_disk_usage(path):
    """Get disk usage for a path"""
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round((usage.used / usage.total) * 100, 1) if usage.total > 0 else 0,
        }
    except Exception:
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}


def count_files(path):
    """Count files recursively"""
    count = 0
    try:
        for root, dirs, files in os.walk(path):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            count += len(files)
    except Exception:
        pass
    return count


def search_files(base_path, query, storage_type):
    """Search files by name in a directory tree"""
    results = []
    query_lower = query.lower()
    try:
        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if query_lower in f.lower():
                    filepath = os.path.join(root, f)
                    relpath = os.path.relpath(filepath, base_path)
                    try:
                        stat = os.stat(filepath)
                        size_mb = round(stat.st_size / (1024 * 1024), 1)
                        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        size_mb = 0
                        mtime = "?"
                    results.append({
                        "name": f,
                        "path": relpath,
                        "size_mb": size_mb,
                        "modified": mtime,
                        "storage": storage_type,
                    })
                    if len(results) >= 100:
                        return results
    except Exception:
        pass
    return results


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard"""
    hot = get_disk_usage(config.HOT_DIR)
    cold = get_disk_usage(config.COLD_DIR)
    hot_files = count_files(config.HOT_DIR)
    cold_files = count_files(config.COLD_DIR)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "hot": hot,
        "cold": cold,
        "hot_files": hot_files,
        "cold_files": cold_files,
        "hot_dir": config.HOT_DIR,
        "cold_dir": config.COLD_DIR,
    })


@app.get("/api/browse")
async def api_browse(storage: str = "hot", path: str = ""):
    """Browse directory contents"""
    if storage == "hot":
        base = config.HOT_DIR
    elif storage == "cold":
        base = config.COLD_DIR
    else:
        return JSONResponse(content={"error": "Invalid storage type"})

    # Security: prevent path traversal
    if ".." in path:
        return JSONResponse(content={"error": "Invalid path"})

    target = os.path.join(base, path) if path else base

    if not os.path.exists(target):
        return JSONResponse(content={"error": "Path not found"})

    if not os.path.isdir(target):
        return JSONResponse(content={"error": "Not a directory"})

    items = []
    try:
        entries = sorted(os.listdir(target))
        for entry in entries:
            if entry.startswith('.'):
                continue
            full_path = os.path.join(target, entry)
            rel_path = os.path.join(path, entry) if path else entry
            try:
                stat = os.stat(full_path)
                is_dir = os.path.isdir(full_path)
                if is_dir:
                    # Count items in directory
                    try:
                        child_count = len([x for x in os.listdir(full_path) if not x.startswith('.')])
                    except Exception:
                        child_count = 0
                    items.append({
                        "name": entry,
                        "path": rel_path,
                        "type": "dir",
                        "items": child_count,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
                else:
                    size = stat.st_size
                    if size >= 1024 * 1024 * 1024:
                        size_str = str(round(size / (1024**3), 1)) + " GB"
                    elif size >= 1024 * 1024:
                        size_str = str(round(size / (1024**2), 1)) + " MB"
                    elif size >= 1024:
                        size_str = str(round(size / 1024, 1)) + " KB"
                    else:
                        size_str = str(size) + " B"
                    items.append({
                        "name": entry,
                        "path": rel_path,
                        "type": "file",
                        "size": size_str,
                        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    })
            except Exception:
                continue
    except Exception as e:
        return JSONResponse(content={"error": str(e)})

    # Build breadcrumb
    breadcrumb = [{"name": "Root", "path": ""}]
    if path:
        parts = path.split("/")
        for i, part in enumerate(parts):
            breadcrumb.append({
                "name": part,
                "path": "/".join(parts[:i+1]),
            })

    return JSONResponse(content={
        "items": items,
        "breadcrumb": breadcrumb,
        "current_path": path,
        "storage": storage,
    })


@app.get("/api/search")
async def api_search(q: str = ""):
    """Search files across hot and cold storage"""
    if not q or len(q) < 2:
        return JSONResponse(content={"results": [], "error": "Enter at least 2 characters"})

    results = []
    results.extend(search_files(config.HOT_DIR, q, "hot"))
    results.extend(search_files(config.COLD_DIR, q, "cold"))

    # Sort by modified date descending
    results.sort(key=lambda x: x["modified"], reverse=True)

    return JSONResponse(content={"results": results[:100]})


@app.post("/api/restore")
async def api_restore(request: Request):
    """Move file from cold back to hot storage"""
    body = await request.json()
    relpath = body.get("path", "")

    if not relpath:
        return JSONResponse(content={"status": "error", "message": "No path specified"})

    # Security: prevent path traversal
    if ".." in relpath or relpath.startswith("/"):
        return JSONResponse(content={"status": "error", "message": "Invalid path"})

    src = os.path.join(config.COLD_DIR, relpath)
    dst = os.path.join(config.HOT_DIR, relpath)

    if not os.path.exists(src):
        return JSONResponse(content={"status": "error", "message": "File not found in archive"})

    try:
        dst_dir = os.path.dirname(dst)
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src, dst)
        return JSONResponse(content={"status": "ok", "message": f"Restored: {relpath}"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@app.post("/api/archive/run")
async def api_archive_run(request: Request):
    """Run archive script"""
    body = await request.json()
    dry_run = body.get("dry_run", True)

    if not os.path.exists(config.ARCHIVE_SCRIPT):
        return JSONResponse(content={"status": "error", "message": "Archive script not found"})

    # Temporarily set DRY_RUN in conf
    if not dry_run:
        # Read conf, set DRY_RUN=no, run, then restore
        try:
            with open(config.ARCHIVE_CONF, "r") as f:
                original_conf = f.read()
            modified_conf = original_conf.replace('DRY_RUN="yes"', 'DRY_RUN="no"')
            with open(config.ARCHIVE_CONF, "w") as f:
                f.write(modified_conf)
        except Exception as e:
            return JSONResponse(content={"status": "error", "message": f"Config error: {e}"})

    try:
        result = subprocess.run(
            ["bash", config.ARCHIVE_SCRIPT],
            capture_output=True, text=True, timeout=600
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        output = "Script timed out (10 min limit)"
    except Exception as e:
        output = str(e)
    finally:
        # Restore conf if we modified it
        if not dry_run:
            try:
                with open(config.ARCHIVE_CONF, "w") as f:
                    f.write(original_conf)
            except Exception:
                pass

    return JSONResponse(content={"status": "ok", "output": output})


@app.get("/api/dashboard")
async def api_dashboard():
    """Dashboard data refresh"""
    hot = get_disk_usage(config.HOT_DIR)
    cold = get_disk_usage(config.COLD_DIR)
    hot_files = count_files(config.HOT_DIR)
    cold_files = count_files(config.COLD_DIR)
    return JSONResponse(content={
        "hot": hot, "cold": cold,
        "hot_files": hot_files, "cold_files": cold_files,
    })
