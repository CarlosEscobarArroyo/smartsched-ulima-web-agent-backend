# Capas vs. Dominios, explicado desde cero

Ambas son formas de **organizar carpetas** en tu proyecto. El código que escribes es casi el mismo, lo único que cambia es **dónde vive cada archivo**. Te lo explico con tu propio proyecto.

---

## Imaginemos que Smartsched tiene 3 features

Para que se note la diferencia, supongamos que ya tienes:

1. **chat** — hablar con el agente (ya lo tienes)
2. **users** — registro/login de alumnos
3. **schedules** — horarios de clases

Cada feature necesita típicamente 5 archivos:
- **router** → los endpoints HTTP (`POST /chat`, `GET /users/{id}`...)
- **schema** → los modelos Pydantic de request/response
- **service** → la lógica de negocio
- **model** → la tabla en la base de datos (SQLAlchemy)
- **repository** → las consultas SQL

Son 3 features × 5 archivos = **15 archivos**. La pregunta es: ¿cómo los acomodo en carpetas?

---

## Opción A: Por CAPAS

Agrupas los archivos **por su tipo técnico**. Todos los routers juntos, todos los schemas juntos, etc.

```
app/
├── api/v1/routers/
│   ├── chat.py          ← endpoints de chat
│   ├── users.py         ← endpoints de users
│   └── schedules.py     ← endpoints de schedules
├── schemas/
│   ├── chat.py          ← Pydantic de chat
│   ├── users.py         ← Pydantic de users
│   └── schedules.py     ← Pydantic de schedules
├── services/
│   ├── chat.py          ← lógica de chat
│   ├── users.py         ← lógica de users
│   └── schedules.py     ← lógica de schedules
├── models/
│   ├── user.py          ← tabla users
│   └── schedule.py      ← tabla schedules
└── repositories/
    ├── users.py
    └── schedules.py
```

**Cómo se siente trabajar así:** si te piden "agrega un campo `email` al endpoint de users", tienes que abrir:
- `api/v1/routers/users.py`
- `schemas/users.py`
- `services/users.py`
- `models/user.py`
- `repositories/users.py`

Cinco archivos en cinco carpetas distintas. **Saltas mucho entre carpetas para tocar una sola feature.**

---

## Opción B: Por DOMINIOS (lo que recomienda la comunidad 2025–2026)

Agrupas los archivos **por feature**. Cada feature es una carpeta autocontenida con TODOS sus archivos adentro.

```
app/
├── chat/
│   ├── router.py        ← endpoints de chat
│   ├── schemas.py       ← Pydantic de chat
│   ├── service.py       ← lógica de chat
│   ├── models.py        ← (chat aún no tiene tabla)
│   └── repository.py
├── users/
│   ├── router.py        ← endpoints de users
│   ├── schemas.py       ← Pydantic de users
│   ├── service.py       ← lógica de users
│   ├── models.py        ← tabla users
│   └── repository.py
└── schedules/
    ├── router.py
    ├── schemas.py
    ├── service.py
    ├── models.py
    └── repository.py
```

**Cómo se siente trabajar así:** misma tarea (agregar `email` a users) → abres **una sola carpeta** (`app/users/`) y ahí está todo. Si mañana decides borrar la feature `schedules`, **borras una carpeta y listo**, no andas cazando archivos sueltos.

---

## La analogía del clóset 

- **Por capas** = ordenar el clóset por tipo de ropa: todas las camisas juntas, todos los pantalones juntos, todas las medias juntas. Cuando quieres armar **un outfit**, tienes que abrir 4 cajones distintos.
- **Por dominios** = ordenar el clóset por outfits completos: en cada percha está la camisa + pantalón + corbata de un look. Para vestirte agarras **una sola percha**.

Para 3 prendas (proyecto chico), da igual. Para 50 prendas (proyecto grande), por capas se vuelve un infierno.

---

## ¿Cuándo conviene cada uno?

| | Por capas | Por dominios |
|---|---|---|
| Proyecto con 1–2 features | Bien | Bien |
| Proyecto con 5+ features | Empieza a doler | Mucho más fácil |
| Borrar una feature entera | Tienes que cazar archivos | Borras una carpeta |
| Onboarding de un dev nuevo | Tiene que entender toda la estructura | "Trabaja en `app/users/`" |
| Lo que enseñan los tutoriales básicos | Sí (es más obvio al principio) | No (parece raro al principio) |

---

## Tu situación

Hoy tienes **1 feature real** (chat) y planeas tener varias más (users, schedules, courses, enrollments…). Tu README ya promete el patrón **por capas**:

> *"routers/<x>.py → services/<x>.py → repositories/<x>.py → models/<x>.py + schemas/<x>.py"*

