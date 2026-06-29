#!/usr/bin/env python3
"""Ajusta la navegación y deja la página de clasificación como vista de eliminatorias."""

from pathlib import Path


PATCH_VERSION = "2026-06-29-1"


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new, 1)


def patch_index() -> None:
    path = Path("index.html")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '<a class="nav-link" href="predicciones.html">Predicciones</a>',
        '<a class="nav-link" href="clasificacion.html">Eliminatorias</a><a class="nav-link" href="predicciones.html">Predicciones</a>',
    )
    path.write_text(text, encoding="utf-8")


def patch_predictions() -> None:
    path = Path("predicciones.html")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '<a class="nav-link" href="index.html">Dashboard</a>',
        '<a class="nav-link" href="index.html">Dashboard</a><a class="nav-link" href="clasificacion.html">Eliminatorias</a>',
    )
    path.write_text(text, encoding="utf-8")


def patch_eliminatorias() -> None:
    path = Path("clasificacion.html")
    text = path.read_text(encoding="utf-8")
    text = text.replace("<title>Clasificación Mundial 2026</title>", "<title>Eliminatorias Mundial 2026</title>")
    text = text.replace("<h1>Clasificación Mundial 2026</h1>", "<h1>Eliminatorias Mundial 2026</h1>")
    text = text.replace('<div class="sub">Tablas y eliminatorias</div>', '<div class="sub">Bracket del torneo</div>')
    text = text.replace(
        '  <section class="tabs"><button class="tab active" data-view="groups">Clasificación</button><button class="tab" data-view="knockout">Eliminatorias</button></section>\n'
        '  <section id="groupsView"><div class="section-title"><h2>Clasificación por grupos</h2><div class="legend"><span>Verde: clasifica directo</span><span>Amarillo: mejores terceros</span><span>Gris: eliminado</span></div></div><div id="groupsGrid" class="grid"></div></section>\n'
        '  <section id="knockoutView" style="display:none"><div class="section-title"><h2>Eliminatorias</h2></div><div class="bracket-shell"><div id="bracketGrid" class="bracket"></div></div></section>',
        '  <section id="knockoutView"><div class="section-title"><h2>Eliminatorias</h2></div><div class="bracket-shell"><div id="bracketGrid" class="bracket"></div></div></section>',
    )
    text = text.replace("buildTables();renderGroups();renderBracket();setupTabs()", "renderBracket()")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_index()
    patch_predictions()
    patch_eliminatorias()


if __name__ == "__main__":
    main()
