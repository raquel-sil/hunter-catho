const API_URL = 'https://hunter-catho.vercel.app/api/receber_candidatos_extensao';

let candidatosExtraidos = [];

document.addEventListener('DOMContentLoaded', () => {
  const btnLerTela = document.getElementById('btnLerTela');
  const btnEnviarSelecionados = document.getElementById('btnEnviarSelecionados');
  const listaContainer = document.getElementById('listaContainer');
  const candidatosLista = document.getElementById('candidatosLista');
  const statusDiv = document.getElementById('status');
  const btnMarcarTodos = document.getElementById('btnMarcarTodos');
  const btnDesmarcarTodos = document.getElementById('btnDesmarcarTodos');

  // 1. Ler os candidatos da aba ativa na Catho
  btnLerTela.addEventListener('click', async () => {
    statusDiv.textContent = 'Buscando candidatos na página...';
    statusDiv.style.color = '#9ca3af';
    candidatosLista.innerHTML = '';
    listaContainer.style.display = 'none';

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

      if (!tab || !tab.id) {
        statusDiv.textContent = 'Erro: Nenhuma aba ativa encontrada.';
        statusDiv.style.color = '#ef4444';
        return;
      }

      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extrairDadosCathoDaPagina
      });

      if (!results || !results[0] || !results[0].result || results[0].result.length === 0) {
        statusDiv.textContent = 'Nenhum candidato encontrado. Verifique se os currículos estão visíveis na tela.';
        statusDiv.style.color = '#f59e0b';
        return;
      }

      candidatosExtraidos = results[0].result;
      renderizarLista(candidatosExtraidos);

      listaContainer.style.display = 'flex';
      statusDiv.textContent = `${candidatosExtraidos.length} candidato(s) carregado(s).`;
      statusDiv.style.color = '#10b981';
    } catch (err) {
      console.error(err);
      statusDiv.textContent = 'Erro ao ler a página da Catho.';
      statusDiv.style.color = '#ef4444';
    }
  });

  // 2. Marcar e Desmarcar todos
  if (btnMarcarTodos) {
    btnMarcarTodos.addEventListener('click', () => {
      document.querySelectorAll('.cand-check').forEach(cb => cb.checked = true);
    });
  }

  if (btnDesmarcarTodos) {
    btnDesmarcarTodos.addEventListener('click', () => {
      document.querySelectorAll('.cand-check').forEach(cb => cb.checked = false);
    });
  }

  // 3. Enviar os candidatos selecionados para a Vercel
  btnEnviarSelecionados.addEventListener('click', async () => {
    const checkboxes = document.querySelectorAll('.cand-check:checked');
    const indices = Array.from(checkboxes).map(cb => parseInt(cb.value, 10));

    if (indices.length === 0) {
      statusDiv.textContent = 'Selecione pelo menos um candidato na lista.';
      statusDiv.style.color = '#f59e0b';
      return;
    }

    const candidatosParaEnviar = indices.map(idx => candidatosExtraidos[idx]);

    btnEnviarSelecionados.disabled = true;
    statusDiv.textContent = `Enviando ${candidatosParaEnviar.length} candidato(s)...`;
    statusDiv.style.color = '#9ca3af';

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          candidatos: candidatosParaEnviar
        })
      });

      const resultado = await response.json().catch(() => ({}));

      if (response.ok && resultado.status === 'success') {
        statusDiv.textContent = `Sucesso! ${candidatosParaEnviar.length} enviado(s) ao painel.`;
        statusDiv.style.color = '#10b981';
      } else {
        throw new Error(resultado.message || `Erro no servidor (${response.status})`);
      }
    } catch (err) {
      console.error(err);
      statusDiv.textContent = `Falha no envio: ${err.message}`;
      statusDiv.style.color = '#ef4444';
    } finally {
      btnEnviarSelecionados.disabled = false;
    }
  });

  function renderizarLista(candidatos) {
    candidatosLista.innerHTML = '';
    candidatos.forEach((cand, index) => {
      const item = document.createElement('div');
      item.className = 'candidato-item';

      item.innerHTML = `
        <input type="checkbox" class="cand-check" value="${index}" checked />
        <div class="candidato-info">
          <span class="candidato-nome" title="${cand.nome}">${cand.nome}</span>
          <span class="candidato-cargo" title="${cand.cargo}">${cand.cargo}</span>
        </div>
      `;
      candidatosLista.appendChild(item);
    });
  }
});

// Extração cirúrgica dos cartões de currículo da Catho
function extrairDadosCathoDaPagina() {
  const lista = [];

  // Encontra os blocos que possuem o marcador exclusivo "Experiência:" dos candidatos
  const todosNos = Array.from(document.querySelectorAll('*'));
  const nosExperiencia = todosNos.filter(el => {
    const txt = el.innerText ? el.innerText.trim() : '';
    return txt.startsWith('Experiência:') && el.children.length <= 2;
  });

  nosExperiencia.forEach((expEl, idx) => {
    // Sobe na árvore DOM até o contêiner do cartão do candidato
    let card = expEl.closest('article') || expEl.parentElement;
    for (let i = 0; i < 6; i++) {
      if (card && card.innerText && card.innerText.includes('Selecionar')) {
        break;
      }
      if (card && card.parentElement && card.parentElement !== document.body) {
        card = card.parentElement;
      }
    }

    if (!card) return;

    const textoCompleto = card.innerText || '';
    const linhas = textoCompleto.split('\n').map(l => l.trim()).filter(l => l.length > 0);

    // O nome aparece logo após a palavra "Selecionar" no card
    let nome = '';
    const idxSelecionar = linhas.findIndex(l => l.toLowerCase() === 'selecionar');
    if (idxSelecionar !== -1 && linhas[idxSelecionar + 1]) {
      nome = linhas[idxSelecionar + 1];
    } else {
      // Fallback: procura títulos que não sejam utilitários
      const titulos = card.querySelectorAll('h2, h3, a');
      for (const t of titulos) {
        const txt = t.innerText ? t.innerText.trim() : '';
        if (txt.length > 4 && !txt.toLowerCase().includes('selecionar') && !txt.toLowerCase().includes('mensagem')) {
          nome = txt;
          break;
        }
      }
    }

    // Linha de idade e localização (ex: "43 anos, Solteiro - Parauapebas...")
    let cidade = '';
    const linhaIdade = linhas.find(l => l.includes('anos') || l.includes(' - '));
    if (linhaIdade) {
      cidade = linhaIdade;
    }

    // Texto da experiência
    const expTexto = expEl.innerText.trim();
    const cargo = expTexto.replace(/^Experiência:\s*/i, '').split('\n')[0];

    // Ignora cabeçalhos globais e opções de lote
    if (nome && !nome.toLowerCase().includes('selecionar todos') && !nome.toLowerCase().includes('encontre o candidato')) {
      lista.push({
        id: `catho_${Date.now()}_${idx}`,
        nome: nome,
        cargo: cargo || 'Profissional Catho',
        cidade: cidade || 'Brasil',
        resumo: textoCompleto.substring(0, 500),
        status_ia: 'Pendente',
        data_cadastro: new Date().toISOString()
      });
    }
  });

  // Remove eventuais duplicados pelo nome
  const vistos = new Set();
  return lista.filter(item => {
    if (!item.nome || vistos.has(item.nome)) return false;
    vistos.add(item.nome);
    return true;
  });
}
