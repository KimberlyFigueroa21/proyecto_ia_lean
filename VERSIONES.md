# Lean 4 + Mathlib + Python Verifier
## Documentación del entorno de desarrollo

**Fecha de configuración:** 4 de noviembre de 2026

---

## 1. Versiones instaladas

| Componente | Versión |
|---|---|
| Sistema operativo del contenedor | Ubuntu 24.04 |
| Sistema anfitrión | Windows 11 |
| Lean | 4.36.0-rc2 |
| Commit de Lean | `b35cb10cf2ced51a2fd1880cfdbf75c71ab7a35a` |
| Lake | 5.0.0-src |
| Toolchain | `leanprover/lean4:v4.36.0-rc2` |
| Mathlib | Commit `9d581dfff2e41de989072ea63abf3daf69311520` |

### Archivos de configuración

Se deben conservar estos archivos:

- `lean-toolchain`: fija la versión de Lean.
- `lakefile.toml`: configura las dependencias del proyecto.
- `lake-manifest.json`: registra las versiones exactas de las dependencias.

Las copias de respaldo están en:

```text
proyecto_ia_lean/lean_config/
```

---

## 2. Arquitectura y rutas

### Windows

```text
C:\LeanMathlib\
│
├── Dockerfile
├── compose.yaml
│
├── LeanMathlibProject\
│
└── proyecto_ia_lean\
    ├── smoke_verifier.py
    ├── requirements.txt
    ├── VERSIONES.md
    ├── lean_config\
    └── src\
        ├── __init__.py
        └── verifier_lean.py
```

### Dentro del contenedor

| Elemento | Ruta |
|---|---|
| Proyecto Lean | `/opt/lean/LeanMathlibProject` |
| Proyecto Python | `/workspace/proyecto_ia_lean` |
| Dockerfile | `/workspace/Dockerfile` |
| Configuración Docker | `/workspace/compose.yaml` |

### Volumen persistente

Docker utiliza un volumen llamado:

`lean-data`

Está montado en:

`/opt/lean`

Este volumen conserva el proyecto Lean y la caché de Mathlib aunque se elimine y vuelva a crear el contenedor.

**IMPORTANTE:** No ejecutar `docker compose down -v`, porque eliminaría el volumen persistente.

---

## 3. Iniciar el entorno

### Desde Windows PowerShell

Primero, abrir Docker Desktop y esperar a que esté iniciado.

Ejecutar:

```powershell
cd C:\LeanMathlib
```

Iniciar el contenedor:

```powershell
docker compose up -d
```

Entrar al contenedor:

```powershell
docker compose exec lean-dev bash
```

### Entrar al proyecto Python

Dentro del contenedor:

```bash
cd /workspace/proyecto_ia_lean
```

### Entrar al proyecto Lean

```bash
cd /opt/lean/LeanMathlibProject
```

---

## 4. Comprobar las versiones

Dentro del proyecto Lean:

```bash
lean --version
```

Muestra la versión instalada de Lean.

```bash
lake --version
```

Muestra la versión de Lake.

```bash
cat lean-toolchain
```

Muestra la versión de Lean fijada para el proyecto.

Consultar el commit de Mathlib:

```bash
git -C .lake/packages/mathlib rev-parse HEAD
```

Consultar el estado de Git de Mathlib:

```bash
git -C .lake/packages/mathlib status --short
```

---

## 5. Comandos importantes de Mathlib

Desde `/opt/lean/LeanMathlibProject`:

### Descargar la caché de Mathlib

```bash
lake exe cache get
```

Descarga y descomprime los archivos compilados de Mathlib.

**IMPORTANTE:** Ya se descargaron 9081 archivos. No es necesario ejecutar este comando cada vez que se inicia Docker.

Solo volver a utilizarlo si se necesita recuperar o actualizar la caché.

### Comprobar un archivo Lean

```bash
lake env lean Test.lean
```

Compila y verifica el archivo `Test.lean`.

### Medir el tiempo de compilación

