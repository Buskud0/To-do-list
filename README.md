# 📝 Todo programa – Universiteto projektas

## Projekto struktūra

```
todo-app/
├── backend/
│   ├── main.py           ← Visas back-end kodas (FastAPI)
│   └── requirements.txt  ← Python bibliotekos
└── frontend/
    └── index.html        ← Visas front-end kodas (HTML + CSS + JS)
```

---

## Paleidimas

### 1. Back-end (terminalas #1)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Serveris veiks adresu: `http://localhost:8000`  
API dokumentacija: `http://localhost:8000/docs` ← automatinė FastAPI dokumentacija!

### 2. Front-end (terminalas #2 arba tiesiog atidaryti naršyklėje)

Tiesiog atidarykite `frontend/index.html` naršyklėje.

---

## API lentelė

| # | Metodas  | URL               | Aprašas                        | Auth reikia? |
|---|----------|-------------------|--------------------------------|-------------|
| 1 | POST     | /register         | Registracija                   | Ne          |
| 2 | POST     | /login            | Prisijungimas → gauna tokeną   | Ne          |
| 3 | GET      | /todos            | Gauti visas užduotis           | Taip        |
| 4 | GET      | /todos?done=true  | Gauti tik atliktas             | Taip        |
| 5 | POST     | /todos            | Sukurti užduotį                | Taip        |
| 6 | PATCH    | /todos/{id}       | Atnaujinti užduotį             | Taip        |
| 7 | DELETE   | /todos/{id}       | Ištrinti užduotį               | Taip        |
| 8 | POST     | /logout           | Atsijungimas                   | Taip        |

## HTTP parametrų lentelė (reikalavimams)

| Tipas   | Pavadinimas   | Kur naudojamas        |
|---------|---------------|-----------------------|
| Header  | Authorization | Visuose apsaugotuose endpoint'uose |
| Header  | Content-Type  | POST ir PATCH užklausose |
| Path    | {todo_id}     | PATCH /todos/{id}, DELETE /todos/{id} |
| Query   | ?done=        | GET /todos?done=true/false |

## Reikalavimai (checkList)

- ✅ 5+ API metodai (mūsų yra 8)
- ✅ 2+ HTTP metodai: POST, PATCH, DELETE, GET
- ✅ 3+ parametrų tipai: Header, Path, Query
- ✅ FE: kiekvienas metodas iškviečiamas per UI
- ✅ BE: duomenys saugomi SQLite duomenų bazėje
- ✅ BE: autorizacija (Bearer token)
- ✅ BE: užklausų validavimas (Pydantic + rankinis)
- ✅ FE: Responsive Design (3 breakpointai: PC, planšetė, telefonas)
