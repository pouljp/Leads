from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from scraper_maps import buscar_maps
from scraper_google import enriquecer_serp
import json
import os
import pandas as pd
import unicodedata
import re
import webbrowser
import time
import urllib.parse
import pyautogui

app = Flask(__name__)

DATA_DIR = "data"
HISTORICO_ARQ = os.path.join(DATA_DIR, "historico.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)

DEFAULT_MESSAGE = """Olá, tudo bem?

Percebi que vocês atuam no segmento de transportes/logística aqui da região e, pela nossa experiência nesse mercado, acredito que podemos agregar bastante valor para a empresa.

Hoje muitas empresas acabam pagando acima do necessário no seguro de vida empresarial ou até ficando desenquadradas da convenção coletiva sem perceber.

Por isso, estamos realizando uma análise gratuita para identificar:
* possíveis reduções de custo;
* melhorias nas coberturas;
* adequação da convenção;
* benefícios mais atrativos para os colaboradores.

Além disso, nosso diferencial está na experiência de atendimento próximo e rápido no pós-venda, offering suporte tanto para a empresa quanto para os colaboradores no dia a dia.

Quem seria a melhor pessoa para eu conversar sobre esse assunto?"""

def carregar_historico():
    if os.path.exists(HISTORICO_ARQ):
        with open(HISTORICO_ARQ, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_historico(dados):
    with open(HISTORICO_ARQ, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"mensagem": DEFAULT_MESSAGE}
    return {"mensagem": DEFAULT_MESSAGE}

def save_config(mensagem):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"mensagem": mensagem}, f, ensure_ascii=False, indent=4)

def limpar_nome_arquivo(texto):
    texto = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("ASCII")
    texto = re.sub(r'[<>:"/\\|?*]', '', texto)
    texto = texto.replace(" | ", "_").replace(" ", "_")
    return texto.lower()

def limpar_telefone(tel):
    if not tel: return ""
    tel_limpo = ''.join(filter(str.isdigit, str(tel)))
    if not tel_limpo.startswith('55') and len(tel_limpo) >= 10:
        tel_limpo = '55' + tel_limpo
    return tel_limpo

# --- ROTAS ORIGINAIS DE BUSCA E ENRIQUECIMENTO ---

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
    caminho = os.path.join(DATA_DIR, f"{nome_limpo}.xlsx")

    with pd.ExcelWriter(caminho, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Leads')
        workbook = writer.book
        worksheet = writer.sheets['Leads']
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'middle', 'align': 'center', 'border': 1})
        
        for col_num, col_name in enumerate(df.columns):
            max_length = max(df[col_name].astype(str).map(len).max(), len(col_name)) + 2
            worksheet.set_column(col_num, col_num, max_length)
            worksheet.write(0, col_num, col_name, header_format)

        cell_format = workbook.add_format({'border': 1})
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
    from serp_service import enriquecer_empresas
    empresas = enriquecer_empresas(empresas)

    historico[chave] = empresas
    salvar_historico(historico)

    return render_template("index.html", empresas=empresas, chave_atual=chave, historico=historico)


# --- RECURSOS DO WHATSAPP INTEGADOS ---

@app.route("/whatsapp/config/<path:chave>")
def whatsapp_config(chave):
    historico = carregar_historico()
    if chave not in historico:
        return "Busca de leads não encontrada.", 404
    
    config = load_config()
    empresas = historico[chave]
    
    # Filtra apenas quem tem telefone para exibir na prévia
    leads_validos = [e for e in empresas if e.get('telefone')]
    
    return render_template(
        "whatsapp.html", 
        chave=chave, 
        mensagem=config['mensagem'], 
        leads=leads_validos
    )

@app.route('/salvar_mensagem', methods=['POST'])
def salvar_mensagem():
    dados = request.json
    save_config(dados.get('mensagem', ''))
    return jsonify({"status": "sucesso"})

@app.route("/whatsapp/disparar/<path:chave>", methods=["POST"])
def whatsapp_disparar(chave):
    historico = carregar_historico()
    if chave not in historico:
        return "Busca não encontrada", 404

    mensagem = request.form.get('mensagem', DEFAULT_MESSAGE)
    save_config(mensagem) # Garante o salvamento no JSON
    
    empresas = historico[chave]
    
    print("\n⚠️ O PROCESSO DE DISPARO COMEÇARÁ EM 5 SEGUNDOS!")
    time.sleep(5)
    
    for e in empresas:
        nome = str(e.get('nome', '')).strip()
        telefone_cru = e.get('telefone', '')
        telefone = limpar_telefone(telefone_cru)
        
        # Pula se não houver telefone válido
        if len(telefone) < 12:
            print(f"❌ Lead {nome} ignorado (Sem telefone válido: '{telefone_cru}')")
            continue
            
        mensagem_personalizada = mensagem
        if nome:
            mensagem_personalizada = mensagem.replace("Olá, tudo bem?", f"Olá, {nome}, tudo bem?")
            
        msg_encoded = urllib.parse.quote(mensagem_personalizada)
        link_whatsapp = f"https://web.whatsapp.com/send?phone={telefone}&text={msg_encoded}"
        
        print(f"🚀 Abrindo chat para: {nome} ({telefone})...")
        webbrowser.open(link_whatsapp)
        
        # Cadência humana
        time.sleep(15) # Tempo de carregamento da página
        pyautogui.press('enter')
        print(f"✅ Comando de envio disparado.")
        
        time.sleep(3)
        pyautogui.hotkey('ctrl', 'w') # Fecha a aba criada
        
        print("⏳ Pausa estratégica anti-bloqueio (20 segundos)...")
        time.sleep(20)
        
    return "<h1>Disparos Concluídos!</h1><p>O robô percorreu a lista selecionada. Veja os detalhes no terminal.</p><br><a href='/'>Voltar ao Início</a>"

