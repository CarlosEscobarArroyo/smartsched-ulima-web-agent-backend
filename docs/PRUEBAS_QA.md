---
title: "Pruebas de Calidad (QA) — SmartSched ULIMA"
lang: es
---

Pruebas de las tres técnicas exigidas (caja blanca, caja negra y unitaria), aplicadas al backend (pytest) y al frontend (Vitest). Son 5 integrantes; cada uno presenta las tres técnicas. En total, 15 pruebas.

**Reparto por integrante**

- Integrante 1 — Backend: `generate_schedules()` (caja blanca), `POST /admin/courses` (caja negra), `TimeBlock.overlaps()` (unitaria).
- Integrante 2 — Frontend: `generateSchedules()` (caja blanca), `createCourseSchema` (caja negra), `timeLabel()` (unitaria).
- Integrante 3 (Carlos) — Backend: `authenticate()` (caja blanca), `POST /admin/professors` (caja negra), `_is_locked()` (unitaria).
- Integrante 4 — Backend: `_merge_courses()` (caja blanca), `OCRCurso` (caja negra), `_parse_horario()` (unitaria).
- Integrante 5 — Frontend: `applyMeridiem()` (caja blanca), `createProfessorSchema` (caja negra), `parseHorario()` (unitaria).

**Cómo ejecutar**

- Backend: `uv run pytest tests/qa/ -v` (72 pruebas en verde).
- Frontend: `npx vitest run src/__tests__/qa` (62 pruebas en verde).

# Backend

## Caja blanca

**`generate_schedules()` — test_caja_blanca_generador.py (Integrante 1)**

Genera combinaciones de horario sin cruces (backtracking). Complejidad ciclomática V(G) = 6 (radon) / 10 (conteo manual). 10 casos:

- `test_target_cero_lanza_valueerror` — target = 0 lanza ValueError.
- `test_target_negativo_lanza_valueerror` — target = -3 lanza ValueError.
- `test_bloqueo_descarta_seccion_y_deja_alternativa` — un bloqueo descarta una sección pero queda otra.
- `test_bloqueo_elimina_todas_las_secciones` — el bloqueo cubre la única sección: sin combinaciones.
- `test_menos_materias_que_target_no_genera` — menos materias que el objetivo: sin combinaciones.
- `test_combinacion_completa_de_dos_materias` — dos materias sin choque: una combinación.
- `test_varias_combinaciones_cuando_hay_multiples_secciones` — varias secciones: varias combinaciones.
- `test_solapamiento_entre_materias_descarta_esa_rama` — A y B chocan: sin combinaciones.
- `test_solapamiento_fuerza_seccion_alternativa` — usa la segunda sección de B.
- `test_poda_por_materias_insuficientes_para_completar` — la poda temprana corta: vacío.

**`authenticate()` — test_caja_blanca_authenticate.py (Integrante 3, Carlos)**

Login con bloqueo tras 3 intentos fallidos. Complejidad ciclomática V(G) = 6. 7 casos:

- `test_login_valido_devuelve_token` — credenciales válidas: devuelve token.
- `test_login_valido_resetea_contador_de_fallos` — login válido con fallos previos: resetea el contador.
- `test_usuario_inexistente_devuelve_401` — usuario inexistente: 401.
- `test_usuario_inactivo_devuelve_401` — usuario inactivo: 401.
- `test_password_incorrecto_incrementa_y_devuelve_401` — contraseña incorrecta: 401 e incrementa el contador.
- `test_tres_intentos_fallidos_bloquean_con_423` — al tercer fallo: 423 (bloquea la cuenta).
- `test_cuenta_bloqueada_rechaza_incluso_con_password_correcto` — cuenta bloqueada: 423 aun con la contraseña correcta.

**`_merge_courses()` — test_caja_blanca_merge_courses.py (Integrante 4)**

Agrupa cursos repetidos que el OCR a veces emite por sección. Complejidad ciclomática V(G) = 7 (radon) / 6 (manual). 6 casos:

- `test_lista_vacia_devuelve_vacio` — lista vacía: devuelve vacío.
- `test_cursos_distintos_se_conservan` — cursos con claves distintas: se conservan por separado.
- `test_curso_repetido_junta_secciones` — mismo código: junta sus secciones.
- `test_seccion_duplicada_no_se_repite` — sección duplicada: no se repite.
- `test_codigo_vacio_usa_el_nombre_como_clave` — código vacío: usa el nombre como clave.
- `test_clave_es_insensible_a_mayusculas` — "cs101" y "CS101" son el mismo curso.

## Caja negra