Eso es **Opción A**. Funciona, pero la comunidad ha visto que con 8–10 features se vuelve incómodo. Por eso la recomendación 2025–2026 es **Opción B (dominios)** desde el inicio: cuesta lo mismo ahora y te ahorra refactor después.

**Sugerencia:**
- Si quieres lo más simple posible y vas a tener pocas features → quédate con capas (lo que ya tienes).
- Si Smartsched va a crecer (varios módulos: chat, alumnos, horarios, cursos, matrículas…) → pásate a dominios **ahora** que solo tienes 1 feature, antes de que duela mover.

---

# Arquitectura de una Web App

## El modelo mental: Frontend ↔ Backend

Una web app tiene dos "mitades" que viven en máquinas distintas y se hablan por la red usando el protocolo **HTTP**:

```
┌─────────────────────┐         Internet / Red         ┌─────────────────────┐
│      FRONTEND       │  ──────── HTTP Request ───────► │      BACKEND        │
│  (navegador / app)  │                                  │  (servidor / API)   │
│                     │  ◄─────── HTTP Response ───────  │                     │
└─────────────────────┘                                  └─────────────────────┘
```

El **frontend** es lo que el usuario ve (React, HTML, una app móvil…). El **backend** es el servidor que guarda datos, aplica reglas de negocio y responde preguntas. Ellos nunca se tocan directamente: todo pasa por mensajes HTTP.

Cada conversación es siempre la misma secuencia:
1. El frontend envía un **Request** (pedido).
2. El backend procesa y devuelve un **Response** (respuesta).
3. El frontend muestra el resultado al usuario.

---

## Anatomía de un Request

Un request tiene cuatro partes clave:

### 1. Method (Método)
Le dice al servidor **qué tipo de acción** quiere el cliente. Los más usados:

| Método | Significado semántico | Ejemplo en Smartsched |
|--------|----------------------|-----------------------|
| `GET` | Leer/obtener algo | Traer el horario de un alumno |
| `POST` | Crear algo nuevo | Enviar un mensaje al chat |
| `PUT` | Reemplazar algo completo | Actualizar todo el perfil |
| `PATCH` | Actualizar una parte | Cambiar solo el correo |
| `DELETE` | Borrar algo | Eliminar una sesión |

### 2. Path (Ruta)
La **dirección** del recurso dentro del servidor. Va después del dominio:

```
https://api.smartsched.com/schedules/2024-1/CS101
                           ↑
                        el path
```

En FastAPI defines estos paths con los decoradores `@app.get("/path")`, `@app.post("/path")`, etc.

### 3. Headers (Cabeceras del request)
Metadatos que viajan junto al pedido, sin ser el contenido principal. Los más comunes:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...   ← token de autenticación
Content-Type: application/json                    ← formato del body
Accept: application/json                          ← qué formato espera la respuesta
```

### 4. Body (Cuerpo)
El **contenido** del pedido, solo presente cuando se envía datos (`POST`, `PUT`, `PATCH`). En APIs modernas casi siempre es JSON:

```json
{
  "message": "¿Qué cursos tengo disponibles este ciclo?",
  "session_id": "abc-123"
}
```

Los `GET` y `DELETE` normalmente **no tienen body** — si necesitan filtros los pasan en la URL como query params: `/schedules?ciclo=2024-1&alumno=20190234`.

---

## Anatomía de un Response

El servidor siempre responde con tres partes:

### 1. Status Code (Código de estado)
Un número de 3 dígitos que le dice al frontend **si la operación salió bien o mal**, y por qué. Están agrupados por centenas:

| Rango | Significado | Ejemplos frecuentes |
|-------|-------------|---------------------|
| `2xx` | Éxito | `200 OK`, `201 Created`, `204 No Content` |
| `3xx` | Redirección | `301 Moved Permanently`, `304 Not Modified` |
| `4xx` | Error del cliente | `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`, `422 Unprocessable Entity` |
| `5xx` | Error del servidor | `500 Internal Server Error`, `503 Service Unavailable` |

El frontend **siempre debe revisar el status code** antes de leer el body. Un `200` con un body de error es un anti-patrón que causa bugs difíciles de debuggear.

### 2. Headers (Cabeceras del response)
Metadatos que el servidor adjunta a la respuesta:

```
Content-Type: application/json        ← formato del body
Content-Length: 342                   ← tamaño en bytes
Cache-Control: no-store               ← instrucciones de caché
Set-Cookie: session=abc; HttpOnly     ← cookies
```

### 3. Body (Cuerpo)
El **contenido** de la respuesta. Puede ser JSON, HTML, texto plano, una imagen, un PDF…

```json
{
  "reply": "Tienes 4 cursos disponibles: Cálculo I, Física II...",
  "session_id": "abc-123",
  "tokens_used": 312
}
```

---

## El ciclo completo en Smartsched

```
Usuario escribe "¿Qué cursos tengo?" en el chat
        │
        ▼
