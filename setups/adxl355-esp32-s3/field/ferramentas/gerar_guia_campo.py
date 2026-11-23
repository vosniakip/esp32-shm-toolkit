"""Reproduz o PDF de campo a partir do Markdown; nao controla o hardware."""
from gerar_guia_pdf import ROOT, parse, footer, SimpleDocTemplate, A4, mm


def main():
    out = ROOT / 'docs/GUIA_CAMPO_PASSARELA_UFPR.pdf'
    story = []
    parse(ROOT / 'docs/GUIA_CAMPO_PASSARELA_UFPR.md', story)
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=18*mm, bottomMargin=22*mm,
                            title='Passarela UFPR: dois pontos, 20 minutos por ponto', author='TFC Isaque')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(out)


if __name__ == '__main__':
    main()
