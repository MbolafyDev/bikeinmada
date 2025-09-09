# common/pdf.py
from django.template.loader import render_to_string
from django.http import HttpResponse
from weasyprint import HTML, CSS

def render_html_to_pdf(template_name: str, context: dict, request, filename: str = "document.pdf"):
    """
    Rend un template HTML -> PDF (bytes) via WeasyPrint et renvoie un HttpResponse PDF.
    - base_url est indispensable pour que {% static %} et les images fonctionnent.
    """
    html_str = render_to_string(template_name, context, request=request)
    base_url = request.build_absolute_uri("/")  # résout les URLs statiques/relatives
    pdf_bytes = HTML(string=html_str, base_url=base_url).write_pdf()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

def render_single_page_pdf(
    template_name,
    context,
    request,
    filename="document.pdf",
    heights_mm=(420, 600, 840, 1000, 1300, 1600, 2000, 2400, 3000, 3600, 4200),
    margin_mm=10,
):
    """
    Force le rendu sur 1 seule page en:
      1) testant des hauteurs de page croissantes,
      2) neutralisant les sauts .page { page-break-after },
      3) redimensionnant avec zoom pour retomber en A4.
    """
    html_str = render_to_string(template_name, context, request=request)
    base_url = request.build_absolute_uri("/")

    A4_W, A4_H = 210.0, 297.0

    # CSS d'override pour le mode "single page"
    def override_css(height_mm: float) -> CSS:
        return CSS(string=f"""
            @page {{
                size: {A4_W}mm {height_mm}mm;   /* page très haute */
                margin: {margin_mm}mm;
            }}
            /* Neutralise le saut forcé de votre template */
            .page {{ page-break-after: auto !important; }}

            /* Limite la casse des blocs importants */
            h1, h2, h3, table, .avoid-break, .signatures, .pay-row {{
                page-break-inside: avoid;
            }}

            /* Eviter qu'un petit bloc passe tout seul sur la page suivante */
            .keep-with-next {{ page-break-after: avoid; }}
        """)

    # On tente jusqu'à obtenir exactement 1 page
    for h in heights_mm:
        doc = HTML(string=html_str, base_url=base_url).render(stylesheets=[override_css(h)])
        if len(doc.pages) == 1:
            zoom = A4_H / h  # ramène la hauteur totale à 297mm
            pdf_bytes = doc.write_pdf(zoom=zoom)
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'inline; filename="{filename}"'
            return resp

    # Fallback multipage A4 si jamais ça ne tient pas (cas extrême)
    normal_css = CSS(string=f"@page {{ size: A4; margin: {margin_mm}mm; }}")
    pdf_bytes = HTML(string=html_str, base_url=base_url).write_pdf(stylesheets=[normal_css])
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp