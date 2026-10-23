const form = document.getElementById("login-form");
const errorMessage = document.getElementById("login-error");
const button = document.getElementById("login-button");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  button.disabled = true;

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        usuario: document.getElementById("usuario").value.trim(),
        contrasena: document.getElementById("contrasena").value,
      }),
      cache: "no-store",
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.detail || "No se pudo iniciar sesión.");
    }

    const next = new URLSearchParams(location.search).get("next");
    location.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard/");
  } catch (error) {
    errorMessage.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