**`POST /admin/courses` — test_caja_negra_crear_curso.py (Integrante 1)**

Crear un curso (admin). 5 campos de entrada: code, name, level, prerequisites, professor_id. 9 casos:

- `test_crear_curso_valido_devuelve_201` — todos los campos válidos: 201.
- `test_opcionales_omitidos_devuelve_201` — opcionales omitidos: 201.
- `test_sin_token_devuelve_401` — sin token: 401.
- `test_rol_estudiante_devuelve_403` — rol estudiante: 403.
- `test_code_valores_limite` — code: "" da 422, 20 caracteres da 201, 21 caracteres da 422.
- `test_name_valores_limite` — name: "" da 422, 120 caracteres da 201.
- `test_level_vacio_devuelve_422` — level vacío: 422.
- `test_falta_campo_obligatorio_devuelve_422` — falta name: 422.
- `test_code_duplicado_ignora_mayusculas_devuelve_409` — "cs101" y luego "CS101": 409.

**`POST /admin/professors` — test_caja_negra_crear_profesor.py (Integrante 3, Carlos)**

Crear un profesor (admin). 5 campos de entrada: name, department, degree, bio, email. 8 casos:

- `test_crear_profesor_valido_devuelve_201` — todos los campos válidos: 201.
- `test_solo_name_opcionales_omitidos_devuelve_201` — solo name: 201, opcionales en null.
- `test_sin_token_devuelve_401` — sin token: 401.
- `test_rol_estudiante_devuelve_403` — rol estudiante: 403.
- `test_name_valores_limite` — name: 1 carácter da 422, 2 da 201, 120 da 201, 121 da 422.
- `test_falta_name_devuelve_422` — falta name: 422.
- `test_department_valores_limite` — department: 120 caracteres da 201, 121 da 422.
- `test_email_excede_limite_devuelve_422` — email de 121 caracteres: 422.

**`OCRCurso` — test_caja_negra_ocr_curso.py (Integrante 4)**

Contrato de salida del OCR: valida cada curso detectado. 5 campos de entrada: codigo, nombre, creditos, nivel, secciones. 8 casos:

- `test_curso_valido_completo` — curso válido completo: válido.
- `test_solo_nombre_aplica_valores_por_defecto` — solo nombre: aplica valores por defecto.
- `test_falta_nombre_es_invalido` — falta nombre: inválido.
- `test_creditos_numerico_en_texto_se_convierte` — creditos "3.5": se convierte a 3.5.
- `test_creditos_no_numerico_es_invalido` — creditos "cuatro": inválido.
- `test_nivel_entero_en_texto_se_convierte` — nivel "5": se convierte a 5.
- `test_nivel_no_entero_es_invalido` — nivel "quinto": inválido.
- `test_secciones_no_es_lista_es_invalido` — secciones que no es una lista: inválido.

## Unitaria

**`TimeBlock.overlaps()` — test_unitaria_solapamiento.py (Integrante 1)**

Decide si dos bloques de horario se cruzan. 6 casos:

- `test_solapamiento_parcial_mismo_dia` — mismo día, solapamiento parcial: True.
- `test_bloques_que_se_tocan_en_el_borde_no_solapan` — se tocan en el borde (10:00): False.
- `test_un_bloque_contiene_al_otro` — un bloque contiene al otro: True.
- `test_bloques_disjuntos_mismo_dia` — mismo día, disjuntos: False.
- `test_mismo_horario_distinto_dia_no_solapa` — mismo horario, distinto día: False.
- `test_bloques_identicos_solapan` — bloques idénticos: True.

**`_is_locked()` — test_unitaria_is_locked.py (Integrante 3, Carlos)**

Decide si una cuenta tiene un bloqueo vigente ahora. 5 casos:

- `test_sin_locked_until_no_esta_bloqueado` — sin bloqueo (None): False.
- `test_locked_until_futuro_esta_bloqueado` — bloqueo en el futuro: True.
- `test_locked_until_pasado_no_esta_bloqueado` — bloqueo en el pasado: False.
- `test_locked_until_naive_futuro_se_asume_utc` — fecha sin zona en el futuro: True.
- `test_locked_until_naive_pasado_se_asume_utc` — fecha sin zona en el pasado: False.

**`_parse_horario()` — test_unitaria_parse_horario.py (Integrante 4)**

Convierte un texto como "MIE 11:00-13:00" en un bloque de horario, o None. 6 casos:

