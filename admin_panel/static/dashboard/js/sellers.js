const form = document.getElementById("sellerForm");
const container = document.getElementById("sellerFormContainer");
const tableBody = document.getElementById("sellerTableBody");
const message = document.getElementById("message");
const emailInput = document.getElementById("seller_email");
const saveButton = document.getElementById("saveSellerBtn");

let sellers = [];
let editingId = null;

function token() {
    return localStorage.getItem("authToken");
}

function showMessage(text, error = false) {
    message.textContent = text;
    message.className = error
        ? "alert alert-danger"
        : "alert alert-success";
}

function hideMessage() {
    message.textContent = "";
    message.className = "alert d-none";
}

async function api(url, options = {}) {
    const headers = {
        "Authorization": `Token ${token()}`,
        ...(options.body ? {"Content-Type": "application/json"} : {}),
        ...(options.headers || {})
    };

    const response = await fetch(url, {
        ...options,
        headers
    });

    const data = response.status === 204
        ? null
        : await response.json().catch(() => ({}));

    if (!response.ok) {
        const details = data && typeof data === "object"
            ? Object.entries(data).map(([key, value]) =>
                `${key}: ${Array.isArray(value) ? value.join(", ") : value}`
              ).join(" | ")
            : "Request failed.";

        throw new Error(details || `Request failed (${response.status}).`);
    }

    return data;
} 


async function loadSellers() {
    try {
        const data = await api("/api/sellers/");
        sellers = Array.isArray(data) ? data : (data.results || []);

        tableBody.innerHTML = "";

        if (sellers.length === 0) {
            tableBody.innerHTML =
                '<tr><td colspan="6" class="text-center">No sellers found.</td></tr>';
            return;
        }

        sellers.forEach(seller => {
            const row = document.createElement("tr");

            [
                seller.id,
                seller.business_name,
                seller.user_email,
                seller.phone || "-",
                seller.address || "-"
            ].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value ?? "";
                row.appendChild(cell);
            });

            const actions = document.createElement("td");

            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "btn btn-sm btn-warning me-2 mb-1";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => editSeller(seller.id));

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "btn btn-sm btn-danger mb-1";
            deleteButton.textContent = "Delete";
            deleteButton.addEventListener("click", () => deleteSeller(seller));

            actions.append(editButton, deleteButton);
            row.appendChild(actions);
            tableBody.appendChild(row);
        });
    } catch (error) {
        tableBody.innerHTML =
            '<tr><td colspan="6" class="text-danger"></td></tr>';
        tableBody.querySelector("td").textContent = error.message;
    }
}


document.getElementById("addSellerBtn").addEventListener("click", async () => {
    resetForm();
    hideMessage();

    try {
        
        container.style.display = "block";
        document.getElementById("formTitle").textContent = "Add Seller";
    } catch (error) {
        showMessage(error.message, true);
    }
});


function editSeller(id) {
    const seller = sellers.find(item => item.id === id);
    if (!seller) return;

    resetForm();
    hideMessage();

    editingId = id;

    document.getElementById("seller_id").value = seller.id;
    document.getElementById("business_name").value =
        seller.business_name || "";
    document.getElementById("seller_email").value =
        seller.user_email || "";
    document.getElementById("seller_phone").value =
        seller.phone || "";
    document.getElementById("seller_address").value =
        seller.address || "";
    document.getElementById("seller_password").value = "";

    document.getElementById("passwordHelp").textContent =
        "Leave blank to keep the current password. Enter a new password to change it.";

    document.getElementById("formTitle").textContent = "Edit Seller";
    saveButton.textContent = "Update Seller";

    container.style.display = "block";
    window.scrollTo({ top: 0, behavior: "smooth" });
}


form.addEventListener("submit", async event => {
    event.preventDefault();

    const email = document.getElementById("seller_email").value.trim();
    const password = document.getElementById("seller_password").value;

    const payload = {
        business_name: document.getElementById("business_name").value.trim(),
        email: email,
        password: password,
        phone: document.getElementById("seller_phone").value.trim(),
        address: document.getElementById("seller_address").value.trim()
    };

    if (!payload.business_name || !payload.email || !payload.address) {
        showMessage("Business name, email, and address are required.", true);
        return;
    }

    if (!editingId && !password) {
        showMessage("Password is required when creating a seller.", true);
        return;
    }

    if (password && password.length < 8) {
        showMessage("Password must contain at least 8 characters.", true);
        return;
    }

    saveButton.disabled = true;

    try {
        if (editingId) {
            // If blank, don't send a password change.
            if (!password) {
                delete payload.password;
            }

            await api(`/api/sellers/${editingId}/`, {
                method: "PATCH",
                body: JSON.stringify(payload)
            });

            showMessage("Seller updated successfully.");
        } else {
            await api("/api/sellers/", {
                method: "POST",
                body: JSON.stringify(payload)
            });

            showMessage("Seller account and business profile created successfully.");
        }

        resetForm();
        await loadSellers();
    } catch (error) {
        showMessage(error.message, true);
    } finally {
        saveButton.disabled = false;
    }
});

async function deleteSeller(seller) {
    if (!confirm(
        `Delete the business profile "${seller.business_name}"? The login account will remain.`
    )) {
        return;
    }

    try {
        await api(`/api/sellers/${seller.id}/`, {method: "DELETE"});

        showMessage("Seller business profile deleted successfully.");
        resetForm();
        await loadSellers();
    } catch (error) {
        showMessage(error.message, true);
    }
}


function resetForm() {
    form.reset();
    editingId = null;

    document.getElementById("seller_id").value = "";
    document.getElementById("formTitle").textContent = "Add Seller";
    document.getElementById("passwordHelp").textContent =
        "Required when creating a seller. Minimum 8 characters.";

    saveButton.textContent = "Save Seller";
    container.style.display = "none";
}

document.getElementById("addSellerBtn").addEventListener("click", () => {
    resetForm();
    hideMessage();

    container.style.display = "block";
    document.getElementById("formTitle").textContent = "Add Seller";

    window.scrollTo({ top: 0, behavior: "smooth" });
});

document.getElementById("cancelSellerBtn").addEventListener("click", () => {
    resetForm();
    hideMessage();
});

document.addEventListener("DOMContentLoaded", loadSellers);
