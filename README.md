# NVIDIA Power Control

Aplicación gráfica para KDE Plasma en CachyOS/Arch Linux que permite gestionar límites de potencia en una GPU NVIDIA compatible.

## Funciones

- Tres perfiles predefinidos: **280 W** (Eficiente), **320 W** (Equilibrado) y **360 W** (Máximo).
- Consumo de GPU, temperatura, utilización y límite actual.
- Interfaz oscura con iconos Qt y menú de bandeja.
- Nombres de perfiles configurables.
- Reglas experimentales por nombre de proceso, **desactivadas por defecto**, con confirmación antes de aplicar cambios.
- Usa **Polkit** (`pkexec`) para autorización. No modifica `sudoers` ni instala demonios con privilegios elevados.

## Instalación en CachyOS

```fish
sudo pacman -S pyside6
fish instalar.fish
```

Busca **NVIDIA Power Control** en el lanzador de KDE. Para cerrar la aplicación, usa la opción **Salir** de la bandeja.

## Requisitos y advertencias

- KDE Plasma y Python 3 con `PySide6`.
- Controlador propietario o abierto NVIDIA con `nvidia-smi`.
- `pkexec` y un agente de autenticación Polkit.
- Esta versión utiliza **GPU índice 0** y límites fijos diseñados para una **Palit GeForce RTX 5080** (rango comprobado: 250–360 W). No apliques estos límites sin comprobar tu GPU.
- Los cambios no son permanentes después de reinicios o reinicios del controlador.
- La detección de juegos lee los nombres de proceso en `/proc`, no utiliza rutas ni argumentos.
- La aplicación no ha pasado todavía una batería de pruebas automatizadas en otras distribuciones.

La configuración privada de usuario se almacena en `~/.config/gpu-profiles/config.json` y no debe subirse al repositorio.

## Licencia

Copyright (C) 2026 NVIDIA Power Control contributors.

Este proyecto se distribuye bajo la **GNU Affero General Public License versión 3 exclusivamente (AGPL-3.0-only)**. Lee el archivo [LICENSE](LICENSE).

## Marcas

NVIDIA es una marca de NVIDIA Corporation. Este proyecto es independiente y no está afiliado ni respaldado por NVIDIA. El icono incluido es una interpretación gráfica original y no el logotipo oficial.
