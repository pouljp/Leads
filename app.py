from flask import Flask, render_template, request, send_file
from scraper_maps import buscar_maps
from scraper_google import enriquecer_serp
import json, os, pandas as pd
import unicodedata
import re

app = Flask(__name__)

DATA_DIR = "data"
HISTORICO_ARQ = os.path.join(DATA_DIR, "historico.json")

os.makedirs(DATA_DIR, exist_ok=True)


def carregar_historico():
    if os.path.exists(HISTORICO_ARQ):
        with open(HISTORICO_ARQ, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def salvar_historico(dados):
    with open(HISTORICO_ARQ, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def limpar_nome_arquivo(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
    texto = re.sub(r'[<>:"/\\|?*]', '', texto)
    texto = texto.replace(" | ", "_").replace(" ", "_")
    return texto.lower()


@app.route("/", methods=["GET", "POST"])
def index():
    empresas = []
    chave_atual = None
    historico = carregar_historico()

    if request.method == "POST":
        atividade = request.form["atividade"]
        cidade = request.form["cidade"]

        chave_atual = f"{atividade} | {cidade}"

        if chave_atual not in historico:
            empresas = buscar_maps(atividade, cidade, limite=30)
            historico[chave_atual] = empresas
            salvar_historico(historico)
        else:
            empresas = historico[chave_atual]

    return render_template(
        "index.html",
        empresas=empresas,
        chave_atual=chave_atual,
        historico=historico
    )


@app.route("/ver/<path:chave>")
def ver_busca(chave):
    historico = carregar_historico()
    empresas = historico.get(chave, [])

    return render_template(
        "index.html",
        empresas=empresas,
        chave_atual=chave,
        historico=historico
    )


@app.route("/exportar/<path:chave>")
def exportar(chave):
    historico = carregar_historico()

    if chave not in historico:
        return "Busca não encontrada"

    df = pd.DataFrame(historico[chave])

    nome_limpo = limpar_nome_arquivo(chave)
    arquivo = f"{nome_limpo}.xlsx"
    caminho = os.path.join(DATA_DIR, arquivo)

    # Criando Excel bonito
    with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')

        workbook = writer.book
        worksheet = writer.sheets['Leads']

        # 🎨 Estilo do cabeçalho
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'middle',
            'align': 'center',
            'border': 1
        })

        # 📏 Ajustar colunas automaticamente
        for col_num, col_name in enumerate(df.columns):
            max_length = max(
                df[col_name].astype(str).map(len).max(),
                len(col_name)
            ) + 2

            worksheet.set_column(col_num, col_num, max_length)

            # aplicar estilo no cabeçalho
            worksheet.write(0, col_num, col_name, header_format)

        # 🧱 Borda nas células
        cell_format = workbook.add_format({
            'border': 1
        })

        for row in range(1, len(df) + 1):
            for col in range(len(df.columns)):
                worksheet.write(row, col, df.iloc[row-1, col], cell_format)

    return send_file(caminho, as_attachment=True)


@app.route("/completar/<path:chave>")
def completar(chave):

    historico = carregar_historico()

    if chave not in historico:
        return "Busca não encontrada"

    empresas = historico[chave]

    atividade, cidade = chave.split("|")

    from serp_service import enriquecer_empresas
    empresas = enriquecer_empresas(empresas)

    historico[chave] = empresas
    salvar_historico(historico)

    return render_template(
        "index.html",
        empresas=empresas,
        chave_atual=chave,
        historico=historico
    )
if __name__ == "__main__":
    app.run(debug=True)