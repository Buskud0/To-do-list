# ============================================================
# BACK-END: FastAPI Todo programa
# ============================================================
# Paleidimui: pip install -r requirements.txt
#             uvicorn main:app --reload
# ============================================================

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # Statinių failų servingui
from fastapi.responses import FileResponse   # Grąžina HTML failą
from pydantic import BaseModel
from typing import Optional
import sqlite3
import hashlib
import secrets
import time
import os

# ------------------------------------------------------------
# PROGRAMA
# Sukuriame FastAPI programą
# ------------------------------------------------------------
app = FastAPI(title="Todo API")

# CORS leidžia naršyklei kreiptis į šį serverį
# (be šito naršyklė blokuotų užklausas iš kito porto)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Leidžiame visus - studijoms OK, produkcijoje geriau nurodyti tikslų adresą
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------
# STATINIŲ FAILŲ SERVINGAS
# Kai atidaro http://localhost:8000 - grąžina index.html
# frontend/ aplankas turi būti šalia backend/ aplanko
# ------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

@app.get("/")
def root():
    #Grąžina pagrindinį HTML puslapį.
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    return FileResponse(index_path)

# ------------------------------------------------------------
# DUOMENŲ BAZĖ (SQLite - vienas failas, nereikia serverio)
# ------------------------------------------------------------
DB_FILE = "todos.db"

def get_db():
    #Grąžina ryšį su SQLite duomenų baze.
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Leidžia pasiekti stulpelius pagal pavadinimą
    return conn

def init_db():
    #Sukuria lenteles, jei jų dar nėra.
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS todos (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   INTEGER NOT NULL,
            title     TEXT NOT NULL,
            done      INTEGER NOT NULL DEFAULT 0,
            position  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Sesijų lentelė - vietoj JWT naudosime paprastus tokenusu RAM
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token   TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()  # Paleidžiame iš karto kai programa startuoja

# ------------------------------------------------------------
# PAGALBINĖS FUNKCIJOS
# ------------------------------------------------------------

def hash_password(password: str) -> str:
    #Paverčia slaptažodį į hash'ą (SHA-256). Niekada nesaugome plain text.
    return hashlib.sha256(password.encode()).hexdigest()

def create_token(user_id: int) -> str:
    #Sukuria atsitiktinį sesijos tokeną ir išsaugo DB.
    token = secrets.token_hex(32)  # 64 simbolių atsitiktinis tekstas
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, created) VALUES (?, ?, ?)",
        (token, user_id, int(time.time()))
    )
    conn.commit()
    conn.close()
    return token

def get_current_user(authorization: str = Header(...)):
    """
    Autorizacijos middleware funkcija.
    
    Tikrina Authorization header'į - jis turi atrodyti taip:
        Authorization: Bearer <token>
    
    Naudojame Depends() mechanizmą - FastAPI automatiškai
    iškviečia šią funkciją prieš kiekvieną apsaugotą endpoint'ą.
    """
    # Patikriname ar header'is teisingos formos
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Neteisingas Authorization header")
    
    token = authorization.split(" ")[1]  # Paimame tokeną po "Bearer "
    
    conn = get_db()
    row = conn.execute(
        "SELECT user_id FROM sessions WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    
    if row is None:
        raise HTTPException(status_code=401, detail="Neteisinga sesija, prisijunkite iš naujo")
    
    return row["user_id"]

# ------------------------------------------------------------
# MODELIAI (Pydantic) - apibrėžia kokius duomenis priima API
# ------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str   # Vartotojo vardas
    password: str   # Slaptažodis

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateTodoRequest(BaseModel):
    title: str      # Užduoties pavadinimas

class UpdateTodoRequest(BaseModel):
    title: Optional[str] = None   # Galima keisti pavadinimą (nebūtina)
    done: Optional[bool] = None   # Galima keisti statusą (nebūtina)
    position: Optional[int] = None  # Galima keisti poziciją (nebūtina)

# ============================================================
# API ENDPOINT'AI
# ============================================================

# ------------------------------------------------------------
# 1. POST /register - Registracija
# HTTP metodas: POST (siunčiame naujus duomenis)
# Body parametrai: username, password
# ------------------------------------------------------------
@app.post("/register", status_code=201)
def register(body: RegisterRequest):
    #Sukuria naują vartotoją.
    
    # Validavimas - tikriname ar laukai ne tušti
    if len(body.username.strip()) < 3:
        raise HTTPException(status_code=400, detail="Vartotojo vardas per trumpas (min. 3 simboliai)")
    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Slaptažodis per trumpas (min. 4 simboliai)")
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (body.username.strip(), hash_password(body.password))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # UNIQUE constraint nepavyko - toks vardas jau yra
        raise HTTPException(status_code=409, detail="Toks vartotojo vardas jau užimtas")
    finally:
        conn.close()
    
    return {"message": "Registracija sėkminga"}

# ------------------------------------------------------------
# 2. POST /login - Prisijungimas
# HTTP metodas: POST (siunčiame slaptažodį - ne GET, nes GET matomas URL)
# Body parametrai: username, password
# Grąžina: token (kurį FE išsaugos ir siųs kituose request'uose)
# ------------------------------------------------------------
@app.post("/login")
def login(body: LoginRequest):
    #Patikrina vartotoją ir grąžina sesijos tokeną.
    
    conn = get_db()
    user = conn.execute(
        "SELECT id, password FROM users WHERE username = ?",
        (body.username,)
    ).fetchone()
    conn.close()
    
    # Tikriname ar vartotojas egzistuoja ir ar slaptažodis teisingas
    if user is None or user["password"] != hash_password(body.password):
        raise HTTPException(status_code=401, detail="Neteisingas vardas arba slaptažodis")
    
    token = create_token(user["id"])
    return {"token": token, "username": body.username}

# ------------------------------------------------------------
# 3. GET /todos - Gauti visas užduotis
# HTTP metodas: GET (skaitome duomenis)
# Header parametras: Authorization: Bearer <token>
# Query parametras: ?done=true/false (filtravimas - nebūtinas)
# ------------------------------------------------------------

@app.get("/todos")
def get_todos(done: Optional[bool] = None, user_id: int = Depends(get_current_user)):
    conn = get_db()
    
    if done is None:
        rows = conn.execute(
            "SELECT id, title, done, position FROM todos WHERE user_id = ? ORDER BY position ASC",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, done, position FROM todos WHERE user_id = ? AND done = ? ORDER BY position ASC",
            (user_id, 1 if done else 0)
        ).fetchall()
    
    conn.close()
    
    return [{"id": r["id"], "title": r["title"], "done": bool(r["done"]), "position": r["position"]} for r in rows]

# ------------------------------------------------------------
# 4. POST /todos - Sukurti naują užduotį
# HTTP metodas: POST
# Header parametras: Authorization: Bearer <token>
# Body parametrai: title
# ------------------------------------------------------------
@app.post("/todos", status_code=201)
def create_todo(body: CreateTodoRequest, user_id: int = Depends(get_current_user)):
    #Sukuria naują užduotį prisijungusiam vartotojui.
    
    # Validavimas
    if len(body.title.strip()) == 0:
        raise HTTPException(status_code=400, detail="Pavadinimas negali būti tuščias")
    
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO todos (user_id, title, done) VALUES (?, ?, 0)",
        (user_id, body.title.strip())
    )
    conn.commit()
    new_id = cursor.lastrowid  # Gauname naujai sukurto įrašo ID
    conn.close()
    
    return {"id": new_id, "title": body.title.strip(), "done": False}

