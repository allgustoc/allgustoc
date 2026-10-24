// Comportamentos mínimos do painel: atalhos de destino e acompanhamento da busca em andamento.

document.querySelectorAll("[data-fill]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.target);
    input.value = button.dataset.fill;
    input.focus();
  });
});

const status = document.querySelector("[data-status-url]");
if (status) {
  const url = status.dataset.statusUrl;
  const render = (providers) => {
    const list = status.querySelector(".progress-list");
    if (!list) return;
    list.innerHTML = "";
    for (const [key, p] of Object.entries(providers)) {
      const row = document.createElement("div");
      row.className = "progress-row";
      const pct = p.total ? Math.round((100 * p.done) / p.total) : 0;
      const label = document.createElement("strong");
      label.textContent = p.label || key;
      const bar = document.createElement("div");
      bar.className = "bar" + (p.total ? "" : " indeterminate");
      bar.setAttribute("role", "progressbar");
      bar.setAttribute("aria-label", `Progresso ${p.label || key}`);
      bar.setAttribute("aria-valuenow", String(pct));
      bar.setAttribute("aria-valuemin", "0");
      bar.setAttribute("aria-valuemax", "100");
      const fill = document.createElement("span");
      fill.style.width = p.total ? `${pct}%` : "";
      bar.appendChild(fill);
      const count = document.createElement("span");
      count.className = "muted num";
      count.textContent = p.status === "stopped" ? "interrompida" : p.total ? `${p.done} de ${p.total}` : "preparando";
      row.append(label, bar, count);
      list.appendChild(row);
    }
  };
  const poll = async () => {
    try {
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      const data = await resp.json();
      if (!data.running) {
        window.location.reload();
        return;
      }
      render(data.providers || {});
    } catch (err) {
      // Servidor reiniciando: tenta de novo no próximo ciclo.
    }
    setTimeout(poll, 3000);
  };
  setTimeout(poll, 1500);
}
