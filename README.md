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

## Enlaces

| | |
|---|---|
| Servicio desplegado | https://policy-service-slra.onrender.com |
| Estado (health check) | https://policy-service-slra.onrender.com/health |
| Documentación de la API (Swagger) | https://policy-service-slra.onrender.com/api/docs |
| Esquema OpenAPI | https://policy-service-slra.onrender.com/api/schema |
| Métricas Prometheus | https://policy-service-slra.onrender.com/metrics |
| Sitio y API Gateway | https://insureflow-gateway-kxhm.onrender.com |

## Pruebas y cobertura

Las pruebas exigidas están en `tests/`:

- `tests/test_unitarias.py`: **2 pruebas unitarias** que verifican una regla de negocio aislada, con *mocks* para la base de datos, otros microservicios, la pasarela o el bus de eventos.
- `tests/test_integracion.py`: **1 prueba de integración** que recorre endpoint, lógica de negocio y base de datos.
- Las pruebas adicionales de la aplicación están en `<app>/tests.py`.

Para ejecutarlas (sin PostgreSQL ni Redis):

```bash
pip install -r requirements.txt coverage
USE_SQLITE=1 CELERY_EAGER=1 coverage run manage.py test -v 2
coverage report        # porcentaje de cobertura
coverage html          # reporte navegable en htmlcov/
```

En GitHub Actions (`.github/workflows/ci.yml`) el reporte de cobertura se publica en el resumen de la ejecución y como artefacto `reporte-cobertura`.

## CI/CD

| Archivo | Función |
|---|---|
| `.github/workflows/ci.yml` | En cada push y pull request: lint (flake8), pruebas unitarias y de integración con cobertura, auditoría de dependencias (pip-audit) e imagen Docker. Si algo falla, no se despliega. |
| `.github/workflows/deploy.yml` | Solo cuando CI termina con éxito en `main`: llama al Deploy Hook de Render (secreto `RENDER_DEPLOY_HOOK_URL`) y espera a que `/health` responda. |
| `.github/workflows/codeql.yml` | Análisis estático de seguridad. |

**Estrategia de ramas (GitFlow):**

- `main`: producción.
- `develop`: integración.
- `feature/*`: funcionalidades nuevas.
- `hotfix/*`: correcciones urgentes.

Los cambios entran por *pull request* con el pipeline en verde.

## Base de datos

- **Esquema:** migraciones de Django en `<app>/migrations/`, que se aplican solas al arrancar el contenedor (`start.sh`).
- **Datos de ejemplo:** `datos/datos_ejemplo.json`. Para cargarlos: `python manage.py loaddata datos/datos_ejemplo.json`.
- **Respaldo:** `datos/respaldo.sql` (volcado de PostgreSQL con `pg_dump`).
- **Variables de entorno:** ver `.env.example`. No se suben credenciales al repositorio.
