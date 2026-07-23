import json
import os
from flask import Flask, render_template_string

def build_static_site():
    print("Building static site for GitHub Pages...")
    os.makedirs("public", exist_ok=True)
    
    with open("templates/index.html", encoding="utf-8") as f:
        html_content = f.read()

    # Sostituisci chiamate API con dati pre-caricati per la visualizzazione statica su GitHub Pages
    items = []
    if os.path.exists("data/subitoscanner_results.json"):
        try:
            with open("data/subitoscanner_results.json", encoding="utf-8") as f:
                items.extend(json.load(f))
        except Exception:
            pass

    if os.path.exists("data/amazonscanner_results.json"):
        try:
            with open("data/amazonscanner_results.json", encoding="utf-8") as f:
                items.extend(json.load(f))
        except Exception:
            pass

    # Copia style.css nella cartella public
    with open("static/style.css", encoding="utf-8") as f:
        css = f.read()
    
    os.makedirs("public/static", exist_ok=True)
    with open("public/static/style.css", "w", encoding="utf-8") as f:
        f.write(css)

    # Inietta lo stato pre-popolato nell'HTML statico per GitHub Pages
    inject_script = f"""
    <script>
      window.STATIC_ITEMS = {json.dumps(items, ensure_ascii=False)};
      document.addEventListener('DOMContentLoaded', () => {{
        if (window.STATIC_ITEMS && window.STATIC_ITEMS.length) {{
          state.items = window.STATIC_ITEMS;
          renderItems(window.STATIC_ITEMS);
          renderNearMiss(window.STATIC_ITEMS);
        }}
      }});
    </script>
    </body>
    """
    
    final_html = html_content.replace("</body>", inject_script)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(final_html)

    print("Static site build completed: public/index.html ready.")

if __name__ == "__main__":
    build_static_site()