# ------------------------------------------------------------
# 5. PATCH /todos/{todo_id} - Atnaujinti užduotį
# HTTP metodas: PATCH (dalinis atnaujinimas - ne visas objektas)
# Path parametras: {todo_id} - užduoties ID URL'e
# Header parametras: Authorization: Bearer <token>
# Body parametrai: title (nebūtinas), done (nebūtinas)
# ------------------------------------------------------------
@app.patch("/todos/{todo_id}")
def update_todo(todo_id: int, body: UpdateTodoRequest, user_id: int = Depends(get_current_user)):
    
    #Atnaujina užduoties pavadinimą ir/arba statusą.
    
    #todo_id - path parametras (dalis URL'o): /todos/42
    
    conn = get_db()
    
    # Patikriname ar ši užduotis priklauso šiam vartotojui
    todo = conn.execute(
        "SELECT id FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id)
    ).fetchone()
    
    if todo is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Užduotis nerasta")
    
    # Atnaujiname tik tuos laukus, kurie buvo atsiųsti
    if body.title is not None:
        if len(body.title.strip()) == 0:
            conn.close()
            raise HTTPException(status_code=400, detail="Pavadinimas negali būti tuščias")
        conn.execute("UPDATE todos SET title = ? WHERE id = ?", (body.title.strip(), todo_id))
    
    if body.done is not None:
        conn.execute("UPDATE todos SET done = ? WHERE id = ?", (1 if body.done else 0, todo_id))
    
    conn.commit()
    
    # Grąžiname atnaujintą objektą
    updated = conn.execute(
        "SELECT id, title, done FROM todos WHERE id = ?", (todo_id,)
    ).fetchone()
    conn.close()
    
    return {"id": updated["id"], "title": updated["title"], "done": bool(updated["done"])}

# ------------------------------------------------------------
# 5.1 POST /todos/reorder - Pakeisti užduočių eiliškumą
# HTTP metodas: POST (siunčiame naują eiliškumą)
# Header parametras: Authorization
# Body parametrai: todo_ids (sąrašas užduočių ID nauja tvarka)
# ------------------------------------------------------------

@app.post("/todos/reorder")
def reorder_todos(todo_ids: list[int], user_id: int = Depends(get_current_user)):
    conn = get_db()
    # Atnaujiname kiekvienos užduoties poziciją pagal jos vietą sąraše
    for index, todo_id in enumerate(todo_ids):
        conn.execute(
            "UPDATE todos SET position = ? WHERE id = ? AND user_id = ?",
            (index, todo_id, user_id)
        )
    conn.commit()
    conn.close()
    return {"message": "Eiliškumas atnaujintas"}

# ------------------------------------------------------------
# 6. DELETE /todos/{todo_id} - Ištrinti užduotį
# HTTP metodas: DELETE
# Path parametras: {todo_id}
# Header parametras: Authorization: Bearer <token>
# ------------------------------------------------------------
@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: int, user_id: int = Depends(get_current_user)):
    #Ištrina užduotį pagal ID.
    
    conn = get_db()
    
    # Patikriname ar priklauso šiam vartotojui
    todo = conn.execute(
        "SELECT id FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id)
    ).fetchone()
    
    if todo is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Užduotis nerasta")
    
    conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    conn.commit()
    conn.close()
    
    # 204 No Content - sėkminga ištrynimas, nieko negrąžiname

# ------------------------------------------------------------
# 7. POST /logout - Atsijungimas
# HTTP metodas: POST
# Header parametras: Authorization: Bearer <token>
# ------------------------------------------------------------
@app.post("/logout")
def logout(user_id: int = Depends(get_current_user), authorization: str = Header(...)):
    #Panaikina sesijos tokeną.
    token = authorization.split(" ")[1]
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return {"message": "Sėkmingai atsijungta"}
