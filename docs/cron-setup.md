# Configuración de Cron — FASE 3D

## Management Commands

### 1. `send_reminders`

Envía recordatorios por email **a las 9:00 AM del día previo al turno**.

```bash
# Diario a las 9:00 AM
0 9 * * * /path/to/venv/bin/python /path/to/manage.py send_reminders
```

Flags:
- `--dry-run`: simula sin enviar
- `--force`: reenvía incluso si ya fue enviado

### 2. `cleanup_expired_appointments`

Elimina (soft-delete) turnos expirados no finalizados.

```bash
# Diario a las 23:59
59 23 * * * /path/to/venv/bin/python /path/to/manage.py cleanup_expired_appointments
```

Flags:
- `--dry-run`: muestra qué se eliminaría sin hacerlo

## Ejemplo crontab

```bash
# Recordatorios diario a las 9:00 AM
0 9 * * * /home/javier/programacion/health-todo/centro-salud/proyecto/.venv/bin/python /home/javier/programacion/health-todo/centro-salud/proyecto/manage.py send_reminders >> /var/log/send_reminders.log 2>&1

# Limpieza diaria a las 23:59
59 23 * * * /home/javier/programacion/health-todo/centro-salud/proyecto/.venv/bin/python /home/javier/programacion/health-todo/centro-salud/proyecto/manage.py cleanup_expired_appointments >> /var/log/cleanup_expired.log 2>&1
```

## Verificación

```bash
# Probar recordatorios (dry-run primero)
python manage.py send_reminders --dry-run

# Probar limpieza (dry-run primero)
python manage.py cleanup_expired_appointments --dry-run

# Ver logs
tail -f /var/log/send_reminders.log
tail -f /var/log/cleanup_expired.log
```
