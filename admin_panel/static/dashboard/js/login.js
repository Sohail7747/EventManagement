const loginForm = document.getElementById("loginForm");
    const message = document.getElementById("message");
    const loginButton = document.getElementById("loginButton");
    const loginButtonText = document.getElementById("loginButtonText");
    const passwordInput = document.getElementById("password");
    const togglePassword = document.getElementById("togglePassword");

    function showMessage(text, type) {
        message.className = "alert alert-" + type + " mb-4";
        message.textContent = text;
    }

    togglePassword.addEventListener("click", function () {
        const showPassword = passwordInput.type === "password";

        passwordInput.type = showPassword ? "text" : "password";

        togglePassword.innerHTML = showPassword
            ? '<i class="bi bi-eye-slash"></i>'
            : '<i class="bi bi-eye"></i>';

        togglePassword.setAttribute(
            "aria-label",
            showPassword ? "Hide password" : "Show password"
        );

        togglePassword.setAttribute("aria-pressed", String(showPassword));
    });

    loginForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const payload = {
            email: document.getElementById("email").value.trim(),
            password: passwordInput.value
        };

        loginButton.disabled = true;
        loginButtonText.textContent = "Signing in...";

        showMessage("Checking your credentials...", "info");

        try {
            const response = await fetch("/accounts/api/login/", {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                const errorMessage =
                    data.error ||
                    Object.values(data)
                        .flat()
                        .filter(value => typeof value === "string")
                        .join(" ") ||
                    "Login failed. Please check your details.";

                showMessage(errorMessage, "danger");
                return;
            }

            if (!data.redirect_url) {
                showMessage(
                    "Login succeeded, but no redirect URL was provided.",
                    "warning"
                );
                return;
            }

            if (data.token) {
                localStorage.setItem("authToken", data.token);
            }

            if (data.user && data.user.role) {
                localStorage.setItem("userRole", data.user.role);
            }

            showMessage("Login successful! Redirecting...", "success");

            // Navigate only after the login API returns success.
            window.location.assign(data.redirect_url);

        } catch (error) {
            console.error("Login error:", error);

            showMessage(
                "Unable to connect to the server. Please try again.",
                "danger"
            );
        } finally {
            loginButton.disabled = false;
            loginButtonText.textContent = "Sign In";
        }
    });
