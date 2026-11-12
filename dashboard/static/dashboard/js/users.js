const form = document.getElementById("userForm");
const container = document.getElementById("userFormContainer");
const tableBody = document.getElementById("usersTableBody");
const message = document.getElementById("message");
const passwordInput = document.getElementById("user_password");
const saveButton = form.querySelector('button[type="submit"]');

function showMessage(text, error = false) {
    message.textContent = text;
    message.className = error ? "alert alert-danger" : "alert alert-success";
}

function token() {
    return localStorage.getItem("authToken");
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "Authorization": `Token ${token()}`,
            ...(options.headers || {})
        }
    });

    const data = response.status === 204 ? null : await response.json();

    if (!response.ok) {
        const details = data && typeof data === "object"
            ? Object.entries(data).map(([key, value]) =>
                `${key}: ${Array.isArray(value) ? value.join(", ") : value}`
              ).join(" | ")
            : "Request failed.";

        throw new Error(details || "Request failed.");
    }

    return data;
}

async function loadUsers() {
    if (!token()) {
        window.location.href = "/login/";
        return;
    }

    try {
        const data = await api("/api/users/");
        const users = Array.isArray(data) ? data : (data.results || []);
        tableBody.innerHTML = "";

        if (!users.length) {
            tableBody.innerHTML =
                '<tr><td colspan="6" class="text-center">No users found.</td></tr>';
            return;
        }

        users.forEach(user => {
            const row = document.createElement("tr");

            [user.id, user.full_name, user.email, user.phone, user.role]
                .forEach(value => {
                    const cell = document.createElement("td");
                    cell.textContent = value ?? "";
                    row.appendChild(cell);
                });

            const actions = document.createElement("td");

            const editButton = document.createElement("button");
            editButton.type = "button";
            editButton.className = "btn btn-sm btn-warning me-2";
            editButton.textContent = "Edit";
            editButton.addEventListener("click", () => editUser(user));

            const deleteButton = document.createElement("button");
            deleteButton.type = "button";
            deleteButton.className = "btn btn-sm btn-danger";
            deleteButton.textContent = "Delete";
            deleteButton.disabled = user.role === "ADMIN";
            deleteButton.addEventListener("click", () => deleteUser(user));

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

document.getElementById("addUserBtn").addEventListener("click", () => {
    form.reset();

    document.getElementById("user_id").value = "";
    document.getElementById("formTitle").textContent = "Add User";

    passwordInput.value = "";
    passwordInput.required = true;
    passwordInput.placeholder = "Minimum 8 characters";

    document.getElementById("user_email").readOnly = false;

    container.style.display = "block";
    message.className = "alert d-none";
});

document.getElementById("cancelUserBtn").addEventListener("click", () => {
    container.style.display = "none";
});

function editUser(user) {
    form.reset();

    document.getElementById("user_id").value = user.id;
    document.getElementById("full_name").value = user.full_name || "";
    document.getElementById("user_email").value = user.email || "";
    document.getElementById("user_phone").value = user.phone || "";

    document.getElementById("formTitle").textContent = "Edit User";

    passwordInput.value = "";
    passwordInput.required = false;
    passwordInput.placeholder = "Leave blank to keep current password";

    document.getElementById("user_email").readOnly = true;

    container.style.display = "block";
    message.className = "alert d-none";
}
form.addEventListener("submit", async event => {
    event.preventDefault();

    const id = document.getElementById("user_id").value;
    const payload = {
        full_name: document.getElementById("full_name").value.trim(),
        email: document.getElementById("user_email").value.trim(),
        phone: document.getElementById("user_phone").value.trim()
    };

    if (passwordInput.value) {
        payload.password = passwordInput.value;
    }

    if (!id || passwordInput.value) {
        if (passwordInput.value) {
            payload.password = passwordInput.value;
        }
    }

    saveButton.disabled = true;

    try {
        await api(id ? `/api/users/${id}/` : "/api/users/", {
            method: id ? "PATCH" : "POST",
            body: JSON.stringify(payload)
        });

        showMessage(id ? "User updated successfully." : "User created successfully.");
        container.style.display = "none";
        form.reset();
        await loadUsers();
    } catch (error) {
        showMessage(error.message, true);
    } finally {
        saveButton.disabled = false;
    }
});

async function deleteUser(user) {
    if (user.role === "ADMIN") {
        showMessage("The main admin account cannot be deleted here.", true);
        return;
    }

    if (!confirm(`Delete user "${user.full_name}"? This cannot be undone.`)) {
        return;
    }

    try {
        await api(`/api/users/${user.id}/`, { method: "DELETE" });
        showMessage("User deleted successfully.");
        await loadUsers();
    } catch (error) {
        showMessage(error.message, true);
    }
}

document.addEventListener("DOMContentLoaded", loadUsers);
