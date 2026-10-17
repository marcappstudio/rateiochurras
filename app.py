import streamlit as st
import datetime
import qrcode
import io

# -------------------------------------------------------------
# 1. FUNÇÕES DO PADRÃO OFICIAL PIX (BR CODE / EMVCo)
# -------------------------------------------------------------
def emv(tag_id: str, value: str) -> str:
    tamanho = f"{len(value):02d}"
    return f"{tag_id}{tamanho}{value}"

def calcular_crc16(payload: str) -> str:
    crc = 0xFFFF
    for char in payload:
        crc ^= ord(char) << 8
        for _ in range(8):
            if (crc & 0x8000) != 0:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"

def gerar_payload_pix(chave: str, nome: str, valor: float) -> str:
    chave = chave.strip()
    nome = nome.strip().upper()[:25]
    valor_str = f"{valor:.2f}" if valor > 0 else ""

    merchant_account = emv("00", "BR.GOV.BCB.PIX") + emv("01", chave)

    payload = (
        emv("00", "01") +
        emv("26", merchant_account) +
        emv("52", "0000") +
        emv("53", "986") +
        (emv("54", valor_str) if valor_str else "") +
        emv("58", "BR") +
        emv("59", nome or "RECEBEDOR") +
        emv("60", "BRASIL") +
        emv("62", emv("05", "***")) +
        "6304"
    )
    return payload + calcular_crc16(payload)

def gerar_imagem_qrcode(conteudo: str):
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# -------------------------------------------------------------
# 2. CONFIGURAÇÃO E ESTADO (INICIALIZA VAZIO)
# -------------------------------------------------------------
st.set_page_config(page_title="Rateio do Churrasco", page_icon="🥩", layout="centered")

# Lista inicia totalmente vazia, sem participantes de teste
if "participantes" not in st.session_state:
    st.session_state.participantes = []

st.title("🥩 Churrascômetro & Rateio Pix")
st.write("Organize os presentes, defina o consumo e acompanhe o rateio em tempo real.")

# -------------------------------------------------------------
# 3. DETALHES DO EVENTO & GASTOS
# -------------------------------------------------------------
st.subheader("📅 Detalhes do Evento")
col_nome, col_data, col_hora = st.columns([2, 1, 1])

with col_nome:
    titulo = st.text_input("Nome do Evento", value="Churrasco da Galera")
with col_data:
    data_evento = st.date_input("Data", value=datetime.date.today(), format="DD/MM/YYYY")
with col_hora:
    hora_evento = st.time_input("Horário", value=datetime.time(12, 0))

st.subheader("💰 Gastos Totais")
col_g1, col_g2 = st.columns(2)
with col_g1:
    gasto_comida = st.number_input("Total Gasto em Comida (R$)", min_value=0.0, value=300.0, step=10.0)
with col_g2:
    gasto_bebida = st.number_input("Total Gasto em Bebida (R$)", min_value=0.0, value=180.0, step=10.0)

# -------------------------------------------------------------
# 4. ADICIONAR NOVO PARTICIPANTE
# -------------------------------------------------------------
st.subheader("👥 Lista de Participantes")

with st.form("form_novo_participante", clear_on_submit=True):
    col_novo_nome, col_novo_tipo, col_btn = st.columns([2, 2, 1])
    with col_novo_nome:
        novo_nome = st.text_input("Nome do convidado", placeholder="ex: João")
    with col_novo_tipo:
        novo_tipo = st.selectbox("Consumo", ["Comida + Bebida", "Só Comida"])
    with col_btn:
        st.write("")
        st.write("")
        adicionar = st.form_submit_button("➕ Adicionar")
    
    if adicionar and novo_nome.strip():
        st.session_state.participantes.append({
            "nome": novo_nome.strip(),
            "tipo": novo_tipo,
            "pago": False
        })
        st.rerun()

# -------------------------------------------------------------
# 5. CÁLCULO DAS COTAS (FEITO ANTES DE DESENHAR A LISTA)
# -------------------------------------------------------------
qtd_so_comida = sum(1 for p in st.session_state.participantes if p["tipo"] == "Só Comida")
qtd_comida_bebida = sum(1 for p in st.session_state.participantes if p["tipo"] == "Comida + Bebida")
total_comem = qtd_so_comida + qtd_comida_bebida
total_bebem = qtd_comida_bebida

cota_comida = (gasto_comida / total_comem) if total_comem > 0 else 0.0
cota_bebida = (gasto_bebida / total_bebem) if total_bebem > 0 else 0.0

valor_apenas_comida = cota_comida
valor_comida_bebida = cota_comida + cota_bebida

