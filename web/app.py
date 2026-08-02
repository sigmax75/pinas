"""PiNAS Web Manager"""

import os
import subprocess
import shutil
import zipfile
import tempfile
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse as FastFileResponse
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
    return templates.TemplateResponse(request=request, name="index.html", context={
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
                    # Count items and calc dir size
                    try:
                        child_count = len([x for x in os.listdir(full_path) if not x.startswith('.')])
                    except Exception:
                        child_count = 0
                    dir_size = 0
                    try:
                        for droot, ddirs, dfiles in os.walk(full_path):
                            ddirs[:] = [d for d in ddirs if not d.startswith('.')]
                            for df in dfiles:
                                try:
                                    dir_size += os.path.getsize(os.path.join(droot, df))
                                except OSError:
                                    pass
                    except Exception:
                        pass
                    if dir_size >= 1024**3:
                        dir_size_str = str(round(dir_size / (1024**3), 1)) + " GB"
                    elif dir_size >= 1024**2:
                        dir_size_str = str(round(dir_size / (1024**2), 1)) + " MB"
                    elif dir_size >= 1024:
                        dir_size_str = str(round(dir_size / 1024, 1)) + " KB"
                    else:
                        dir_size_str = str(dir_size) + " B"
                    items.append({
                        "name": entry,
                        "path": rel_path,
                        "type": "dir",
                        "items": child_count,
                        "size": dir_size_str,
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
    breadcrumb = [{"name": "\u30eb\u30fc\u30c8", "path": ""}]
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


@app.get("/api/download")
async def api_download(storage: str = "hot", path: str = ""):
    """Download a file"""
    if storage == "hot":
        base = config.HOT_DIR
    elif storage == "cold":
        base = config.COLD_DIR
    else:
        raise HTTPException(status_code=400, detail="Invalid storage")

    if ".." in path or not path:
        raise HTTPException(status_code=400, detail="Invalid path")

    filepath = os.path.join(base, path)
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(filepath)
    return FastFileResponse(path=filepath, filename=filename)


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), storage: str = Form("hot"), path: str = Form("")):
    """Upload a file to specified directory"""
    if storage == "hot":
        base = config.HOT_DIR
    elif storage == "cold":
        base = config.COLD_DIR
    else:
        return JSONResponse(content={"status": "error", "message": "Invalid storage"})

    if ".." in path:
        return JSONResponse(content={"status": "error", "message": "Invalid path"})

    target_dir = os.path.join(base, path) if path else base
    if not os.path.isdir(target_dir):
        return JSONResponse(content={"status": "error", "message": "Directory not found"})

    filename = file.filename or "uploaded_file"
    # Sanitize filename
    filename = filename.replace("/", "_").replace("\\", "_").replace("..", "_")

    filepath = os.path.join(target_dir, filename)

    # If file exists, add number suffix
    if os.path.exists(filepath):
        name, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(filepath):
            filepath = os.path.join(target_dir, f"{name}_{i}{ext}")
            i += 1

    contents = await file.read()
    with open(filepath, "wb") as f:
        f.write(contents)

    size_mb = round(len(contents) / (1024 * 1024), 1)
    return JSONResponse(content={"status": "ok", "filename": os.path.basename(filepath), "size_mb": size_mb})


@app.post("/api/mkdir")
async def api_mkdir(request: Request):
    """Create a new directory"""
    body = await request.json()
    storage = body.get("storage", "hot")
    path = body.get("path", "")
    name = body.get("name", "").strip()

    if not name or ".." in name or "/" in name or "\\" in name:
        return JSONResponse(content={"status": "error", "message": "Invalid folder name"})
    if ".." in path:
        return JSONResponse(content={"status": "error", "message": "Invalid path"})

    base = config.HOT_DIR if storage == "hot" else config.COLD_DIR
    target = os.path.join(base, path, name) if path else os.path.join(base, name)

    if os.path.exists(target):
        return JSONResponse(content={"status": "error", "message": "Already exists"})

    try:
        os.makedirs(target)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@app.post("/api/delete")
async def api_delete(request: Request):
    """Delete a file or directory"""
    body = await request.json()
    storage = body.get("storage", "hot")
    path = body.get("path", "")

    if not path or ".." in path:
        return JSONResponse(content={"status": "error", "message": "Invalid path"})

    base = config.HOT_DIR if storage == "hot" else config.COLD_DIR
    target = os.path.join(base, path)

    if not os.path.exists(target):
        return JSONResponse(content={"status": "error", "message": "Not found"})

    try:
        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@app.post("/api/rename")
async def api_rename(request: Request):
    """Rename a file or directory"""
    body = await request.json()
    storage = body.get("storage", "hot")
    path = body.get("path", "")
    new_name = body.get("new_name", "").strip()

    if not path or not new_name or ".." in path or ".." in new_name or "/" in new_name or "\\" in new_name:
        return JSONResponse(content={"status": "error", "message": "Invalid input"})

    base = config.HOT_DIR if storage == "hot" else config.COLD_DIR
    old_path = os.path.join(base, path)
    new_path = os.path.join(os.path.dirname(old_path), new_name)

    if not os.path.exists(old_path):
        return JSONResponse(content={"status": "error", "message": "Not found"})
    if os.path.exists(new_path):
        return JSONResponse(content={"status": "error", "message": "Name already exists"})

    try:
        os.rename(old_path, new_path)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@app.post("/api/move")
async def api_move(request: Request):
    """Move file between storages or within same storage"""
    body = await request.json()
    src_storage = body.get("src_storage", "")
    src_path = body.get("src_path", "")
    dst_storage = body.get("dst_storage", "")
    dst_path = body.get("dst_path", "")

    if not src_path or ".." in src_path or ".." in dst_path:
        return JSONResponse(content={"status": "error", "message": "Invalid path"})

    src_base = config.HOT_DIR if src_storage == "hot" else config.COLD_DIR
    dst_base = config.HOT_DIR if dst_storage == "hot" else config.COLD_DIR

    src_full = os.path.join(src_base, src_path)
    filename = os.path.basename(src_path)
    dst_dir = os.path.join(dst_base, dst_path) if dst_path else dst_base
    dst_full = os.path.join(dst_dir, filename)

    if not os.path.exists(src_full):
        return JSONResponse(content={"status": "error", "message": "Source not found"})

    try:
        os.makedirs(dst_dir, exist_ok=True)
        shutil.move(src_full, dst_full)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)})


@app.get("/api/download-zip")
async def api_download_zip(storage: str = "hot", path: str = ""):
    """Download a directory as ZIP"""
    if not path or ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    base = config.HOT_DIR if storage == "hot" else config.COLD_DIR
    target = os.path.join(base, path)

    if not os.path.isdir(target):
        raise HTTPException(status_code=400, detail="Not a directory")

    dirname = os.path.basename(path)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    tmp_path = tmp.name
    tmp.close()

    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(target):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    if f.startswith('.'):
                        continue
                    fpath = os.path.join(root, f)
                    arcname = os.path.join(dirname, os.path.relpath(fpath, target))
                    zf.write(fpath, arcname)

        return FastFileResponse(path=tmp_path, filename=dirname + '.zip', media_type='application/zip')
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


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