# --- ROTA PARA A TELA DE DISPARO MANUAL ---
@app.route("/whatsapp/manual")
def whatsapp_manual():
    config = load_config()
    return render_template("whatsapp_manual.html", mensagem=config['mensagem'])

# --- ROTA QUE PROCESSA OS LEADS INSERIDOS MANUALMENTE ---
# --- ROTA QUE PROCESSA OS LEADS INSERIDOS MANUALMENTE (TEXTO OU PLANILHA CORRIGIDA) ---
@app.route("/whatsapp/disparar_manual", methods=["POST"])
def whatsapp_disparar_manual():
    mensagem = request.form.get('mensagem', DEFAULT_MESSAGE)
    save_config(mensagem) # Salva a mensagem atualizada no JSON
    
    empresas_manuais = []

    # 1. VERIFICA SE FOI ENVIADO UM ARQUIVO DE PLANILHA
    if 'file' in request.files and request.files['file'].filename != '':
        file = request.files['file']
        
        try:
            if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
                df = pd.read_excel(file)
            elif file.filename.endswith('.csv'):
                # 💡 CORREÇÃO AQUI: Deteta se o CSV usa vírgula (como a sua planilha de teste) ou ponto e vírgula
                try:
                    # Tenta ler com vírgula primeiro
                    df = pd.read_csv(file, sep=',')
                    # Se leu errado e gerou apenas 1 coluna, tenta com ponto e vírgula
                    if df.shape[1] <= 1:
                        file.seek(0)
                        df = pd.read_csv(file, sep=';')
                except:
                    file.seek(0)
                    df = pd.read_csv(file, sep=';')
            else:
                return "<h1>Erro</h1><p>Formato de arquivo inválido. Use Excel (.xlsx) ou CSV.</p><br><a href='/whatsapp/manual'>Voltar</a>"
            
            # Limpa espaços em branco ocultos nos nomes das colunas da planilha
            df.columns = [str(col).strip().lower() for col in df.columns]
            
            # Mapeia as linhas procurando pelas colunas corretas
            for index, row in df.iterrows():
                # Tenta achar a coluna de nome (independente de maiúscula/minúscula)
                nome = str(row.get('nome', row.get('Nome', ''))).strip()
                if nome.lower() == 'nan' or nome.lower() == 'none': 
                    nome = ''
                
                # Tenta achar a coluna de telefone
                telefone = str(row.get('telefone', row.get('Telefone', ''))).strip()
                
                if telefone and telefone.lower() != 'nan':
                    empresas_manuais.append({'nome': nome, 'telefone': telefone})
                    
        except Exception as e:
            return f"<h1>Erro ao ler planilha</h1><p>{str(e)}</p><br><a href='/whatsapp/manual'>Voltar</a>"

    # 2. SE NÃO HOUVER ARQUIVO, PEGA O TEXTO DIGITADO
    else:
        lista_contatos = request.form.get('contatos', '').split('\n')
        for linha in lista_contatos:
            if not linha.strip():
                continue
            
            if ',' in linha:
                partes = linha.split(',', 1)
                nome = partes[0].strip()
                tel = partes[1].strip()
            elif ';' in linha:
                partes = linha.split(';', 1)
                nome = partes[0].strip()
                tel = partes[1].strip()
            else:
                nome = ""
                tel = linha.strip()
                
            if tel:
                empresas_manuais.append({'nome': nome, 'telefone': tel})
            
    # VALIDAÇÃO SE ENCONTROU CONTATOS
    if not empresas_manuais:
        return "<h1>Erro</h1><p>Nenhum contato encontrado. Verifique se as colunas da planilha se chamam exatamente 'nome' e 'telefone'.</p><br><a href='/whatsapp/manual'>Voltar</a>"

    print(f"\n⚠️ O PROCESSO COMEÇARÁ EM 5 SEGUNDOS! Total de leads carregados: {len(empresas_manuais)}")
    time.sleep(5)
    
    for e in empresas_manuais:
        nome = e['nome']
        telefone = limpar_telefone(e['telefone'])
        
        # 💡 CORREÇÃO DO TAMANHO DO TELEFONE: Aceita DDD (2 dígitos) + Número (8 ou 9 dígitos) + DDI (55) = Mínimo 11 dígitos
        if len(telefone) < 11:
            print(f"❌ Lead {nome} ignorado (Telefone muito curto ou inválido: '{e['telefone']}')")
            continue
            
        mensagem_personalizada = mensagem
        if nome:
            mensagem_personalizada = mensagem.replace("Olá, tudo bem?", f"Olá, {nome}, tudo bem?")
            
        msg_encoded = urllib.parse.quote(mensagem_personalizada)
        link_whatsapp = f"https://web.whatsapp.com/send?phone={telefone}&text={msg_encoded}"
        
        print(f"🚀 Abrindo chat para: {nome if nome else 'Cliente'} ({telefone})...")
        webbrowser.open(link_whatsapp)
        
        time.sleep(15) # Espera carregar a página do WhatsApp Web
        pyautogui.press('enter')
        print(f"✅ Comando de envio disparado com sucesso.")
        
        time.sleep(3)
        pyautogui.hotkey('ctrl', 'w') # Fecha a aba
        
        print("⏳ Pausa estratégica anti-bloqueio (20 segundos)...")
        time.sleep(20)
        
    return "<h1>Disparos Concluídos!</h1><p>O robô terminou de processar o seu ficheiro de testes.</p><br><a href='/'>Voltar ao Início</a>"


if __name__ == "__main__":
    app.run(debug=True)