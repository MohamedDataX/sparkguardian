// Admin dashboard — list + revoke licenses. Token kept in-memory only.
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  let token = "";

  const api = (path, opts = {}) =>
    fetch(path, {
      ...opts,
      headers: { Authorization: `Bearer ${token}`, ...(opts.headers || {}) },
    });

  const short = (iso) => (iso ? iso.slice(0, 10) : "—");

  function render(payload) {
    const { licenses, stats } = payload;
    $("#stats").innerHTML = [
      ["Total", stats.total],
      ["Active", stats.active],
      ["Trials", stats.trials],
      ["Paid", stats.paid],
    ]
      .map(([l, n]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`)
      .join("");

    $("#rows").innerHTML = licenses
      .map((l) => {
        const status = l.revoked
          ? '<span class="badge revoked">Revoked</span>'
          : `<span class="badge ${l.type === "trial" ? "trial" : "paid"}">${l.type}</span>`;
        const revokeBtn = l.revoked
          ? ""
          : `<button class="revoke" data-jti="${l.jti}">Revoke</button>`;
        return `<tr>
          <td>${l.name}</td><td>${l.email}</td><td>${status}</td>
          <td>${short(l.created_at)}</td><td>${short(l.expires_at)}</td>
          <td>${l.activations}</td><td>${l.revoked ? "revoked" : "ok"}</td>
          <td>${revokeBtn}</td></tr>`;
      })
      .join("");

    $("#rows").querySelectorAll(".revoke").forEach((btn) =>
      btn.addEventListener("click", async () => {
        if (!confirm("Revoke this license?")) return;
        await api(`/api/admin/licenses/${btn.dataset.jti}/revoke`, { method: "POST" });
        load();
      })
    );
  }

  async function load() {
    const res = await api("/api/admin/licenses");
    if (!res.ok) {
      $("#auth-msg").textContent = "Invalid token.";
      $("#auth-msg").className = "msg err";
      return false;
    }
    render(await res.json());
    $("#auth").hidden = true;
    $("#dash").hidden = false;
    return true;
  }

  $("#login").addEventListener("click", () => {
    token = $("#token").value.trim();
    load();
  });
  $("#token").addEventListener("keydown", (e) => {
    if (e.key === "Enter") $("#login").click();
  });
})();
