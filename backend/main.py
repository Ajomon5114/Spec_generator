import sqlite3
import json
import os
import bcrypt
import uuid
import datetime
import io
from fastapi import FastAPI, Request, HTTPException, Depends, Response, File, UploadFile
from fastapi.responses import StreamingResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pdf_generator import generate_pdf_buffer
from pdf_parser import parse_pdf

import sys

def format_sqlite_timestamp(ts):
    if not ts:
        return ts
    if isinstance(ts, str) and len(ts) >= 19 and ts[4] == '-':
        return ts.replace(' ', 'T') + 'Z'
    return ts

app = FastAPI(title="SpecGenerator API")

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()
static_dir = os.path.join(base_path, 'static')

if getattr(sys, 'frozen', False):
    db_dir = os.path.dirname(sys.executable)
else:
    db_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(db_dir, 'specifications.db')

# Initialize DB
def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Templates table (base columns)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT UNIQUE NOT NULL,
            spec_data TEXT NOT NULL
        )
    ''')

    # Safely migrate templates table — add new columns if they don't exist yet
    for col, definition in [
        ("is_archived", "INTEGER NOT NULL DEFAULT 0"),
        ("notes",       "TEXT NOT NULL DEFAULT ''"),
        ("created_at",  "TIMESTAMP DEFAULT ''"),
        ("updated_at",  "TIMESTAMP DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE templates ADD COLUMN {col} {definition}")
        except Exception:
            pass  # Column already exists — safe to ignore
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')

    # Safely migrate users table
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT ''")
    except Exception:
        pass
    
    # Sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS app_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    ''')

    # Template versions table — stores up to 10 snapshots per template
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS template_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            spec_data TEXT NOT NULL,
            saved_by TEXT NOT NULL DEFAULT 'unknown',
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES templates (id) ON DELETE CASCADE
        )
    ''')

    # Activity log — records PDF generation, downloads, edits per user
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT NOT NULL DEFAULT 'unknown',
            action TEXT NOT NULL,
            template_id INTEGER,
            product_name TEXT,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Seed default settings
    cursor.execute("SELECT COUNT(*) FROM app_settings WHERE setting_key = 'protocols'")
    if cursor.fetchone()[0] == 0:
        default_protocols = [
            "Organoleptic",
            "Internal method",
            "Eur.Ph <2.2.32>",
            "Eur.Ph <2.9.34>",
            "Eur.Ph <2.9.12>",
            "EC <396/2005>",
            "EC<2023/915>",
            "Eur.Ph <2.8.18>",
            "EC<2023/951>",
            "Eur.Ph <2.4.24>",
            "Eur.Ph.<5.1.8>",
            "Internal method by HPLC"
        ]
        cursor.execute(
            "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)",
            ("protocols", json.dumps(default_protocols))
        )
    
    # Seed users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_hash = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode('utf-8')
        user_hash = bcrypt.hashpw(b"user", bcrypt.gensalt()).decode('utf-8')
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ("admin", admin_hash, "admin"))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", ("user", user_hash, "user"))

    # Seed templates if empty
    cursor.execute("SELECT COUNT(*) FROM templates")
    if cursor.fetchone()[0] == 0:
        seed_path = os.path.join(static_dir, 'data.json')
        if os.path.exists(seed_path):
            with open(seed_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                product_name = data.get('product_name', 'Default Product')
                cursor.execute(
                    "INSERT INTO templates (product_name, spec_data) VALUES (?, ?)", 
                    (product_name, json.dumps(data))
                )
                
    conn.commit()
    conn.close()

init_db()

def record_activity(cursor, user_id, username, action, template_id=None, product_name=None, details=None):
    cursor.execute('''
        INSERT INTO activity_log (user_id, username, action, template_id, product_name, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, action, template_id, product_name, details))

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Authentication Dependency
def get_current_user(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        return None
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.id, u.username, u.role, s.expires_at 
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    """, (token,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    user_id, username, role, expires_at = row
    
    # Check expiration
    if datetime.datetime.fromisoformat(expires_at) < datetime.datetime.utcnow():
        return None
        
    return {"id": user_id, "username": username, "role": role}

def require_auth(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_admin(user = Depends(require_auth)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def require_manager(user = Depends(require_auth)):
    if user["role"] not in ["admin", "dept_head"]:
        raise HTTPException(status_code=403, detail="Manager access required")
    return user

# Auth Endpoints
@app.post("/api/login")
async def login(request: Request, response: Response):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Missing credentials")
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    
    if not row or not bcrypt.checkpw(password.encode('utf-8'), row[1].encode('utf-8')):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    user_id = row[0]
    token = str(uuid.uuid4())
    expires_at = (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat()
    
    cursor.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    conn.commit()
    conn.close()
    
    response.set_cookie(
        key="session_token", 
        value=token, 
        httponly=True, 
        max_age=86400,
        samesite="lax"
    )
    return {"status": "success"}

@app.post("/api/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    
    response.delete_cookie("session_token")
    return {"status": "success"}

@app.get("/api/me")
async def get_me(user = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user

# View Routes (Return HTML directly)
@app.get("/login")
async def login_page():
    with open(os.path.join(static_dir, 'login.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    return HTMLResponse(content=html)

@app.get("/")
async def root():
    with open(os.path.join(static_dir, 'index.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    return HTMLResponse(content=html)



# API Routes
@app.post("/generate")
async def generate_pdf_endpoint(request: Request, user = Depends(require_auth)):
    data = await request.json()
    pdf_buffer = generate_pdf_buffer(data)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    record_activity(cursor, user["id"], user["username"], "Generated PDF", product_name=data.get("product_name", "Unknown"))
    conn.commit()
    conn.close()
    
    return StreamingResponse(
        pdf_buffer, 
        media_type="application/pdf", 
        headers={"Content-Disposition": "attachment; filename=specification.pdf"}
    )

@app.get("/api/templates")
async def get_templates(user = Depends(require_auth)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Check if is_archived exists, if not, fallback
    try:
        cursor.execute("SELECT id, product_name, spec_data, is_archived, notes, updated_at FROM templates")
        rows = cursor.fetchall()
        has_new_cols = True
    except:
        cursor.execute("SELECT id, product_name, spec_data FROM templates")
        rows = cursor.fetchall()
        has_new_cols = False
    conn.close()
    
    templates = []
    for row in rows:
        try:
            t = {
                "id": row[0],
                "product_name": row[1],
                "spec_data": json.loads(row[2])
            }
            if has_new_cols:
                t["is_archived"] = bool(row[3])
                t["notes"] = row[4] if row[4] else ""
                t["updated_at"] = format_sqlite_timestamp(row[5])
            else:
                t["is_archived"] = False
                t["notes"] = ""
                t["updated_at"] = None
        except json.JSONDecodeError:
            t = {
                "id": row[0],
                "product_name": row[1],
                "spec_data": {},
                "is_archived": False,
                "notes": "",
                "updated_at": None
            }
        templates.append(t)
    return {"templates": templates}

@app.post("/api/save-template")
async def save_template_endpoint(request: Request, user = Depends(require_auth)):
    data = await request.json()
    product_name = data.get('product_name', 'Unnamed Product')
    notes = data.get('notes', '')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM templates WHERE product_name = ?", (product_name,))
        existing = cursor.fetchone()
        
        spec_data_json = json.dumps(data.get('spec_data', data)) # handle if spec_data is nested or not
        # In this app, the entire payload is often just the spec_data.
        
        template_id = None
        if existing:
            template_id = existing[0]
            try:
                cursor.execute("UPDATE templates SET spec_data = ?, notes = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (json.dumps(data), notes, template_id))
            except:
                cursor.execute("UPDATE templates SET spec_data = ? WHERE id = ?", (json.dumps(data), template_id))
        else:
            try:
                cursor.execute("INSERT INTO templates (product_name, spec_data, notes) VALUES (?, ?, ?)", (product_name, json.dumps(data), notes))
            except:
                cursor.execute("INSERT INTO templates (product_name, spec_data) VALUES (?, ?)", (product_name, json.dumps(data)))
            template_id = cursor.lastrowid
            
        # Save version
        if template_id is not None:
            try:
                cursor.execute("SELECT MAX(version_number) FROM template_versions WHERE template_id = ?", (template_id,))
                max_v = cursor.fetchone()[0] or 0
                next_v = max_v + 1
                cursor.execute("INSERT INTO template_versions (template_id, version_number, spec_data, saved_by) VALUES (?, ?, ?, ?)",
                               (template_id, next_v, json.dumps(data), user['username']))
                # Keep only last 10 versions
                cursor.execute("DELETE FROM template_versions WHERE template_id = ? AND version_number <= ?", (template_id, next_v - 10))
            except Exception as e:
                print("Version tracking error:", e)
                
        record_activity(cursor, user["id"], user["username"], "Saved Template", template_id=template_id, product_name=product_name)
        
        conn.commit()
        return {"status": "success", "message": "Template saved successfully", "id": template_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: int, user = Depends(require_manager)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT product_name FROM templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        product_name = row[0] if row else "Unknown"
        
        cursor.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        
        record_activity(cursor, user["id"], user["username"], "Deleted Template", template_id=template_id, product_name=product_name)
        
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/parse-pdf")
async def parse_pdf_endpoint(file: UploadFile = File(...), user = Depends(require_auth)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        contents = await file.read()
        file_stream = io.BytesIO(contents)
        parsed_data = parse_pdf(file_stream)
        return {"status": "success", "data": parsed_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT setting_key, setting_value FROM app_settings")
    rows = cursor.fetchall()
    conn.close()
    
    settings = {}
    for row in rows:
        settings[row[0]] = json.loads(row[1])
    return {"settings": settings}

@app.post("/api/settings")
async def save_settings(request: Request, user = Depends(require_admin)):
    data = await request.json()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        for key, value in data.items():
            cursor.execute("SELECT setting_key FROM app_settings WHERE setting_key = ?", (key,))
            if cursor.fetchone():
                cursor.execute("UPDATE app_settings SET setting_value = ? WHERE setting_key = ?", (json.dumps(value), key))
            else:
                cursor.execute("INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)", (key, json.dumps(value)))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# -----------------------------
# PHASE 3 API ENDPOINTS
# -----------------------------

@app.post("/api/templates/{template_id}/duplicate")
async def duplicate_template(template_id: int, user = Depends(require_auth)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT product_name, spec_data, notes FROM templates WHERE id = ?", (template_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Template not found")
        
        new_name = row[0] + " (Copy " + str(uuid.uuid4())[:4] + ")"
        cursor.execute("INSERT INTO templates (product_name, spec_data, notes) VALUES (?, ?, ?)", (new_name, row[1], row[2]))
        new_id = cursor.lastrowid
        
        record_activity(cursor, user["id"], user["username"], "Duplicated Template", template_id=new_id, product_name=new_name)
        
        conn.commit()
        return {"status": "success", "new_id": new_id, "new_name": new_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/templates/{template_id}/versions")
async def get_template_versions(template_id: int, user = Depends(require_auth)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT version_number, saved_by, saved_at, spec_data FROM template_versions WHERE template_id = ? ORDER BY version_number DESC", (template_id,))
        versions = [{"version": r[0], "saved_by": r[1], "saved_at": format_sqlite_timestamp(r[2]), "spec_data": json.loads(r[3])} for r in cursor.fetchall()]
        return {"status": "success", "versions": versions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



@app.get("/api/templates/export/{template_id}")
async def export_template(template_id: int, user = Depends(require_auth)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT product_name, spec_data, notes FROM templates WHERE id = ?", (template_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    
    export_data = {
        "product_name": row[0],
        "spec_data": json.loads(row[1]),
        "notes": row[2]
    }
    
    # Generate JSON file download
    import io
    file_bytes = json.dumps(export_data, indent=2).encode('utf-8')
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=template_{template_id}.json"}
    )

@app.post("/api/templates/import")
async def import_template(file: UploadFile = File(...), user = Depends(require_auth)):
    try:
        contents = await file.read()
        data = json.loads(contents)
        product_name = data.get("product_name", f"Imported {uuid.uuid4().hex[:6]}")
        spec_data = data.get("spec_data", {})
        notes = data.get("notes", "")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # append random hex to avoid name collisions
        cursor.execute("SELECT id FROM templates WHERE product_name = ?", (product_name,))
        if cursor.fetchone():
            product_name += f" ({uuid.uuid4().hex[:4]})"
            
        cursor.execute("INSERT INTO templates (product_name, spec_data, notes) VALUES (?, ?, ?)", (product_name, json.dumps(spec_data), notes))
        
        record_activity(cursor, user["id"], user["username"], "Imported Template", template_id=cursor.lastrowid, product_name=product_name)
        
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Template imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.get("/api/users")
async def list_users(user = Depends(require_admin)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role FROM users")
    users = [{"id": r[0], "username": r[1], "role": r[2]} for r in cursor.fetchall()]
    conn.close()
    return {"users": users}

@app.post("/api/users")
async def create_user(request: Request, user = Depends(require_admin)):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "user")
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
        
    pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, pw_hash, role))
        record_activity(cursor, user["id"], user["username"], f"Created User: {username}")
        conn.commit()
        return {"status": "success"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Username already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/api/users/{target_id}")
async def delete_user(target_id: int, user = Depends(require_admin)):
    if target_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (target_id,))
    record_activity(cursor, user["id"], user["username"], f"Deleted User ID: {target_id}")
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/users/{target_id}/role")
async def change_user_role(target_id: int, request: Request, user = Depends(require_admin)):
    if target_id == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    data = await request.json()
    role = data.get("role", "user")
    if role not in ["admin", "dept_head", "user", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role, target_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.post("/api/change-password")
async def change_password(request: Request, user = Depends(require_auth)):
    data = await request.json()
    new_password = data.get("new_password")
    if not new_password:
        raise HTTPException(status_code=400, detail="New password required")
        
    pw_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user["id"]))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/activity-log")
async def get_activity_log(user = Depends(require_manager)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username, action, product_name, details, timestamp FROM activity_log ORDER BY id DESC LIMIT 100")
        logs = [{"username": r[0], "action": r[1], "product_name": r[2], "details": r[3], "timestamp": format_sqlite_timestamp(r[4])} for r in cursor.fetchall()]
        return {"status": "success", "logs": logs}
    except Exception as e:
        return {"status": "error", "logs": []}
    finally:
        conn.close()

@app.post("/api/log-activity")
async def log_activity(request: Request, user = Depends(require_auth)):
    data = await request.json()
    action = data.get("action", "unknown")
    template_id = data.get("template_id")
    product_name = data.get("product_name")
    details = data.get("details", "")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO activity_log (user_id, username, action, template_id, product_name, details) VALUES (?, ?, ?, ?, ?, ?)",
                       (user["id"], user["username"], action, template_id, product_name, details))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.get("/api/dashboard-stats")
async def dashboard_stats(user = Depends(require_auth)):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM templates")
        total_templates = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT product_name, updated_at FROM templates ORDER BY updated_at DESC LIMIT 5")
        recent = [{"name": r[0], "date": format_sqlite_timestamp(r[1])} for r in cursor.fetchall()]
        
        return {
            "status": "success",
            "total_templates": total_templates,
            "total_users": total_users,
            "recent_templates": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

if __name__ == "__main__":

    import uvicorn
    import threading
    import webbrowser
    import time
    
    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000")
        
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