```bash
time lake env lean Test.lean
```

Muestra el tiempo real, el tiempo de CPU y el tiempo de sistema.

### Crear un archivo de prueba

```bash
cat > Test.lean <<'EOF'
import Mathlib

theorem t (a b : ℕ) : a + b = b + a := by
  omega
EOF
```

---

## 6. Verificador Python

Proyecto:

```text
/workspace/proyecto_ia_lean
```

### Ejecutar las pruebas básicas

```bash
cd /workspace/proyecto_ia_lean
python3 smoke_verifier.py
```

Ejecuta cinco pruebas:

1. `ok_omega`: acepta una demostración mediante omega.
2. `ok_exact`: acepta una demostración mediante Nat.add_comm.
3. `sorry`: rechaza una demostración incompleta.
4. `error`: rechaza código incorrecto.
5. `axioma`: rechaza axiomas no autorizados.

Resultado esperado:

```text
5/5 casos correctos
```

### Ejecutar las pruebas con Mathlib completo

```bash
python3 smoke_verifier.py --full
```

Utiliza `import Mathlib` completo en lugar de `import Mathlib.Data.Nat.Basic`.

Esta prueba permite comprobar el comportamiento con el entorno completo de Mathlib y puede tardar considerablemente más.

### Revisar el código del verificador

```bash
cat /workspace/proyecto_ia_lean/src/verifier_lean.py
```

### Revisar las dependencias Python

```bash
cat /workspace/proyecto_ia_lean/requirements.txt
```

---

## 7. Monitorizar los procesos

Se puede abrir una segunda terminal de PowerShell y entrar al contenedor:

```powershell
cd C:\LeanMathlib
docker compose exec lean-dev bash
```

Consultar los procesos de Lean y Lake:

```bash
ps -eo pid,etime,%cpu,%mem,cmd | grep -E '[l]ean|[l]ake'
```

Consultar la memoria disponible:

```bash
free -h
```

Consultar los procesos en tiempo real:

```bash
top
```

Estos comandos permiten comprobar si Lean continúa trabajando durante una compilación prolongada.

---

## 8. Cerrar el entorno correctamente

Desde Windows PowerShell:

```powershell
cd C:\LeanMathlib
docker compose down
```

Detiene y elimina el contenedor, pero conserva el volumen persistente.

Alternativamente:

```powershell
docker compose stop
```

Detiene los servicios sin eliminar el contenedor.

Para volver a iniciar:

```powershell
docker compose up -d
```

Después:

```powershell
docker compose exec lean-dev bash
```

**Nunca utilizar:**

```powershell
docker compose down -v
```

Este comando elimina también los volúmenes y puede borrar la instalación persistente de Mathlib.

---

## 9. Respaldo y reproducibilidad

Conservar siempre:

- `lean-toolchain`
- `lakefile.toml`
- `lake-manifest.json`
- `VERSIONES.md`
- `Dockerfile`
- `compose.yaml`
- Código fuente de Python y Lean.

El archivo `lake-manifest.json` es especialmente importante porque permite reproducir las revisiones exactas de las dependencias.

El volumen `lean-data` contiene los datos compilados de Mathlib y debe conservarse.

Se recomienda mantener una copia de seguridad del proyecto y registrar los cambios mediante Git.

---

## 10. Estado actual del entorno

| Componente | Estado |
|---|---|
| Docker | Configurado |
| Lean 4 | Instalado |
| Lake | Instalado |
| Mathlib | Caché descargada |
| Proyecto Lean | Funcionando |
| Proyecto Python | Disponible |
| Comunicación Python-Lean | Verificada |
| Prueba `omega` | Correcta |
| Prueba `exact` | Correcta |
| Rechazo de `sorry` | Correcto |
| Rechazo de errores | Correcto |
| Rechazo de axiomas no autorizados | Correcto |

**Resultado de la prueba de humo: 5/5 casos correctos.**

El entorno está preparado para continuar con el desarrollo del sistema multiagente de generación y verificación formal de demostraciones.