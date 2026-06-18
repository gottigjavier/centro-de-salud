
![Versión](https://img.shields.io/badge/versión-0.9.0-blue)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)
![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.3-06B6D4?logo=tailwindcss)
![HTMX](https://img.shields.io/badge/HTMX-2.1-3366FF)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql)
![Licencia](https://img.shields.io/badge/licencia-MIT-success)

# Sistema de Gestión de Turnos — Centro de Salud

Aplicación web para la **gestión de turnos** de un centro de salud. Permite administrar pacientes, profesionales, recursos físicos (consultorios, salas) y la asignación de turnos con una máquina de estados. Incluye dashboard con reportes y gráficos, envío de recordatorios por email y exportación a CSV.

Deploy pensado para **Vercel** (serverless) con **Neon** (PostgreSQL serverless).

---

## Tabla de contenidos

- [Stack tecnológico](#stack-tecnológico)
- [Funcionalidades](#funcionalidades)
- [Secciones de la aplicación](#secciones-de-la-aplicación)
- [Roles de usuario](#roles-de-usuario)
- [Primeros pasos](#primeros-pasos)
  - [Desarrollo local](#desarrollo-local)
  - [Con Docker](#con-docker)
  - [Producción (Vercel + Neon)](#producción-vercel--neon)
- [Variables de entorno](#variables-de-entorno)
- [Tareas programadas](#tareas-programadas)
- [Licencia](#licencia)

---

## Stack tecnológico

### Backend

| Componente         | Tecnología                                                   |
| ------------------ | ------------------------------------------------------------ |
| Framework          | Django 5.2.15                                                |
| Python             | 3.12                                                         |
| Base de datos      | PostgreSQL (Neon serverless en prod) / SQLite (dev)          |
| Autenticación      | django-allauth 65.3.1 (login por email, sin username)        |
| ORM                | Django ORM                                                   |
| Servidor           | Gunicorn (Docker) / WSGI serverless (Vercel)                 |

### Frontend

| Componente    | Tecnología                                                   |
| ------------- | ------------------------------------------------------------ |
| Templates     | Django Templates (DTL)                                       |
| CSS           | Tailwind CSS v4.3.1 (`@tailwindcss/cli` + `@tailwindcss/forms`) |
| Interactividad | HTMX 2.1 (sin JavaScript escrito a mano)                     |
| Gráficos      | Chart.js (CDN en templates de reportes)                      |
| Dark mode     | Soporte completo con persistencia en `localStorage`          |

### Infraestructura

| Componente     | Tecnología                                                   |
| -------------- | ------------------------------------------------------------ |
| Contenedor     | Docker multi-stage (`python:3.12-slim-bookworm`)             |
| Orquestación   | docker-compose (PostgreSQL + Django)                         |
| Deploy         | Vercel (serverless functions vía `api/index.py`)             |
| Base de datos  | Neon (PostgreSQL serverless, pooled connections)             |
| Static files   | Whitenoise (`CompressedManifestStaticFilesStorage`)          |
| Logging        | JSON estructurado en producción                              |

---

## Funcionalidades

1. **Autenticación con email** — Sin username, registro público deshabilitado.
2. **Wizard de setup inicial** — Crea el primer administrador si no existe ningún usuario.
3. **Tres roles** con permisos granulares y scoping automático.
4. **CRUD completo de turnos** con selección dinámica vía HTMX (recurso → profesional → horarios disponibles).
5. **Máquina de estados** con 7 estados y transiciones validadas.
6. **Agenda del día** con turnos agrupados por profesional, stats y filtros.
7. **Gestión de profesionales** con especialidades y asignación temporal a recursos.
8. **Gestión de recursos** (consultorios, salas de procedimientos, enfermería, laboratorio) con horarios semanales y capacidad diaria.
9. **Días no laborables** (feriados recurrentes y puntuales).
10. **Dashboard de reportes** con 6 widgets y gráficos Chart.js.
11. **Exportación CSV** de todos los reportes.
12. **Notificaciones por email** — Confirmación automática al crear el turno + recordatorio programado.
13. **Log de notificaciones** con auditoría completa (estado, errores, timestamp).
14. **Soft-delete** de turnos expirados vía management command.
15. **Dark mode** completo con persistencia en `localStorage`.
16. **Responsive** con Tailwind CSS.
17. **Deploy en Vercel** serverless + Neon PostgreSQL.

---

## Secciones de la aplicación

### Turnos (`/`)

El núcleo del sistema. Permite:

- **Calendario** (`/`) — Vista mensual con turnos.
- **Listado** (`/lista/`) — Turnos paginados con filtros.
- **Crear turno** (`/crear/`) — Formulario con selects dinámicos HTMX: seleccionás recurso → se cargan profesionales → se cargan horarios disponibles.
- **Detalle** (`/<pk>/`) — Info completa del turno, historial de cambios, botones de transición de estado.
- **Editar** (`/<pk>/editar/`) — Modificar datos del paciente.
- **Cancelar** (`/<pk>/cancelar/`) — Con motivo obligatorio.
- **Agenda del día** (`/agenda/`) — Turnos del día agrupados por profesional, con stats en tiempo real y actualización vía HTMX.

**Estados de un turno:**

```
SCHEDULED → CONFIRMED → ARRIVED → IN_PROGRESS → COMPLETED
    │                                           
    └──→ CANCELLED (terminal)                   
    └──→ NO_SHOW (terminal, desde SCHEDULED)    
```

### Recursos (`/resources/`)

Gestión de los espacios físicos del centro:

- **Listado** de consultorios, salas de enfermería, procedimientos, laboratorio y otros.
- **Detalle** con horarios semanales asociados.
- **CRUD** de recursos con capacidad diaria y ubicación.
- **Horarios semanales** por recurso (día, hora inicio, hora fin, duración del slot, cupo por slot).
- **Días no laborables** (`/resources/feriados/`) — Feriados recurrentes y puntuales.

### Profesionales (`/professionals/`)

Gestión del personal de salud:

- **Listado** con especialidad, matrícula, estado activo/inactivo.
- **CRUD** de profesionales con 7 especialidades (General, Cardiología, Pediatría, Dermatología, Traumatología, Enfermería, Otra).
- **Asignación a recursos** — Vinculación temporal de un profesional a un consultorio con horarios específicos y fecha de vigencia.

### Reportes (`/reportes/`)

Dashboard con 6 widgets actualizables vía HTMX:

| Widget               | Descripción                                              | Gráfico  |
| -------------------- | -------------------------------------------------------- | -------- |
| Profesionales        | Turnos por profesional desglosados por estado            | Barras   |
| Cancelaciones        | Total, tasa y motivos de cancelación                     | Torta    |
| Recursos             | Ocupación por recurso                                    | Barras   |
| Tendencia            | Evolución diaria o mensual de turnos                     | Línea    |
| Frecuentes           | Top 20 pacientes más frecuentes                          | Tabla    |
| Horas pico           | Distribución de turnos por hora del día                  | Barras   |

Todos los widgets tienen **exportación CSV** individual.

### Usuarios (`/accounts/`)

- **Setup inicial** (`/accounts/setup/`) — Wizard que crea el primer administrador. Solo accesible si no existe ningún admin en el sistema.
- **Perfil** (`/accounts/perfil/`) — Datos del usuario logueado.
- **Gestión de usuarios** (`/accounts/usuarios/`) — CRUD de usuarios del sistema (solo admin).
- **Login / Logout** vía django-allauth.

---

## Roles de usuario

| Acción                                          | admin | secretary | professional |
| ----------------------------------------------- | ----- | --------- | ------------ |
| Setup inicial (primer admin)                    | ✓     | —         | —            |
| CRUD usuarios                                   | ✓     | —         | —            |
| CRUD profesionales                              | ✓     | —         | —            |
| CRUD recursos                                   | ✓     | —         | —            |
| CRUD horarios de recursos                       | ✓     | —         | —            |
| CRUD días no laborables                         | ✓     | —         | —            |
| Ver días no laborables                          | ✓     | ✓         | —            |
| Crear turnos                                    | ✓     | ✓         | —            |
| Editar turnos (datos del paciente)              | ✓     | ✓         | —            |
| Cancelar turnos                                 | ✓     | ✓         | Solo propios |
| Transiciones de estado (confirmar, atender…)    | ✓     | ✓         | Solo propios |
| Ver detalle de turno                            | ✓     | ✓         | Solo propios |
| Listar turnos / Agenda del día                  | ✓     | ✓         | Solo propios |
| Dashboard de reportes                           | ✓     | ✓         | Solo sus datos |
| Exportación CSV                                 | ✓     | ✓         | Solo sus datos |
| Panel admin Django (`/admin/`)                  | ✓¹    | —         | —            |

¹ Solo si el usuario tiene `is_staff=True`.

**Scoping por rol professional**: Cuando un usuario con rol `professional` accede a listados, agenda o reportes, el sistema filtra automáticamente por el perfil `Professional` vinculado a su `User`. Si no tiene un perfil asociado, se muestra un aviso y datos vacíos.

---

## Primeros pasos

### Desarrollo local

```bash
# 1. Clonar el repositorio y crear el entorno virtual
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno (opcional, hay defaults para dev)
cp .env.example .env

# 4. Ejecutar migraciones
python manage.py migrate

# 5. Compilar Tailwind (en otra terminal o en background)
npx tailwindcss -i ./theme/input.css -o ./static/theme/css/tailwind.css --watch

# 6. Iniciar servidor de desarrollo
python manage.py runserver

# 7. Abrir http://localhost:8000/accounts/setup/ para crear el primer admin
```

### Con Docker

```bash
docker compose up -d
# App en http://localhost:8000
# Setup inicial en /accounts/setup/
```

### Producción (Vercel + Neon)

```bash
# 1. Configurar proyecto en Vercel
#    - Framework: Other
#    - Build Command: bash vercel_build.sh
#    - Install Command: pip install -r requirements.txt

# 2. Variables de entorno en Vercel:
#    DJANGO_SECRET_KEY=<secreto>
#    DATABASE_URL=<neon-pooled-connection-string>
#    DJANGO_ALLOWED_HOSTS=<tus-dominios>
#    DJANGO_DEBUG=False

# 3. Conectar Neon (PostgreSQL serverless)
#    Usar pooled connection string (PgBouncer en modo transaction)
#    Ej: postgresql://user:pass@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require

# 4. ¡Deployar!
```

---

## Variables de entorno

| Variable               | Obligatoria | Default                              | Descripción                         |
| ---------------------- | ----------- | ------------------------------------ | ----------------------------------- |
| `DJANGO_SECRET_KEY`    | Sí (prod)   | `insecure-dev-key`         | Secret key de Django                |
| `DJANGO_DEBUG`         | No          | `False`                              | Modo debug (`True` para desarrollo) |
| `DJANGO_ALLOWED_HOSTS` | No          | `localhost,127.0.0.1,centro-de-salud.vercel.app` | Hosts permitidos (CSV) |
| `DATABASE_URL`         | Sí (prod)   | `sqlite:///dev.db`                   | URL de conexión PostgreSQL (Neon)   |
| `SECURE_SSL_REDIRECT`  | No          | `True`                               | Redirigir HTTP a HTTPS              |
| `SECURE_HSTS_SECONDS`  | No          | `31536000`                           | HSTS en segundos                    |
| `EMAIL_HOST`           | Para email  | `""`                                 | Servidor SMTP                       |
| `EMAIL_PORT`           | Para email  | `587`                                | Puerto SMTP                         |
| `EMAIL_HOST_USER`      | Para email  | `""`                                 | Usuario SMTP                        |
| `EMAIL_HOST_PASSWORD`  | Para email  | `""`                                 | Contraseña SMTP                     |
| `EMAIL_USE_TLS`        | No          | `True`                               | TLS para SMTP                       |
| `DEFAULT_FROM_EMAIL`   | No          | `noreply@centrodesalud.com`          | Remitente por defecto               |
| `CLINIC_NAME`          | No          | `Centro de Salud`                    | Nombre del centro (notificaciones)  |
| `CLINIC_ADDRESS`       | No          | `""`                                 | Dirección del centro                |

---

## Tareas programadas

Se ejecutan via cron del sistema. Ver [`docs/cron-setup.md`](docs/cron-setup.md) para la configuración.

```bash
# Enviar recordatorios de turnos — todos los días a las 9:00
0 9 * * * /ruta/al/venv/bin/python manage.py send_reminders >> /var/log/send_reminders.log 2>&1

# Limpiar turnos expirados — todos los días a las 23:59
59 23 * * * /ruta/al/venv/bin/python manage.py cleanup_expired_appointments >> /var/log/cleanup_expired.log 2>&1
```

---

## Licencia

Distribuido bajo licencia MIT. Ver [LICENSE](LICENSE).