Frontend (React/etc.)
  construye el request:
    Method: POST
    Path:   /chat/message
    Header: Authorization: Bearer <token>
    Body:   { "message": "¿Qué cursos tengo?" }
        │
        ▼  ──────── viaja por Internet ────────
        │
        ▼
Backend (FastAPI)
  1. Recibe el request en el router de chat
  2. Valida el token (middleware de auth)
  3. Llama al servicio de chat
  4. El servicio llama al agente de IA
  5. Construye la respuesta
        │
        ▼  ──────── viaja por Internet ────────
        │
        ▼
Frontend recibe el response:
    Status: 200 OK
    Body:   { "reply": "Tienes 4 cursos..." }
        │
        ▼
Muestra la respuesta en pantalla
```

---

## Regla de oro

El backend **no sabe** si al otro lado hay un navegador, una app móvil, Postman, o un script de Python. Solo sabe que alguien mandó un HTTP request con cierto method, path y body. Por eso una buena API puede servir a múltiples frontends a la vez sin cambiar nada del servidor.

---

## Ejemplo real: subir una imagen y leerla con OCR

### ¿Qué método se usa?

**`POST`** — y sí, también devuelve datos, igual que un `GET`. La confusión más común es pensar que `POST` solo envía y `GET` solo recibe. No es así: **todos los métodos siempre devuelven un response con status code y body**. La diferencia está en lo que *tú mandas*, no en lo que recibes:

| | ¿Mandas body? | ¿Recibes body? |
|---|---|---|
| `GET` | No | Sí |
| `POST` | Sí | Sí |
| `DELETE` | No | Sí (generalmente vacío) |

Usas `POST` en vez de `GET` únicamente porque necesitas mandar el archivo primero. Un `GET` no tiene body, no hay forma de adjuntar una imagen. Piénsalo así:

- `GET` → "dame lo que ya tienes guardado"
- `POST` → "toma esto, procésalo, y dime el resultado"

En ambos casos el servidor te responde con datos.

### El request

El body ya no es JSON — es `multipart/form-data`, el formato estándar para subir archivos:

```
POST /ocr/extract
Content-Type: multipart/form-data; boundary=----FormBoundaryXyZ

------FormBoundaryXyZ
Content-Disposition: form-data; name="file"; filename="horario_ulima.png"
Content-Type: image/png

<bytes binarios de la imagen>
------FormBoundaryXyZ--
```

Lo que cambia respecto a un request normal:
- El `Content-Type` no es `application/json` sino `multipart/form-data`
- El body no es texto legible, son los bytes crudos de la imagen
- El navegador/frontend arma este formato automáticamente cuando usas un `<input type="file">`

### Lo que ocurre dentro del backend

```
Frontend sube horario_ulima.png
        │
        ▼
POST /ocr/extract
        │
        ▼
Router recibe el archivo (FastAPI lo expone como UploadFile)
        │
        ▼
Service envía los bytes al servicio OCR (Google Vision, Tesseract, etc.)
        │
        ▼
OCR devuelve el texto crudo extraído de la imagen
        │
        ▼
Service parsea el texto → estructura JSON con cursos, horarios, aulas
        │
        ▼
200 OK + JSON estructurado
```

### El response

```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "cursos": [
    {
      "codigo": "1419",
      "nombre": "COMUNICACIÓN DE DATOS",
      "creditos": 3.0,
      "nivel": 5,
      "secciones": [
        {
          "seccion": "523",
          "profesor": "TORRES PAREDES CARLOS MARTIN",
          "vacantes": 0,
          "horario": [
            { "dia": "MIE", "inicio": "11:00", "fin": "13:00", "aula": "850014" },
            { "dia": "VIE", "inicio": "11:00", "fin": "13:00", "aula": "850014" }
          ]
        }
      ]
    }
  ]
}
```

El frontend recibió bytes de imagen → el backend devuelve JSON estructurado. Esa transformación es el trabajo del backend.

### ¿Y si el archivo es inválido o no es una imagen?

El backend responde con un código `4xx`, nunca con `200`:

| Situación | Status code |
|-----------|-------------|
| No se mandó ningún archivo | `400 Bad Request` |
| El archivo no es una imagen | `422 Unprocessable Entity` |
| El OCR no pudo leer nada | `200` con `{ "cursos": [] }` (operación exitosa, resultado vacío) |
| El servicio OCR externo falló | `502 Bad Gateway` |

El `200` con lista vacía es intencional: la operación funcionó, simplemente no había cursos legibles. No es un error del cliente ni del servidor.