- `test_horario_valido_devuelve_timeblock` — "MIE 11:00-13:00": bloque correcto.
- `test_horario_minusculas_con_aula` — "lun 08:00-10:00 Aula 850": se normaliza.
- `test_dia_invalido_devuelve_none` — día desconocido: None.
- `test_formato_irreconocible_devuelve_none` — texto sin formato: None.
- `test_hora_fuera_de_rango_devuelve_none` — "MAR 25:00-26:00": None.
- `test_inicio_mayor_o_igual_que_fin_devuelve_none` — inicio mayor o igual que fin: None.

# Frontend

En Vitest, el nombre de cada test es el texto de su `it(...)`.

## Caja blanca

**`generateSchedules()` — caja-blanca.generateSchedules.test.ts (Integrante 2)**

Envía los cursos al backend y adapta la respuesta. El `fetch` se reemplaza por un mock (`vi.fn()`, equivalente a Mockito). Complejidad ciclomática V(G) = 7. 7 casos:

- "D1: sin cursos seleccionados devuelve error y NO llama al backend".
- "D2: curso seleccionado sin secciones devuelve error y NO llama al backend".
- "D3: si el backend no responde (fetch rechaza) devuelve error de conexión".
- "D4/D5: respuesta no-OK con detail usa ese mensaje".
- "D4: respuesta no-OK sin cuerpo JSON cae al mensaje por defecto".
- "D6: respuesta OK con options=[] informa que no hay combinaciones".
- "éxito: mapea el horario del curso a los horarios de la sección elegida".

**`applyMeridiem()` — caja-blanca.applyMeridiem.test.ts (Integrante 5)**

Cambia una hora entre AM y PM y la mantiene dentro del rango. Complejidad ciclomática V(G) = 7. 6 casos:

- "D1: a AM con hora >= 12 resta 12 horas" (18:00 a 06:00).
- "D1/D2 falsos: a AM con hora < 12 no cambia" (09:15).
- "D2: a PM con hora < 12 suma 12 horas" (05:30 a 17:30).
- "D2 falso: a PM con hora >= 12 no cambia" (20:45).
- "D3: clamp inferior — una hora < 6 se sube a 06" (03:20 a 06:20).
- "D4: clamp superior — una hora > 23 se baja a 23" (30:10 a 23:10).

## Caja negra

**`createCourseSchema` — caja-negra.courseForm.test.ts (Integrante 2)**

Validación del formulario de curso (Zod). 5 campos de entrada: code, name, level, prerequisites, professor_id. 6 casos:

- "acepta un curso con todos los campos válidos".
- "acepta omitir los campos opcionales (prerequisites/professor_id)".
- "code=... válido=..." (9 variantes): AB12, ABCD1234, CS101 válidos; cs101, A1, CSABC, ABCDE12, CS12345 y "" inválidos.
- "name de ... caracteres válido=..." (4 variantes): 1 y 120 válidos; "" y 121 inválidos.
- "level=... válido=..." (5 variantes): 1 y 12 válidos; 123, abc y "" inválidos.
- "reporta un error por cada campo inválido".

**`createProfessorSchema` — caja-negra.professorForm.test.ts (Integrante 5)**

Validación del formulario de profesor (Zod). 5 campos de entrada: name, department, degree, bio, email. 6 casos:

- "acepta un profesor con todos los campos válidos".
- "acepta omitir los 4 campos opcionales (quedan en null)".
- "name=... válido=..." (5 variantes): 1 carácter inválido; 2 y 120 válidos; 121 y "" inválidos.
- "... de ... caracteres válido=..." (opcionales): department 120/121, degree 200/201, bio 1000/1001, email 120/121.
- "normaliza un opcional con solo espacios a null".
- "recorta los espacios de un opcional con contenido".

## Unitaria

**`timeLabel()` — unitaria.timeLabel.test.ts (Integrante 2)**

Convierte una hora de 24h a 12h con AM/PM. 6 casos:

- "convierte 00:00 en '12:00 AM'".
- "convierte 12:00 en '12:00 PM'".
- "convierte 07:30 en '7:30 AM'".
- "convierte 13:00 en '1:00 PM'".
- "convierte 23:45 en '11:45 PM'".
- "rellena los minutos a dos dígitos: 11:05 → '11:05 AM'".

**`parseHorario()` — unitaria.parseHorario.test.ts (Integrante 5)**

Convierte un texto de horario en un bloque, o None. 5 casos:

- "parsea 'MIE 11:00-13:00 Aula 850014'".
- "parsea 'LUN 07:00-09:00' sin aula (aula vacía)".
- "devuelve null ante un formato irreconocible".
- "normaliza el día en minúsculas y rellena la hora a dos dígitos".
- "recorta un nombre de día largo a su código de 3 letras".
