#!/usr/bin/env python3
"""
Sube un modelo (.tar.gz) a un algoritmo de Grand Challenge usando Chrome
headless en ESTE servidor.

Los bytes viajan servidor -> Grand Challenge mediante Uppy/S3 multipart.

Auth:
  cookies de sesion del navegador del usuario.

Uso:

  export GC_SESSIONID='...'
  export GC_CSRFTOKEN='...'

  # Inspeccionar el formulario sin subir nada:
  .venv/bin/python delete/gc_browser_upload_model.py \
      --slug blackboard-experts-and-algorithms \
      --file model.tar.gz \
      --inspect-only

  # Subida normal:
  .venv/bin/python delete/gc_browser_upload_model.py \
      --slug blackboard-experts-and-algorithms \
      --file model.tar.gz
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)

BASE = "https://grand-challenge.org"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)

    ap.add_argument(
        "--slug",
        required=True,
        help="Slug del algoritmo en Grand Challenge.",
    )

    ap.add_argument(
        "--file",
        required=True,
        help="Ruta al model.tar.gz.",
    )

    ap.add_argument(
        "--sessionid",
        default=os.environ.get("GC_SESSIONID"),
        help="Cookie sessionid. Por defecto usa GC_SESSIONID.",
    )

    ap.add_argument(
        "--csrftoken",
        default=os.environ.get("GC_CSRFTOKEN"),
        help="Cookie _csrftoken. Por defecto usa GC_CSRFTOKEN.",
    )

    ap.add_argument(
        "--timeout-min",
        type=int,
        default=180,
        help="Tiempo maximo de espera de subida, en minutos.",
    )

    ap.add_argument(
        "--inspect-only",
        action="store_true",
        help="Inspecciona el formulario y termina sin subir el archivo.",
    )

    ap.add_argument(
        "--comment",
        default=None,
        help="Comentario opcional para el modelo.",
    )

    return ap.parse_args()


def get_label(page, element) -> str:
    """
    Intenta obtener el texto del label asociado a un control.
    """
    try:
        element_id = element.get_attribute("id")

        if element_id:
            lab = page.locator(f'label[for="{element_id}"]')

            if lab.count():
                return " ".join(
                    (lab.first.inner_text() or "").split()
                )

        parent = element.locator(
            "xpath=ancestor::*[contains(@class,'form-group')][1]"
        )

        if parent.count():
            lab = parent.locator("label")

            if lab.count():
                return " ".join(
                    (lab.first.inner_text() or "").split()
                )

    except Exception:
        pass

    return ""


def inspect_form(page) -> None:
    """
    Muestra los inputs/selects/textareas del formulario.
    """
    print()
    print("==============================")
    print(" CAMPOS DEL FORMULARIO")
    print("==============================")

    controls = page.locator(
        "form input, form textarea, form select"
    )

    for i in range(controls.count()):
        el = controls.nth(i)

        try:
            tag = el.evaluate(
                "e => e.tagName.toLowerCase()"
            )

            name = el.get_attribute("name") or ""
            typ = el.get_attribute("type") or ""

            required = (
                el.get_attribute("required")
                is not None
            )

            try:
                visible = el.is_visible()
            except Exception:
                visible = False

            label = get_label(page, el)

            value = ""

            if tag == "select":
                try:
                    value = el.input_value()
                except Exception:
                    pass

            elif typ not in (
                "file",
                "password",
                "checkbox",
                "radio",
                "submit",
                "button",
            ):
                try:
                    value = el.input_value()
                except Exception:
                    pass

            print(
                f"[{i:02d}] "
                f"tag={tag:<8} "
                f"type={typ:<12} "
                f"name={name!r:<35} "
                f"required={str(required):<5} "
                f"visible={str(visible):<5} "
                f"label={label!r} "
                f"value={value!r}"
            )

        except Exception as exc:
            print(
                f"[{i:02d}] ERROR inspeccionando control: {exc}"
            )

    print("==============================")
    print()


def get_user_upload_value(page) -> str:
    """
    Obtiene el valor actual de input[name=user_upload].
    """
    loc = page.locator(
        'input[name="user_upload"]'
    )

    if not loc.count():
        return ""

    try:
        value = loc.first.input_value()
        if value:
            return value.strip()
    except Exception:
        pass

    try:
        value = loc.first.get_attribute("value")
        if value:
            return value.strip()
    except Exception:
        pass

    return ""


def wait_for_user_upload(
    page,
    timeout_seconds: int = 300,
) -> str:
    """
    Espera a que Grand Challenge/Uppy rellene el campo oculto
    user_upload después de completar la transferencia a S3.
    """
    print(
        "Esperando a que Grand Challenge registre el upload..."
    )

    loc = page.locator(
        'input[name="user_upload"]'
    )

    try:
        loc.wait_for(
            state="attached",
            timeout=30_000,
        )
    except Exception:
        print(
            "ERROR: no existe "
            "input[name='user_upload']."
        )
        return ""

    deadline = (
        time.time()
        + timeout_seconds
    )

    last_message = 0.0

    while time.time() < deadline:
        value = get_user_upload_value(page)

        if value:
            return value

        now = time.time()

        if now - last_message >= 10:
            print(
                "  Archivo transferido; "
                "esperando identificador user_upload..."
            )
            last_message = now

        time.sleep(2)

    return ""


def collect_form_errors(page) -> list[str]:
    """
    Busca errores comunes de formularios Django/Bootstrap.
    """
    errors: list[str] = []

    selectors = (
        ".errorlist li",
        ".invalid-feedback",
        ".alert-danger",
        ".text-danger",
    )

    for sel in selectors:
        loc = page.locator(sel)

        for i in range(loc.count()):
            try:
                text = (
                    loc.nth(i).inner_text()
                    or ""
                ).strip()

                if text:
                    errors.append(text)

            except Exception:
                pass

    # Eliminar duplicados conservando orden.
    return list(dict.fromkeys(errors))


def main() -> int:
    a = parse_args()

    f = Path(a.file).resolve()

    if not f.is_file():
        sys.exit(
            f"No existe el fichero: {f}"
        )

    if not a.sessionid:
        sys.exit(
            "Falta la cookie sessionid "
            "(--sessionid o GC_SESSIONID)."
        )

    print(
        f"Fichero  : {f} "
        f"({f.stat().st_size / 1e9:.2f} GB)"
    )

    print(
        "Algoritmo:",
        f"{BASE}/algorithms/{a.slug}/",
    )

    cookies = [
        {
            "name": "sessionid",
            "value": a.sessionid,
            "domain": ".grand-challenge.org",
            "path": "/",
        }
    ]

    if a.csrftoken:
        cookies.append(
            {
                "name": "_csrftoken",
                "value": a.csrftoken,
                "domain": ".grand-challenge.org",
                "path": "/",
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
        )

        ctx = browser.new_context(
            user_agent=UA,
            viewport={
                "width": 1440,
                "height": 900,
            },
            locale="en-US",
        )

        ctx.set_default_timeout(
            120_000
        )

        ctx.add_cookies(
            cookies
        )

        page = ctx.new_page()

        page.on(
            "console",
            lambda m:
                m.type in (
                    "error",
                    "warning",
                )
                and print(
                    "  [browser]",
                    m.text[:160],
                ),
        )

        # ---------------------------------------
        # Abrir formulario de modelos
        # ---------------------------------------

        url = (
            f"{BASE}/algorithms/"
            f"{a.slug}/models/create/"
        )

        r = page.goto(
            url,
            wait_until="domcontentloaded",
        )

        if "/accounts/login" in page.url:
            browser.close()

            sys.exit(
                "Cookie invalida/expirada "
                "o sin permiso de editor "
                "en este algoritmo."
            )

        if (
            r is None
            or r.status >= 400
        ):
            browser.close()

            sys.exit(
                "La pagina de subida devolvio "
                f"{r.status if r else '???'}."
            )

        print(
            "Formulario cargado:",
            page.url,
        )

        # ---------------------------------------
        # Comentario opcional
        # ---------------------------------------

        if a.comment is not None:
            comment = page.locator(
                'textarea[name="comment"]'
            )

            if comment.count():
                comment.fill(
                    a.comment
                )

        # ---------------------------------------
        # Inspeccionar
        # ---------------------------------------

        if a.inspect_only:
            inspect_form(page)

            print(
                "Modo --inspect-only: "
                "no se subira ningun fichero."
            )

            browser.close()
            return 0

        # ---------------------------------------
        # Localizar file input
        # ---------------------------------------

        file_input = page.locator(
            'input[type="file"]'
        ).first

        file_input.wait_for(
            state="attached",
            timeout=60_000,
        )

        print(
            "Adjuntando fichero; empieza la "
            "subida S3 multipart "
            "(puede tardar bastante)..."
        )

        file_input.set_input_files(
            str(f)
        )

        # ---------------------------------------
        # Vigilar Uppy
        # ---------------------------------------

        status = page.locator(
            ".uppy-StatusBar"
        )

        try:
            status.wait_for(
                state="attached",
                timeout=30_000,
            )
        except Exception:
            print(
                "Aviso: no aparecio "
                ".uppy-StatusBar; "
                "sigo vigilando igualmente."
            )

        deadline = (
            time.time()
            + a.timeout_min * 60
        )

        last = ""
        complete = False

        while time.time() < deadline:
            klass = ""
            txt = ""

            try:
                if status.count():
                    klass = (
                        status.first.get_attribute(
                            "class"
                        )
                        or ""
                    )

                    for sel in (
                        ".uppy-StatusBar-statusPrimary",
                        ".uppy-StatusBar-content",
                    ):
                        loc = page.locator(
                            sel
                        )

                        if loc.count():
                            txt = " ".join(
                                (
                                    loc.first.inner_text(
                                        timeout=1500
                                    )
                                    or ""
                                ).split()
                            )

                            if txt:
                                break

            except Exception:
                pass

            pct = ""

            try:
                pb = page.locator(
                    "[role=progressbar]"
                )

                if pb.count():
                    pct = (
                        pb.first.get_attribute(
                            "aria-valuenow"
                        )
                        or ""
                    )

            except Exception:
                pass

            line = (
                f"{txt} "
                f"{pct + '%' if pct else ''}"
            ).strip()

            if (
                line
                and line != last
            ):
                print(
                    "  ",
                    line[:140],
                )

                last = line

            # Importante:
            # pct == 100 significa que la transferencia terminó,
            # pero todavía NO necesariamente que user_upload
            # esté listo.
            if (
                "is-complete" in klass
                or "upload complete" in txt.lower()
                or pct == "100"
            ):
                complete = True
                break

            time.sleep(6)

        print(
            "Subida Uppy:",
            "COMPLETA"
            if complete
            else "NO CONFIRMADA",
        )

        if not complete:
            print(
                "\nERROR: no se pudo confirmar "
                "la finalizacion de la subida."
            )

            print(
                "No se pulsara Save."
            )

            browser.close()
            return 4

        # ---------------------------------------
        # ESPERAR user_upload
        # ---------------------------------------

        upload_value = wait_for_user_upload(
            page,
            timeout_seconds=300,
        )

        if not upload_value:
            print()
            print(
                "ERROR: Uppy llego al 100%, "
                "pero Grand Challenge no relleno "
                "input[name='user_upload']."
            )

            print(
                "No se pulsara Save para evitar "
                "el error:"
            )

            print(
                "  This field is required."
            )

            print()
            print(
                "Estado actual del formulario:"
            )

            inspect_form(page)

            browser.close()
            return 7

        print(
            "Upload registrado correctamente."
        )

        print(
            "user_upload:",
            upload_value[:120],
        )

        # Pequeña espera adicional para que cualquier
        # listener JS de Uppy termine de actualizar
        # el formulario.
        time.sleep(3)

        # Confirmar otra vez justo antes del Save.
        final_upload_value = (
            get_user_upload_value(page)
        )

        if not final_upload_value:
            print(
                "ERROR: user_upload se vacio "
                "antes de Save."
            )

            browser.close()
            return 8

        print(
            "user_upload antes de Save:",
            final_upload_value[:120],
        )

        # ---------------------------------------
        # Guardar
        # ---------------------------------------

        save = page.locator(
            "button[type=submit]:has-text('Save'), "
            "input[type=submit]"
        ).first

        save.wait_for(
            state="visible",
            timeout=30_000,
        )

        print(
            "Pulsando 'Save'..."
        )

        save.click()

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=180_000,
            )
        except Exception:
            # Algunas páginas mantienen conexiones
            # abiertas y nunca llegan estrictamente
            # a networkidle.
            pass

        print(
            "URL tras enviar:",
            page.url,
        )

        # ---------------------------------------
        # Buscar errores Django
        # ---------------------------------------

        errors = collect_form_errors(
            page
        )

        if errors:
            print()
            print(
                "!! El formulario devolvio errores:"
            )

            for error in errors:
                print(
                    "   -",
                    error[:300],
                )

            print()
            print(
                "Estado del formulario "
                "despues del error:"
            )

            inspect_form(page)

            browser.close()
            return 2

        # ---------------------------------------
        # Verificar que salimos de create
        # ---------------------------------------

        if "/models/create/" in page.url:
            print()
            print(
                "?? Sigue en la pagina "
                "de creacion."
            )

            print(
                "No hay errores visibles, "
                "pero Grand Challenge no "
                "redirecciono."
            )

            inspect_form(page)

            browser.close()
            return 5

        print()
        print(
            "OK: modelo enviado correctamente."
        )

        print(
            "Ve a:",
            f"{BASE}/algorithms/"
            f"{a.slug}/models/",
        )

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