# -------------------------------------------------------------
# 6. EXIBIÇÃO E EDIÇÃO EM TEMPO REAL DOS PARTICIPANTES
# -------------------------------------------------------------
if st.session_state.participantes:
    remover_idx = None
    
    for idx, p in enumerate(st.session_state.participantes):
        col_check, col_nome_p, col_tipo_p, col_valor, col_del = st.columns([1, 2.5, 2.5, 2, 1])
        
        with col_check:
            # Checkbox para registrar se pagou
            p["pago"] = st.checkbox("Pago", value=p["pago"], key=f"pago_{idx}")
        
        with col_nome_p:
            st.markdown(f"**{p['nome']}**")
            
        with col_tipo_p:
            # Seletor editável na hora: altera de 'Comida + Bebida' para 'Só Comida' sem deletar
            opcoes = ["Comida + Bebida", "Só Comida"]
            idx_atual = opcoes.index(p["tipo"]) if p["tipo"] in opcoes else 0
            novo_tipo_selecionado = st.selectbox(
                "Tipo",
                opcoes,
                index=idx_atual,
                key=f"tipo_{idx}",
                label_visibility="collapsed"
            )
            if novo_tipo_selecionado != p["tipo"]:
                p["tipo"] = novo_tipo_selecionado
                st.rerun()

        with col_valor:
            cota_individual = valor_apenas_comida if p["tipo"] == "Só Comida" else valor_comida_bebida
            if p["pago"]:
                st.markdown("<span style='color:green; font-weight:600;'>✅ Quitado</span>", unsafe_allow_html=True)
            else:
                st.markdown(f"**R$ {cota_individual:.2f}**")
                
        with col_del:
            if st.button("❌", key=f"del_{idx}"):
                remover_idx = idx

    if remover_idx is not None:
        st.session_state.participantes.pop(remover_idx)
        st.rerun()
else:
    st.info("Nenhum participante adicionado ainda. Insira o primeiro nome acima para iniciar o rateio.")

# -------------------------------------------------------------
# 7. RESUMO FINANCEIRO
# -------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Resumo Financeiro")

arrecadado = 0.0
for p in st.session_state.participantes:
    if p["pago"]:
        arrecadado += valor_apenas_comida if p["tipo"] == "Só Comida" else valor_comida_bebida

total_gasto = gasto_comida + gasto_bebida
restante = max(0.0, total_gasto - arrecadado)

c1, c2, c3 = st.columns(3)
c1.metric("🍽️ Só Comida (por pessoa)", f"R$ {valor_apenas_comida:.2f}")
c2.metric("🍻 Comida + Bebida (por pessoa)", f"R$ {valor_comida_bebida:.2f}")
c3.metric("💰 Arrecadado", f"R$ {arrecadado:.2f}", delta=f"-R$ {restante:.2f} pendente" if restante > 0 else "Quitado! 🎉")

# -------------------------------------------------------------
# 8. PIX & QR CODE
# -------------------------------------------------------------
st.markdown("---")
st.subheader("💳 Dados do Pix & QR Code")

col_pix1, col_pix2 = st.columns([1, 2])
with col_pix1:
    nome_recebedor = st.text_input("Beneficiário", value="ORGANIZADOR")
with col_pix2:
    chave_pix = st.text_input("Chave Pix", value="seu-pix-aqui", placeholder="CPF, telefone ou e-mail")

opcao_cobranca = st.radio(
    "Escolha o valor para o QR Code:",
    options=["Apenas Comida", "Comida + Bebida"],
    horizontal=True
)

valor_pix = valor_apenas_comida if opcao_cobranca == "Apenas Comida" else valor_comida_bebida

if chave_pix.strip() and chave_pix != "seu-pix-aqui":
    payload_pix = gerar_payload_pix(chave_pix, nome_recebedor, valor_pix)
    img_qr = gerar_imagem_qrcode(payload_pix)

    col_qr, col_txt = st.columns([1, 2])
    with col_qr:
        st.image(img_qr, caption=f"Pix: R$ {valor_pix:.2f}", width=180)
    with col_txt:
        st.write("**Pix Copia e Cola:**")
        st.code(payload_pix, language="text")
else:
    st.warning("Preencha a chave Pix acima para gerar o QR Code.")

# -------------------------------------------------------------
# 9. MENSAGEM PARA O WHATSAPP
# -------------------------------------------------------------
st.markdown("---")
st.subheader("💬 Mensagem para o WhatsApp")

data_formatada = data_evento.strftime("%d/%m/%Y")
hora_formatada = hora_evento.strftime("%H:%M")

lista_nomes = "\n".join([
    f"- {p['nome']} ({p['tipo']}): {'[PAGO ✅]' if p['pago'] else f'R$ {valor_apenas_comida:.2f}' if p['tipo'] == 'Só Comida' else f'R$ {valor_comida_bebida:.2f}'}"
    for p in st.session_state.participantes
]) or "Nenhum participante listado ainda."

msg_zap = f"""🥩 *{titulo}*
📅 *Data:* {data_formatada} às {hora_formatada}

📊 *Valores do Rateio:*
🍽️ *Apenas Comida:* R$ {valor_apenas_comida:.2f}
🍻 *Comida + Bebida:* R$ {valor_comida_bebida:.2f}

👥 *Participantes:*
{lista_nomes}

💳 *Chave Pix:* {chave_pix} ({nome_recebedor})

Favor enviar o comprovante para darmos baixa no rateio! 🔥"""

st.text_area("Copie o texto para colar no grupo:", value=msg_zap, height=220)