from flask import Flask, render_template, request, jsonify
import pandas as pd
import json
import os
import webbrowser
import time
import urllib.parse
import pyautogui

app = Flask(__name__)

CONFIG_FILE = 'config.json'
DEFAULT_MESSAGE = """Olá, tudo bem?

Percebi que vocês atuam no segmento de transportes/logística aqui da região e, pela nossa experiência nesse mercado, acredito que podemos agregar bastante valor para a empresa.

Hoje muitas empresas acabam pagando acima do necessário no seguro de vida empresarial ou até ficando desenquadradas da convenção coletiva sem perceber.

Por isso, estamos realizando uma análise gratuita para identificar:
* possíveis reduções de custo;
* melhorias nas coberturas;
* adequação da convenção;
* benefícios mais atrativos para os colaboradores.

Além disso, nosso diferencial está na experiência de atendimento próximo e rápido no pós-venda, oferecendo suporte tanto para a empresa quanto para os colaboradores no dia a dia.

Quem seria a melhor pessoa para eu conversar sobre esse assunto?"""

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"mensagem": DEFAULT_MESSAGE}

def save_config(mensagem):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"mensagem": mensagem}, f, ensure_ascii=False, indent=4)

def limpar_telefone(tel):
    # Remove tudo que não for número
    tel_limpo = ''.join(filter(str.isdigit, str(tel)))
    # Adiciona o DDI 55 do Brasil se faltar
    if not tel_limpo.startswith('55') and len(tel_limpo) >= 10:
        tel_limpo = '55' + tel_limpo
    return tel_limpo

def disparo_humanizado(df, mensagem_base):
    print("\n⚠️ O PROCESSO VAI COMEÇAR! Mantenha o WhatsApp Web conectado no navegador padrão.")
    time.sleep(5) # Tempo para você soltar o mouse
    
    for index, row in df.iterrows():
        nome = str(row.get('nome', row.get('Nome', ''))).strip()
        if nome.lower() == 'nan': nome = ''
        
        telefone_cru = row.get('telefone', row.get('Telefone', ''))
        telefone = limpar_telefone(telefone_cru)
        
        if len(telefone) < 12:
            print(f"❌ Número inválido pulado: {telefone_cru}")
            continue
            
        mensagem_personalizada = mensagem_base
        if nome:
            mensagem_personalizada = mensagem_base.replace("Olá, tudo bem?", f"Olá, {nome}, tudo bem?")
            
        msg_encoded = urllib.parse.quote(mensagem_personalizada)
        link_whatsapp = f"https://web.whatsapp.com/send?phone={telefone}&text={msg_encoded}"
        
        print(f"🚀 Enviando para: {nome if nome else 'Cliente'} ({telefone})...")
        webbrowser.open(link_whatsapp)
        
        # --- Simulação Humana ---
        time.sleep(15) # Espera carregar a página do chat
        
        pyautogui.press('enter') # Pressiona enter fisicamente para enviar
        print(f"✅ Mensagem enviada!")
        
        time.sleep(3)
        pyautogui.hotkey('ctrl', 'w') # Fecha a aba para não acumular
        
        print("⏳ Pausa anti-bloqueio de 20 segundos...")
        time.sleep(20)

@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', mensagem=config['mensagem'])

@app.route('/salvar_mensagem', methods=['POST'])
def salvar_mensagem():
    dados = request.json
    save_config(dados.get('mensagem', ''))
    return jsonify({"status": "sucesso"})

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "Nenhum arquivo enviado.", 400
    
    file = request.files['file']
    mensagem = request.form.get('mensagem', DEFAULT_MESSAGE)
    save_config(mensagem)
    
    if file.filename == '':
        return "Nenhum arquivo selecionado.", 400

    if file.filename.endswith('.xlsx') or file.filename.endswith('.xls'):
        df = pd.read_excel(file)
    elif file.filename.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        return "Formato inválido. Use Excel (.xlsx) ou CSV.", 400
        
    disparo_humanizado(df, mensagem)
    return "<h1>Processo concluído!</h1><p>Verifique o terminal do Python para mais detalhes.</p>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)