(function () {
  const params = new URLSearchParams(window.location.search);

  const userId = params.get("user_id") || "–";
  const name = params.get("name") || "Cliente";
  const email = params.get("email") || "sin-email@example.com";
  const amountRaw = params.get("amount") || "0";
  const itemsEncoded = params.get("items") || null;

  // Formatear monto
  const amountNumber = parseFloat(amountRaw) || 0;
  const amountFormatted = amountNumber.toLocaleString("es-AR", {
    style: "currency",
    currency: "ARS",
  });

  // Pintamos datos
  document.getElementById("buyer-name").textContent = name;
  document.getElementById("buyer-email").textContent = email;
  document.getElementById("buyer-id").textContent = userId;
  document.getElementById("order-amount").textContent = amountFormatted;

  // Procesamos los items del carrito
  let items = [];
  if (itemsEncoded) {
    try {
      const decoded = atob(itemsEncoded.replace(/-/g, '+').replace(/_/g, '/'));
      items = JSON.parse(decoded);
    } catch (e) {
      console.error("Error decoding items:", e);
    }
  }

  // Renderizamos items en una tabla
  const table = document.createElement("table");
  table.className = "items-table";

  table.innerHTML = `
    <tr>
      <th>Producto</th>
      <th>Cant.</th>
      <th>Unit.</th>
      <th>Subtotal</th>
    </tr>
  `;

  items.forEach((item) => {
    const row = document.createElement("tr");

    const subtotal = item.unit_price * item.quantity;

    row.innerHTML = `
      <td>${item.name}</td>
      <td>${item.quantity}</td>
      <td>$${item.unit_price.toLocaleString("es-AR")}</td>
      <td>$${subtotal.toLocaleString("es-AR")}</td>
    `;

    table.appendChild(row);
  });

  document.querySelector(".card-right").appendChild(table);

  // Botón demo
  const btnConfirm = document.getElementById("btn-confirm");
  const confirmationMsg = document.getElementById("confirmation-message");

  btnConfirm.addEventListener("click", () => {
    confirmationMsg.hidden = false;
    btnConfirm.disabled = true;
    btnConfirm.textContent = "Pedido confirmado (demo)";
  });
})();
