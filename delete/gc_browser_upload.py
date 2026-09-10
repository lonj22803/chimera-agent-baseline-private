#!/usr/bin/env python3
"""Sube una imagen de contenedor (.tar.gz) a un algoritmo de Grand Challenge
manejando Chrome headless en ESTE servidor: los bytes viajan servidor -> GC
(S3 multipart via Uppy) y no pasan por la maquina cliente.

Auth: cookies de sesion del navegador del usuario (no la contrasena).

Uso:
  export GC_SESSIONID='...'          # cookie sessionid
  export GC_CSRFTOKEN='...'          # cookie _csrftoken
  .venv/bin/python delete/gc_browser_upload.py \
      --slug blackboard-experts-and-llms \
      --file chimera_agent_baseline_debug_bxisupfix_20260910-194641.tar.gz
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
BASE = "https://grand-challenge.org"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--sessionid", default=os.environ.get("GC_SESSIONID"))
    ap.add_argument("--csrftoken", default=os.environ.get("GC_CSRFTOKEN"))
    ap.add_argument("--timeout-min", type=int, default=180)
    return ap.parse_args()


def main() -> int:
    a = parse_args()
    f = Path(a.file).resolve()
    if not f.is_file():
        sys.exit(f"No existe el fichero: {f}")
    if not a.sessionid:
        sys.exit("Falta la cookie sessionid (--sessionid o GC_SESSIONID).")
    print(f"Fichero  : {f}  ({f.stat().st_size / 1e9:.2f} GB)")
    print(f"Algoritmo: {BASE}/algorithms/{a.slug}/")

    cookies = [{"name": "sessionid", "value": a.sessionid, "domain": ".grand-challenge.org", "path": "/"}]
    if a.csrftoken:
        cookies.append({"name": "_csrftoken", "value": a.csrftoken, "domain": ".grand-challenge.org", "path": "/"})

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 900}, locale="en-US")
        ctx.set_default_timeout(120_000)
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.on("console", lambda m: m.type in ("error", "warning") and print("  [browser]", m.text[:160]))

        url = f"{BASE}/algorithms/{a.slug}/images/create/"
        r = page.goto(url, wait_until="domcontentloaded")
        if "/accounts/login" in page.url:
            sys.exit("Cookie invalida/expirada o sin permiso de editor en este algoritmo.")
        if r is None or r.status >= 400:
            sys.exit(f"La pagina de subida devolvio {r.status if r else '???'}.")
        print("Formulario cargado:", page.url)

        # Adjuntar el fichero -> Uppy arranca la subida por partes a S3.
        file_input = page.locator("input[type=file]").first
        file_input.wait_for(state="attached", timeout=60_000)
        print("Adjuntando fichero; empieza la subida S3 multipart (puede tardar bastante)...")
        file_input.set_input_files(str(f))

        status = page.locator(".uppy-StatusBar")
        try:
            status.wait_for(state="attached", timeout=30_000)
        except Exception:
            print("Aviso: no aparecio .uppy-StatusBar; sigo vigilando de todas formas.")

        deadline = time.time() + a.timeout_min * 60
        last = ""
        complete = False
        while time.time() < deadline:
            klass = ""
            txt = ""
            try:
                if status.count():
                    klass = status.first.get_attribute("class") or ""
                    for sel in (".uppy-StatusBar-statusPrimary", ".uppy-StatusBar-content"):
                        loc = page.locator(sel)
                        if loc.count():
                            txt = " ".join((loc.first.inner_text(timeout=1500) or "").split())
                            if txt:
                                break
            except Exception:
                pass
            pct = ""
            try:
                pb = page.locator("[role=progressbar]")
                if pb.count():
                    pct = pb.first.get_attribute("aria-valuenow") or ""
            except Exception:
                pass
            line = f"{txt}  {pct + '%' if pct else ''}".strip()
            if line and line != last:
                print("  ", line[:140])
                last = line
            if "is-complete" in klass or "upload complete" in txt.lower() or pct == "100":
                complete = True
                break
            # a veces Uppy termina y no deja rastro: si el boton Save quedo listo y ya subio algo
            time.sleep(6)

        print("Subida Uppy:", "COMPLETA" if complete else "no confirmada (continuo igualmente)")

        # Enviar el formulario (crea la Algorithm Container Image).
        save = page.locator("button[type=submit]:has-text('Save'), input[type=submit]").first
        save.wait_for(state="visible", timeout=30_000)
        print("Pulsando 'Save'...")
        save.click()
        try:
            page.wait_for_load_state("networkidle", timeout=180_000)
        except Exception:
            pass
        print("URL tras enviar:", page.url)

        # Buscar errores de formulario Django.
        errs = []
        for sel in (".errorlist li", ".invalid-feedback", ".alert-danger", ".text-danger"):
            loc = page.locator(sel)
            for i in range(loc.count()):
                t = (loc.nth(i).inner_text() or "").strip()
                if t:
                    errs.append(t)
        if errs:
            print("\n!! El formulario devolvio errores:")
            for e in errs:
                print("   -", e[:200])
            browser.close()
            return 2

        if "/images/create/" in page.url:
            print("\n?? Sigue en la pagina de creacion sin errores visibles. Revisa manualmente.")
        else:
            print("\nOK: imagen enviada. Ve a", f"{BASE}/algorithms/{a.slug}/images/")
            print("Espera a que quede 'Active' (~20 min; hasta 1 h).")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
