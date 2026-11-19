(() => {
  // The shell keeps the header and the side menu in place. Each member page is shown in the frame below them.
  const frame = document.getElementById("shellFrame");
  const base = window.ZABAN_BASE || "";

  // The page in the shell's address, without the base path and without the frame marker.
  function currentAddress() {
    return new URLSearchParams(location.search).get("p") || "/student";
  }

  // Shows a member page in the frame and puts it in the address bar, so the shell can be reloaded at the same page.
  function show(address, refreshMenu) {
    const next = new URL(address, location.origin);
    const query = next.search ? `${next.search}&frame=1` : "?frame=1";
    frame.src = Z.url(next.pathname + query);
    history.replaceState(null, "", Z.url(`/app?p=${encodeURIComponent(next.pathname + next.search)}`));
    if (refreshMenu) Z.refreshMenu();
  }

  // A link to a member page opens in the frame. Any other link leaves the shell as usual.
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest ? event.target.closest("a[href]") : null;
    if (!link || link.target === "_blank") return;
    const target = new URL(link.href);
    if (target.origin !== location.origin) return;
    let path = target.pathname;
    if (base && path.startsWith(base)) path = path.slice(base.length);
    if (!Z.isMemberPath(path)) return;
    event.preventDefault();
    show(path + target.search, true);
  });

  // When the page in the frame moves on by itself, the shell's address and menu follow it.
  frame.addEventListener("load", () => {
    let here;
    try {
      here = frame.contentWindow.location;
    } catch (_) {
      return;
    }
    let path = here.pathname;
    if (base && path.startsWith(base)) path = path.slice(base.length);
    if (!Z.isMemberPath(path)) return;
    const params = new URLSearchParams(here.search);
    params.delete("frame");
    const address = path + (params.toString() ? `?${params.toString()}` : "");
    if (address === currentAddress()) return;
    history.replaceState(null, "", Z.url(`/app?p=${encodeURIComponent(address)}`));
    Z.refreshMenu();
  });

  // The shell needs a signed-in visitor. Anyone else goes to sign-in.
  Z.request("GET", "/v1/web/me")
    .then(() => show(currentAddress(), false))
    .catch(() => location.replace(Z.url("/login")));
})();
