// =====================================
// SMART LIBRARY WEBSITE
// =====================================

// Explore Library button
document
    .querySelector(".primary-btn")
    .addEventListener("click", function () {

        document
            .querySelector("#features")
            .scrollIntoView({
                behavior: "smooth"
            });

    });


// AI Assistant button
document
    .querySelector(".secondary-btn")
    .addEventListener("click", function () {

        alert(
            "🤖 AI Assistant will be connected in the next step!"
        );

    });


// Login button
document
    .querySelector(".login-btn")
    .addEventListener("click", function () {

        alert(
            "🔐 Login system will be added soon!"
        );

    });