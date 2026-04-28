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
