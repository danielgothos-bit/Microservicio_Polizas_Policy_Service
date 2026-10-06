# Microservicio de Pólizas — Policy Service

Microservicio de InsureFlow definido en la sección 4.1 del documento de arquitectura.

## Responsabilidad

Emitir, renovar y cancelar pólizas (auto, hogar, vida) con sus coberturas, primas y beneficiarios.

## Tecnología

Python · Django REST Framework · PostgreSQL (`policy_db`) · Celery + Redis · Docker

## Modelo de datos (3FN, IDs UUID)

`poliza` (coverage JSONB, status, vigencia) y `beneficiario` (porcentaje 0–100, suma ≤ 100).

## Endpoints

```
POST /api/v1/polizas — emitir póliza (valida al asegurado con Policyholder)
GET  /api/v1/polizas — listar (filtro ?status=)
GET  /api/v1/polizas/{id} — consultar póliza y cobertura vigente
GET  /api/v1/polizas/{id}/cobertura?fecha=AAAA-MM-DD — cobertura en una fecha (la usa Siniestros)
PUT  /api/v1/polizas/{id}/renovar — renovar póliza
POST /api/v1/polizas/{id}/cancelar — cancelar póliza
GET  /api/v1/polizas/asegurado/{id} — historial de pólizas de un asegurado
GET  /health — estado del servicio y de su base de datos
POST /api/v1/eventos — endpoint interno donde otros microservicios entregan eventos
```

## Eventos

Publica:
- policy.issued
- policy.renewed
- policy.cancelled

Consume:
- (ninguno)

Los eventos se encolan con Celery/Redis y se entregan por HTTP al endpoint `/api/v1/eventos` de cada
suscriptor, con reintentos y backoff exponencial (módulo `comun/eventos.py`). Cada evento se procesa una
sola vez (idempotencia por `event_id`).

## Variables de entorno

- `DATABASE_URL`, `REDIS_URL`: base de datos y Redis propios
- `INTERNAL_TOKEN`: token compartido por todos los microservicios para los eventos
- `RUN_WORKER_IN_WEB=1`: corre el worker de Celery dentro del mismo contenedor (Render gratis)
- `SYNC_TIMEOUT`: timeout de las llamadas REST síncronas (3 s por defecto)
- `POLICYHOLDER_SERVICE_URL`: microservicio de Asegurados

Si una URL no está configurada, el servicio funciona en modo aislado (omite esa validación o ese evento).

## Ejecución local

```bash
docker compose up --build
```

El servicio queda en http://localhost:8003 y las migraciones se aplican solas al arrancar.

Pruebas:

```bash
docker compose exec policy_service python manage.py test polizas
```

## Despliegue en Render

En Render: **New → Blueprint** → conectar este repositorio → **Deploy Blueprint**.
El `render.yaml` crea el servicio web, su PostgreSQL y su Redis (plan gratis).
