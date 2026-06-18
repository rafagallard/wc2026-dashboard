# Dashboard Copa Mundial 2026

Proyecto listo para publicar en GitHub Pages.

## Archivos

- `index.html`: dashboard cliente-facing.
- `worldcup_results.json`: fuente de datos que consume el dashboard.
- `scripts/update_worldcup_results.py`: actualizador de resultados.
- `.github/workflows/update-worldcup.yml`: tarea automática cada 6 horas.

## Publicación sugerida

1. Crear un repositorio en GitHub.
2. Subir estos archivos a la raíz del repositorio.
3. Activar GitHub Pages desde `Settings > Pages` usando la rama principal.
4. Activar GitHub Actions.

El dashboard no usa localStorage ni muestra instrucciones internas. Sólo consume `worldcup_results.json`.
