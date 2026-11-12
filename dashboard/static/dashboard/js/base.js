const logoutButton = document.getElementById("logoutButton");

if (logoutButton) {
    logoutButton.addEventListener("click", async function () {
        const token = localStorage.getItem("authToken");

        try {
            if (token) {
                const response = await fetch("/accounts/api/logout/", {
                    method: "POST",
                    headers: {
                        "Authorization": `Token ${token}`,
                        "Content-Type": "application/json"
                    }
                });

                if (!response.ok) {
                    alert("Logout failed. Please try again.");
                    return;
                }
            }

            localStorage.removeItem("authToken");
            localStorage.removeItem("userRole");
            window.location.href = "/accounts/login/";
        } catch (error) {
            alert("Unable to connect to the server. Please try again.");
        }
    });
}
