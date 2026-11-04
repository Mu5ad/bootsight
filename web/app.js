const $ = (id) => document.getElementById(id);
let imagen = null;

const ETIQUETA_FASE = {
  power: "alimentación", post: "POST", bootloader: "arranque",
  kernel: "kernel", driver: "controlador", os_init: "sistema",
  desktop: "escritorio", unknown: "sin determinar",
};

fetch("/api/health").then(r => r.json()).then(h => {
  $("meta").textContent = `${h.model}${h.mock ? " · mock" : ""}`;
}).catch(() => { $("meta").textContent = "sin conexión"; });

$("foto").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const lector = new FileReader();
  lector.onload = () => {
    imagen = String(lector.result).split(",")[1];
    $("preview").src = lector.result;
    $("drop").classList.add("lleno");
    $("dropTxt").hidden = true;
    $("go").disabled = false;
  };
  lector.readAsDataURL(f);
});

$("go").addEventListener("click", async () => {
  if (!imagen) return;
  $("go").disabled = true;
  $("go").textContent = "Leyendo la pantalla…";
  try {
    const r = await fetch("/api/diagnose", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_b64: imagen, notes: $("notas").value, locale: "es" }),
    });
    const datos = await r.json();
    if (!r.ok) throw new Error(datos.detail || r.statusText);
    pinta(datos);
  } catch (e) {
    const caja = document.getElementById("errbox") || document.createElement("div");
    caja.id = "errbox";
    caja.className = "errbox";
    caja.textContent = "No se pudo diagnosticar: " + e.message;
    document.querySelector("main").prepend(caja);
  } finally {
    $("go").disabled = false;
    $("go").textContent = "Diagnosticar";
  }
});

function pinta(d) {
  const g = d.diagnosis, p = d.plan;
  $("out").hidden = false;
  $("fase").textContent = ETIQUETA_FASE[g.boot_phase] || g.boot_phase;
  $("conf").textContent = { high: "confianza alta", medium: "confianza media", low: "confianza baja" }[g.confidence];
  $("conf").className = "pill conf " + g.confidence;
  $("mockTag").hidden = !d.mock;
  $("estado").textContent = g.machine_state;

  $("causas").innerHTML = (g.likely_causes || []).map(c => `<li>${esc(c)}</li>`).join("");

  $("ver").innerHTML = (g.evidence || []).map(e => `
    <div class="ev">
      <code>${esc(e.text)}</code>
      <span>${esc(e.meaning)}</span>
    </div>`).join("");

  if ((g.cannot_see || []).length) {
    $("nolisto").hidden = false;
    $("nolisto").innerHTML = `<strong>No se puede ver en la foto</strong><ul>${g.cannot_see.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
  } else { $("nolisto").hidden = true; }

  $("resumen").textContent = p.summary || "";
  $("pasos").innerHTML = (p.steps || []).map(s => {
    const cmd = s.command ? `
      <div class="cmd ${s.destructive ? "peligro" : ""}">
        <code>${esc(s.command.command)}</code>
        <button data-cmd="${esc(s.command.command)}" data-shell="${esc(s.command.shell)}" data-ro="${s.command.read_only && !s.destructive}">Ejecutar</button>
      </div>
      ${s.command.expected_output ? `<small>esperado: ${esc(s.command.expected_output)}</small>` : ""}
      ${s.command.if_not_this ? `<small class="alerta">si no: ${esc(s.command.if_not_this)}</small>` : ""}
    ` : "";
    return `<li><h3>${s.order}. ${esc(s.title)}</h3><p>${esc(s.rationale)}</p>${cmd}</li>`;
  }).join("");

  if ((p.stop_if || []).length) {
    $("stop").hidden = false;
    $("stop").innerHTML = `<strong>Para y no sigas si…</strong><ul>${p.stop_if.map(x => `<li>${esc(x)}</li>`).join("")}</ul>`;
  } else { $("stop").hidden = true; }

  $("pasos").querySelectorAll("button[data-cmd]").forEach(b => {
    b.addEventListener("click", async () => {
      b.disabled = true;
      const r = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: b.dataset.cmd, shell: b.dataset.shell, read_only: b.dataset.ro === "true" }),
      });
      const j = await r.json();
      b.textContent = r.ok ? (j.executed ? `rc=${j.rc}` : "validado") : "bloqueado";
      if (!r.ok) b.classList.add("bloqueado");
    });
  });

  $("out").scrollIntoView({ behavior: "smooth", block: "start" });
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Modo demo: ?demo=1 carga la muestra y lanza el diagnóstico solo.
if (new URLSearchParams(location.search).get("demo") === "1") {
  fetch("/samples/bios-no-bootable.jpg")
    .then(r => r.blob())
    .then(async (blob) => {
      const dataUrl = await new Promise((res) => {
        const fr = new FileReader();
        fr.onload = () => res(String(fr.result));
        fr.readAsDataURL(blob);
      });
      imagen = dataUrl.split(",")[1];
      $("preview").src = dataUrl;
      $("drop").classList.add("lleno");
      $("dropTxt").hidden = true;
      $("notas").value = "El cliente oye el ventilador pero no arranca. El disco hace un clic repetido.";
      $("go").disabled = false;
      $("go").click();
    });
}
