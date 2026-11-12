const roleSelect = document.getElementById("role");
    const message = document.getElementById("message");
    const registerButton = document.getElementById("registerButton");
    const registerButtonText = document.getElementById("registerButtonText");
    const registerForm = document.getElementById("registerForm");
    const passwordInput = document.getElementById("password");
    const togglePassword = document.getElementById("togglePassword");

    function showMessage(text, type) {
        message.className = "alert alert-" + type;
        message.textContent = text;
    }

    togglePassword.addEventListener("click", function () {
        const isPassword = passwordInput.type === "password";
        passwordInput.type = isPassword ? "text" : "password";

        togglePassword.innerHTML = isPassword
            ? '<i class="bi bi-eye-slash"></i>'
            : '<i class="bi bi-eye"></i>';

        togglePassword.setAttribute(
            "aria-label",
            isPassword ? "Hide password" : "Show password"
        );
    });

    async function loadRoles() {
        roleSelect.innerHTML = '<option value="">Loading roles...</option>';
        roleSelect.disabled = true;

        try {
            const response = await fetch("/accounts/api/registration-options/");

            if (!response.ok) {
                throw new Error("Could not load roles.");
            }

            const data = await response.json();

            if (!Array.isArray(data.roles)) {
                throw new Error("Invalid registration roles response.");
            }

            roleSelect.innerHTML =
                '<option value="">Select your account type</option>';

            data.roles.forEach(function (role) {
                const option = document.createElement("option");
                option.value = role;

                if (role === "SUB_ADMIN") {
                    option.textContent = "Sub-admin";
                } else {
                    option.textContent =
                        role.charAt(0) + role.slice(1).toLowerCase();
                }

                roleSelect.appendChild(option);
            });

            roleSelect.disabled = false;

        } catch (error) {
            console.error("Role loading error:", error);

            roleSelect.innerHTML =
                '<option value="">Unable to load roles</option>';

            showMessage(
                "Could not load registration roles. Please refresh the page.",
                "danger"
            );
        }
    }

    registerForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const payload = {
            full_name: document.getElementById("name").value.trim(),
            email: document.getElementById("email").value.trim(),
            phone: document.getElementById("phone").value.trim(),
            password: passwordInput.value,
            role: roleSelect.value
        };

        if (!payload.role) {
            showMessage("Please select an account type.", "danger");
            return;
        }

        if (payload.full_name.length > 100) {
            showMessage("Full name must not exceed 100 characters.", "danger");
            return;
        }

        if (payload.password.length < 8) {
            showMessage("Password must contain at least 8 characters.", "danger");
            return;
        }

        registerButton.disabled = true;
        registerButtonText.textContent = "Creating account...";

        try {
            const response = await fetch("/accounts/api/register/", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                showMessage(
                    "Registration successful! Redirecting to login...",
                    "success"
                );

                registerForm.reset();
                await loadRoles();

                window.setTimeout(function () {
                    window.location.href = "/accounts/login/";
                }, 1200);

            } else {
                const errors = Object.entries(data)
                    .map(([field, fieldErrors]) => {
                        const text = Array.isArray(fieldErrors)
                            ? fieldErrors.join(" ")
                            : typeof fieldErrors === "string"
                                ? fieldErrors
                                : JSON.stringify(fieldErrors);

                        return field === "non_field_errors"
                            ? text
                            : field + ": " + text;
                    })
                    .join(" ");

                showMessage(errors || "Registration failed. Please try again.", "danger");
            }

        } catch (error) {
            console.error("Registration error:", error);
            showMessage("Unable to connect to the server. Please try again.", "danger");
        } finally {
            registerButton.disabled = false;
            registerButtonText.textContent = "Create Account";
        }
    });

    loadRoles();
