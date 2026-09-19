let selectedRole = null;
let currentUser = null;
let currentStatusApplications = [];
let selectedStatusApplicationId = null;
let posterApplicationsCache = [];
let applicationHistoryCache = [];


/* =========================================================
   BASIC HELPERS
========================================================= */

function $(id) {
    return document.getElementById(id);
}

function escapeHTML(value) {
    if (value === null || value === undefined) return "";

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeHtml(value) {
    return escapeHTML(value);
}

function showToast(message) {
    const toast = $("toast");
    const toastMessage = $("toastMessage");

    if (!toast || !toastMessage) return;

    toastMessage.textContent = message;
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}

function showValidation(elementId, valid, message = "") {
    const element = $(elementId);

    if (!element) return;

    if (valid) {
        element.innerHTML = `
            <div class="validation-message validation-success">
                <span class="validation-icon">✓</span>
                <span>${escapeHTML(message || "Looks good")}</span>
            </div>
        `;
    } else {
        element.innerHTML = `
            <div class="validation-message validation-error">
                <span class="validation-icon">✕</span>
                <span>${escapeHTML(message || "This field is required")}</span>
            </div>
        `;
    }
}

function markInput(inputId, valid) {
    const input = $(inputId);

    if (!input) return;

    input.classList.remove(
        "form-field-error",
        "form-field-success"
    );

    input.classList.add(
        valid
            ? "form-field-success"
            : "form-field-error"
    );
}

function showErrorBox(id, message) {
    const box = $(id);

    if (!box) return;

    box.textContent = message;
    box.classList.add("show");
}

function hideErrorBox(id) {
    const box = $(id);

    if (!box) return;

    box.textContent = "";
    box.classList.remove("show");
}


/* =========================================================
   USER ID / OWNERSHIP HELPERS
========================================================= */

function getCurrentUserId() {
    if (!currentUser) return null;

    return (
        currentUser.id ??
        currentUser.user_id ??
        currentUser.userId ??
        null
    );
}

function getCurrentUserEmail() {
    if (!currentUser) return "";

    return String(
        currentUser.email || ""
    ).trim().toLowerCase();
}

function sameValue(a, b) {
    if (
        a === null ||
        a === undefined ||
        b === null ||
        b === undefined
    ) {
        return false;
    }

    return String(a) === String(b);
}

function applicationBelongsToCurrentUser(application) {
    if (!currentUser || !application) return false;

    const currentId = getCurrentUserId();
    const currentEmail = getCurrentUserEmail();

    const applicant =
        application.applicant ||
        application.user ||
        application.seeker ||
        {};

    const applicantId =
        application.user_id ??
        application.userId ??
        application.seeker_id ??
        application.applicant_id ??
        applicant.id ??
        applicant.user_id ??
        applicant.userId ??
        null;

    const applicantEmail = String(
        application.email ??
        application.applicant_email ??
        application.seeker_email ??
        applicant.email ??
        ""
    ).trim().toLowerCase();

    /*
       If the backend supplies an explicit user ID,
       use it as the strongest ownership check.
    */
    if (currentId !== null && applicantId !== null) {
        return sameValue(currentId, applicantId);
    }

    /*
       Otherwise compare email.
    */
    if (currentEmail && applicantEmail) {
        return currentEmail === applicantEmail;
    }

    /*
       If the API has already returned a session-scoped
       record and does not expose ownership fields,
       keep the record.
    */
    return true;
}

function notificationBelongsToCurrentUser(notification) {
    if (!currentUser || !notification) return false;

    const currentId = getCurrentUserId();
    const currentEmail = getCurrentUserEmail();

    const recipient =
        notification.recipient ||
        notification.user ||
        {};

    const notificationUserId =
        notification.user_id ??
        notification.userId ??
        notification.recipient_id ??
        notification.recipient_user_id ??
        recipient.id ??
        recipient.user_id ??
        recipient.userId ??
        null;

    const notificationEmail = String(
        notification.email ??
        notification.user_email ??
        notification.recipient_email ??
        recipient.email ??
        ""
    ).trim().toLowerCase();

    if (
        currentId !== null &&
        notificationUserId !== null
    ) {
        return sameValue(
            currentId,
            notificationUserId
        );
    }

    if (
        currentEmail &&
        notificationEmail
    ) {
        return (
            currentEmail ===
            notificationEmail
        );
    }

    /*
       If the backend already scopes /api/notifications
       to the logged-in session, allow it.
    */
    return true;
}


/* =========================================================
   ROLE / AUTH
========================================================= */

function chooseRole(role) {
    selectedRole = role;

    $("startPage").classList.add("hidden");
    $("authPage").classList.remove("hidden");

    $("selectedRoleText").textContent =
        role === "job_seeker"
            ? "Job Seeker"
            : "Job Poster";

    $("authTitle").textContent =
        role === "job_seeker"
            ? "Job Seeker Login"
            : "Employer Login";

    $("authSubtitle").textContent =
        role === "job_seeker"
            ? "Welcome back. Find your next opportunity."
            : "Welcome back. Find your next great hire.";

    showLogin();
}

function backToStart() {
    $("authPage").classList.add("hidden");
    $("startPage").classList.remove("hidden");

    selectedRole = null;
}

function showLogin() {
    $("loginForm").classList.remove("hidden");
    $("signupForm").classList.add("hidden");

    $("loginTab").classList.add("active");
    $("signupTab").classList.remove("active");

    hideErrorBox("loginError");
}

function showSignup() {
    $("loginForm").classList.add("hidden");
    $("signupForm").classList.remove("hidden");

    $("loginTab").classList.remove("active");
    $("signupTab").classList.add("active");

    hideErrorBox("signupError");
}


/* =========================================================
   LOAD USER PORTAL
========================================================= */

async function loadUserPortal() {
    if (!currentUser) return;

    /*
       Clear old cached information whenever a different
       account enters the portal.
    */
    currentStatusApplications = [];
    applicationHistoryCache = [];
    posterApplicationsCache = [];

    if (currentUser.role === "job_seeker") {

        $("seekerPage").classList.remove("hidden");
        $("posterPage").classList.add("hidden");

        /*
           IMPORTANT:
           These are awaited so the new user's data finishes
           loading before another user's old information can
           remain visible.
        */
        await loadJobs();
        await loadApplicationHistory();
        await loadApplicationStatus();
        await loadFavorites();
        await loadNotifications();

    } else {

        $("posterPage").classList.remove("hidden");
        $("seekerPage").classList.add("hidden");

        await loadMyJobs();
        await loadPosterApplications();
        await loadNotifications();
    }
}


/* =========================================================
   LOGIN
========================================================= */

async function login() {

    hideErrorBox("loginError");

    const email =
        $("loginEmail").value.trim();

    const password =
        $("loginPassword").value;

    let valid = true;

    if (!email) {

        markInput("loginEmail", false);

        showValidation(
            "loginEmailValidation",
            false,
            "Email is required."
        );

        valid = false;

    } else {

        markInput("loginEmail", true);

        showValidation(
            "loginEmailValidation",
            true,
            "Email entered."
        );
    }

    if (!password) {

        markInput("loginPassword", false);

        showValidation(
            "loginPasswordValidation",
            false,
            "Password is required."
        );

        valid = false;

    } else {

        markInput("loginPassword", true);

        showValidation(
            "loginPasswordValidation",
            true,
            "Password entered."
        );
    }

    if (!valid) return;

    try {

        const response = await fetch(
            "/api/login",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    email,
                    password,
                    role: selectedRole
                })
            }
        );

        const data = await response.json();

        if (!response.ok || !data.success) {

            markInput(
                "loginPassword",
                false
            );

            showValidation(
                "loginPasswordValidation",
                false,
                data.message ||
                "Incorrect password."
            );

            showErrorBox(
                "loginError",
                data.message ||
                "Login failed."
            );

            return;
        }

        currentUser = data.user;

        $("authPage").classList.add("hidden");
        $("startPage").classList.add("hidden");

        $("welcomeUser").textContent =
            "Welcome, " +
            (currentUser.name || "");

        $("logoutBtn").style.display =
            "inline-flex";

        await loadUserPortal();

        showToast("Login successful.");

    } catch (error) {

        console.error(
            "Login error:",
            error
        );

        showErrorBox(
            "loginError",
            "Unable to connect to the server."
        );
    }
}


/* =========================================================
   SIGNUP
========================================================= */

async function signup() {

    hideErrorBox("signupError");

    const name =
        $("signupName").value.trim();

    const email =
        $("signupEmail").value.trim();

    const password =
        $("signupPassword").value;

    let valid = true;

    if (!name) {

        markInput(
            "signupName",
            false
        );

        showValidation(
            "signupNameValidation",
            false,
            "Full name is required."
        );

        valid = false;

    } else {

        markInput(
            "signupName",
            true
        );

        showValidation(
            "signupNameValidation",
            true,
            "Name entered."
        );
    }

    if (!email) {

        markInput(
            "signupEmail",
            false
        );

        showValidation(
            "signupEmailValidation",
            false,
            "Email is required."
        );

        valid = false;

    } else if (!email.includes("@")) {

        markInput(
            "signupEmail",
            false
        );

        showValidation(
            "signupEmailValidation",
            false,
            "Enter a valid email."
        );

        valid = false;

    } else {

        markInput(
            "signupEmail",
            true
        );

        showValidation(
            "signupEmailValidation",
            true,
            "Valid email."
        );
    }

    if (!password) {

        markInput(
            "signupPassword",
            false
        );

        showValidation(
            "signupPasswordValidation",
            false,
            "Password is required."
        );

        valid = false;

    } else if (password.length < 4) {

        markInput(
            "signupPassword",
            false
        );

        showValidation(
            "signupPasswordValidation",
            false,
            "Password must contain at least 4 characters."
        );

        valid = false;

    } else {

        markInput(
            "signupPassword",
            true
        );

        showValidation(
            "signupPasswordValidation",
            true,
            "Password looks good."
        );
    }

    if (!valid) return;

    try {

        const response = await fetch(
            "/api/signup",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    name,
                    email,
                    password,
                    role: selectedRole
                })
            }
        );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showErrorBox(
                "signupError",
                data.message ||
                "Unable to create account."
            );

            return;
        }

        currentUser = data.user;

        $("authPage").classList.add(
            "hidden"
        );

        $("startPage").classList.add(
            "hidden"
        );

        $("welcomeUser").textContent =
            "Welcome, " +
            (currentUser.name || "");

        $("logoutBtn").style.display =
            "inline-flex";

        await loadUserPortal();

        showToast(
            "Account created successfully."
        );

    } catch (error) {

        console.error(
            "Signup error:",
            error
        );

        showErrorBox(
            "signupError",
            "Unable to connect to the server."
        );
    }
}


/* =========================================================
   LOGOUT
========================================================= */

async function logout() {

    try {

        await fetch(
            "/api/logout",
            {
                method: "POST"
            }
        );

    } catch (error) {

        console.error(error);
    }

    currentUser = null;
    currentStatusApplications = [];
    applicationHistoryCache = [];
    posterApplicationsCache = [];

    if ($("logoutBtn"))
        $("logoutBtn").style.display =
            "none";

    if ($("welcomeUser"))
        $("welcomeUser").textContent = "";

    $("seekerPage").classList.add(
        "hidden"
    );

    $("posterPage").classList.add(
        "hidden"
    );

    $("authPage").classList.add(
        "hidden"
    );

    $("startPage").classList.remove(
        "hidden"
    );

    showToast(
        "Logged out successfully."
    );
}


/* =========================================================
   DASHBOARD NAVIGATION
========================================================= */

function showSeekerSection(
    sectionId,
    clickedButton
) {

    document
        .querySelectorAll(
            "#seekerPage .seeker-content-section"
        )
        .forEach(section => {
            section.classList.add(
                "hidden-section"
            );
        });

    const section = $(sectionId);

    if (section) {
        section.classList.remove(
            "hidden-section"
        );
    }

    document
        .querySelectorAll(
            "#seekerPage .dashboard-nav-btn"
        )
        .forEach(btn => {
            btn.classList.remove(
                "active"
            );
        });

    if (clickedButton) {
        clickedButton.classList.add(
            "active"
        );
    }
}

function showPosterSection(
    sectionId,
    clickedButton
) {

    document
        .querySelectorAll(
            "#posterPage .poster-content-section"
        )
        .forEach(section => {
            section.classList.add(
                "hidden-section"
            );
        });

    const section = $(sectionId);

    if (section) {
        section.classList.remove(
            "hidden-section"
        );
    }

    document
        .querySelectorAll(
            "#posterPage .dashboard-nav-btn"
        )
        .forEach(btn => {
            btn.classList.remove(
                "active"
            );
        });

    if (clickedButton) {
        clickedButton.classList.add(
            "active"
        );
    }
}

function openNotifications() {

    if (!currentUser) return;

    if (
        currentUser.role ===
        "job_seeker"
    ) {

        showSeekerSection(
            "seekerNotifications"
        );

    } else {

        showPosterSection(
            "posterNotifications"
        );
    }

    markNotificationsRead();
}


/* =========================================================
   JOB SEARCH
========================================================= */

async function loadJobs() {

    try {

        const response =
            await fetch("/api/jobs");

        const data =
            await response.json();

        renderJobs(
            "jobsContainer",
            data.jobs || []
        );

    } catch (error) {

        console.error(
            "Load jobs error:",
            error
        );

        if ($("jobsContainer")) {

            $("jobsContainer").innerHTML =
                "<p>Unable to load jobs.</p>";
        }
    }
}

async function searchJobs() {

    const category =
        $("jobSearchCategory")
            ? $("jobSearchCategory")
                .value.trim()
            : "";

    const location =
        $("jobSearchLocation")
            ? $("jobSearchLocation")
                .value.trim()
            : "";

    const salary =
        $("jobSearchSalary")
            ? $("jobSearchSalary")
                .value.trim()
            : "";

    const params =
        new URLSearchParams();

    if (category)
        params.append(
            "category",
            category
        );

    if (location)
        params.append(
            "location",
            location
        );

    if (salary)
        params.append(
            "salary",
            salary
        );

    try {

        const response =
            await fetch(
                "/api/jobs?" +
                params.toString()
            );

        const data =
            await response.json();

        renderJobs(
            "jobsContainer",
            data.jobs || []
        );

    } catch (error) {

        console.error(error);

        showToast(
            "Unable to search jobs."
        );
    }
}


/* =========================================================
   FAVORITES
========================================================= */

function isJobFavorite(jobId) {

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {
        return false;
    }

    const favorites =
        Array.isArray(
            currentUser.favorites
        )
            ? currentUser.favorites
            : [];

    return favorites
        .map(Number)
        .includes(Number(jobId));
}

async function toggleFavorite(jobId) {

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {

        showToast(
            "Please login as a job seeker to save favorites."
        );

        return;
    }

    try {

        const response =
            await fetch(
                `/api/jobs/${jobId}/favorite`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    }
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to update favorite."
            );

            return;
        }

        currentUser.favorites =
            Array.isArray(
                data.favorites
            )
                ? data.favorites.map(Number)
                : [];

        await loadJobs();
        await loadFavorites();

        showToast(
            data.message ||
            "Favorite updated."
        );

    } catch (error) {

        console.error(
            "Favorite error:",
            error
        );

        showToast(
            "Unable to update favorite."
        );
    }
}

async function loadFavorites() {

    const container =
        $("favoritesContainer");

    if (!container) return;

    try {

        const response =
            await fetch(
                "/api/favorites",
                {
                    method: "GET"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            container.innerHTML = `
                <div class="empty-state">
                    <div>❤️</div>
                    <h3>Unable to load favorites</h3>
                    <p>
                        ${escapeHTML(
                            data.message ||
                            "Please try again."
                        )}
                    </p>
                </div>
            `;

            return;
        }

        if (currentUser) {

            currentUser.favorites =
                Array.isArray(
                    data.favorites
                )
                    ? data.favorites.map(Number)
                    : [];
        }

        const jobs =
            Array.isArray(data.jobs)
                ? data.jobs
                : [];

        if (!jobs.length) {

            container.innerHTML = `
                <div class="empty-state">
                    <div>❤️</div>
                    <h3>No favorite jobs</h3>
                    <p>
                        Jobs you save as favorites
                        will appear here.
                    </p>
                </div>
            `;

            return;
        }

        container.innerHTML =
            jobs.map(job => `
                <div class="job-card">

                    <div class="job-card-top">

                        <div class="job-card-icon">
                            💼
                        </div>

                        <button
                            class="favorite-button is-favorite"
                            title="Remove from favorites"
                            onclick="toggleFavorite(${job.id})">

                            ❤️

                        </button>

                    </div>

                    <span class="small-label">
                        ${escapeHTML(
                            job.category || "JOB"
                        )}
                    </span>

                    <h3>
                        ${escapeHTML(
                            job.title ||
                            "Untitled Job"
                        )}
                    </h3>

                    <p class="job-company">
                        ${escapeHTML(
                            job.company ||
                            "Company not provided"
                        )}
                    </p>

                    <div class="job-meta">

                        <span>
                            📍
                            ${escapeHTML(
                                job.location ||
                                "Not provided"
                            )}
                        </span>

                        <span>
                            💰 Rs.
                            ${escapeHTML(
                                job.salary ||
                                "Negotiable"
                            )}
                        </span>

                    </div>

                    <div class="job-card-buttons">

                        <button
                            class="small-btn"
                            onclick="openJobModal(${job.id})">

                            View Details

                        </button>

                        <button
                            class="main-btn apply-now-btn"
                            onclick="openApplyModal(${job.id})">

                            Apply Now →

                        </button>

                    </div>

                </div>
            `).join("");

    } catch (error) {

        console.error(
            "Favorites error:",
            error
        );

        container.innerHTML = `
            <div class="empty-state">
                <div>⚠️</div>
                <h3>Unable to load favorites</h3>
                <p>Please try again.</p>
            </div>
        `;
    }
}


/* =========================================================
   RENDER JOBS
========================================================= */

function renderJobs(
    containerId,
    jobs,
    showApply = true
) {

    const container =
        $(containerId);

    if (!container) return;

    if (!jobs.length) {

        container.innerHTML = `
            <div class="empty-state">
                <div>📭</div>
                <h3>No jobs found</h3>
                <p>Try another search.</p>
            </div>
        `;

        return;
    }

    const isPosterView =
        !showApply;

    container.innerHTML =
        jobs.map(job => {

            const favorite =
                isJobFavorite(job.id);

            return `
                <div class="job-card">

                    <div class="job-card-top">

                        <div class="job-card-icon">
                            💼
                        </div>

                        ${
                            !isPosterView
                            ? `
                                <button
                                    class="favorite-button ${
                                        favorite
                                            ? "is-favorite"
                                            : ""
                                    }"
                                    title="${
                                        favorite
                                            ? "Remove from favorites"
                                            : "Add to favorites"
                                    }"
                                    onclick="toggleFavorite(${job.id})">

                                    ${
                                        favorite
                                            ? "❤️"
                                            : "♡"
                                    }

                                </button>
                            `
                            : ""
                        }

                    </div>

                    <span class="small-label">
                        ${escapeHTML(
                            job.category ||
                            "JOB"
                        )}
                    </span>

                    <h3>
                        ${escapeHTML(
                            job.title ||
                            "Untitled Job"
                        )}
                    </h3>

                    <p class="job-company">
                        ${escapeHTML(
                            job.company ||
                            "Company not provided"
                        )}
                    </p>

                    <div class="job-meta">

                        <span>
                            📍
                            ${escapeHTML(
                                job.location ||
                                "Not provided"
                            )}
                        </span>

                        <span>
                            💰 Rs.
                            ${escapeHTML(
                                job.salary ||
                                "Negotiable"
                            )}
                        </span>

                    </div>

                    ${
                        isPosterView
                        ? `
                            <div class="job-card-buttons">

                                <button
                                    class="small-btn"
                                    onclick="deleteJob(${job.id})">

                                    🗑 Delete Job

                                </button>

                            </div>
                        `
                        : `
                            <div class="job-card-buttons">

                                <button
                                    class="small-btn"
                                    onclick="openJobModal(${job.id})">

                                    View Details

                                </button>

                                ${
                                    currentUser &&
                                    currentUser.role ===
                                    "job_seeker"
                                    ? `
                                        <button
                                            class="main-btn apply-now-btn"
                                            onclick="openApplyModal(${job.id})">

                                            Apply Now →

                                        </button>
                                    `
                                    : ""
                                }

                            </div>
                        `
                    }

                </div>
            `;
        }).join("");
}


/* =========================================================
   JOB DETAILS
========================================================= */

async function openJobModal(jobId) {

    try {

        const response =
            await fetch(
                `/api/jobs/${jobId}`
            );

        const data =
            await response.json();

        if (!data.success) {

            showToast(
                data.message ||
                "Unable to load job."
            );

            return;
        }

        const job = data.job;

        $("jobModalContent").innerHTML = `
            <span class="small-label">
                ${escapeHTML(
                    job.category || ""
                )}
            </span>

            <h2>
                ${escapeHTML(
                    job.title || ""
                )}
            </h2>

            <h4>
                ${escapeHTML(
                    job.company || ""
                )}
            </h4>

            <div class="job-detail-list">

                <div>
                    <strong>Location</strong>
                    <span>
                        ${escapeHTML(
                            job.location || ""
                        )}
                    </span>
                </div>

                <div>
                    <strong>Salary</strong>
                    <span>
                        Rs.
                        ${escapeHTML(
                            job.salary ||
                            "Negotiable"
                        )}
                    </span>
                </div>

            </div>

            <h3>Job Description</h3>

            <p class="job-description">
                ${escapeHTML(
                    job.description || ""
                )}
            </p>

            ${
                (
                    !currentUser ||
                    currentUser.role ===
                    "job_seeker"
                )
                ? `
                    <button
                        class="main-btn apply-now-btn"
                        onclick="
                            closeJobModal();
                            openApplyModal(${job.id});
                        ">

                        Apply for this Job →

                    </button>
                `
                : ""
            }
        `;

        $("jobModal").classList.remove(
            "hidden"
        );

    } catch (error) {

        console.error(error);

        showToast(
            "Unable to load job."
        );
    }
}

function closeJobModal() {

    if ($("jobModal")) {
        $("jobModal").classList.add(
            "hidden"
        );
    }
}


/* =========================================================
   APPLY MODAL
========================================================= */

async function openApplyModal(jobId) {

    if (
        currentUser &&
        currentUser.role !==
        "job_seeker"
    ) {

        showToast(
            "Job providers cannot apply for jobs."
        );

        return;
    }

    if (!currentUser) {

        showToast(
            "Please login as a job seeker first."
        );

        return;
    }

    $("applyJobId").value =
        jobId;

    hideErrorBox(
        "applyError"
    );

    $("applyName").value =
        currentUser.name || "";

    $("applyEmail").value =
        currentUser.email || "";

    $("applyContact").value = "";
    $("applyIntroduction").value = "";
    $("applyResumeFile").value = "";

    $("applyModal").classList.remove(
        "hidden"
    );
}

function closeApplyModal() {

    if ($("applyModal")) {
        $("applyModal").classList.add(
            "hidden"
        );
    }
}


/* =========================================================
   SUBMIT APPLICATION
========================================================= */

async function submitApplication() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {

        showToast(
            "Please login as a job seeker."
        );

        return;
    }

    hideErrorBox(
        "applyError"
    );

    const jobId =
        $("applyJobId").value;

    const name =
        $("applyName").value.trim();

    const email =
        $("applyEmail").value.trim();

    const contact =
        $("applyContact").value.trim();

    const introduction =
        $("applyIntroduction")
            .value.trim();

    const resume =
        $("applyResumeFile").files[0];

    let valid = true;

    if (!name) {

        markInput(
            "applyName",
            false
        );

        showValidation(
            "applyNameValidation",
            false,
            "Your name is required."
        );

        valid = false;

    } else {

        markInput(
            "applyName",
            true
        );

        showValidation(
            "applyNameValidation",
            true,
            "Name entered."
        );
    }

    if (
        !email ||
        !email.includes("@")
    ) {

        markInput(
            "applyEmail",
            false
        );

        showValidation(
            "applyEmailValidation",
            false,
            "Enter a valid email."
        );

        valid = false;

    } else {

        markInput(
            "applyEmail",
            true
        );

        showValidation(
            "applyEmailValidation",
            true,
            "Valid email."
        );
    }

    if (!contact) {

        markInput(
            "applyContact",
            false
        );

        showValidation(
            "applyContactValidation",
            false,
            "Contact number is required."
        );

        valid = false;

    } else {

        markInput(
            "applyContact",
            true
        );

        showValidation(
            "applyContactValidation",
            true,
            "Contact number entered."
        );
    }

    if (!introduction) {

        markInput(
            "applyIntroduction",
            false
        );

        showValidation(
            "applyIntroductionValidation",
            false,
            "Please introduce yourself."
        );

        valid = false;

    } else {

        markInput(
            "applyIntroduction",
            true
        );

        showValidation(
            "applyIntroductionValidation",
            true,
            "Introduction added."
        );
    }

    if (!resume) {

        markInput(
            "applyResumeFile",
            false
        );

        showValidation(
            "applyResumeValidation",
            false,
            "Resume is required."
        );

        valid = false;

    } else {

        markInput(
            "applyResumeFile",
            true
        );

        showValidation(
            "applyResumeValidation",
            true,
            "Resume selected."
        );
    }

    if (!valid) return;

    const formData =
        new FormData();

    formData.append(
        "name",
        name
    );

    formData.append(
        "email",
        email
    );

    formData.append(
        "contact",
        contact
    );

    formData.append(
        "introduction",
        introduction
    );

    formData.append(
        "resume",
        resume
    );

    try {

        const response =
            await fetch(
                `/api/jobs/${jobId}/apply`,
                {
                    method: "POST",
                    body: formData
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showErrorBox(
                "applyError",
                data.message ||
                "Unable to submit application."
            );

            return;
        }

        closeApplyModal();

        showToast(
            "Application submitted successfully."
        );

        /*
           IMPORTANT:
           Reload only the currently logged-in
           user's application information.
        */
        await loadApplicationHistory();
        await loadApplicationStatus();
        await loadNotifications();

    } catch (error) {

        console.error(
            "Submit application error:",
            error
        );

        showErrorBox(
            "applyError",
            "Unable to connect to the server."
        );
    }
}


/* =========================================================
   APPLICATION HISTORY
========================================================= */

async function loadApplicationHistory() {

    const container =
        $("applicationHistory");

    if (!container) return;

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/application-history",
                {
                    method: "GET",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    cache: "no-store"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            /*
               Some versions of the backend may use
               /api/applications/history.
            */
            const fallback =
                await fetch(
                    "/api/applications/history",
                    {
                        method: "GET",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        cache: "no-store"
                    }
                );

            if (fallback.ok) {

                const fallbackData =
                    await fallback.json();

                if (fallbackData.success) {

                    applicationHistoryCache =
                        Array.isArray(
                            fallbackData.applications
                        )
                            ? fallbackData.applications
                            : [];

                    renderApplicationHistory(
                        applicationHistoryCache
                    );

                    return;
                }
            }

            renderApplicationHistory([]);

            console.error(
                "Application history error:",
                data.message
            );

            return;
        }

        let applications =
            Array.isArray(
                data.applications
            )
                ? data.applications
                : Array.isArray(data.history)
                    ? data.history
                    : [];

        /*
           Extra frontend ownership protection.
        */
        applications =
            applications.filter(
                application =>
                    applicationBelongsToCurrentUser(
                        application
                    )
            );

        applicationHistoryCache =
            applications;

        renderApplicationHistory(
            applications
        );

    } catch (error) {

        console.error(
            "Application history error:",
            error
        );

        renderApplicationHistory([]);
    }
}

function renderApplicationHistory(
    applications
) {

    const container =
        $("applicationHistory");

    if (!container) return;

    if (!applications.length) {

        container.innerHTML = `
            <div class="empty-state">
                <div>📄</div>

                <h3>
                    No application history
                </h3>

                <p>
                    Jobs you apply for will
                    appear here.
                </p>
            </div>
        `;

        return;
    }

    container.innerHTML =
        applications.map(
            application => {

                const job =
                    application.job || {};

                const title =
                    job.title ||
                    application.job_title ||
                    application.title ||
                    "Job";

                const company =
                    job.company ||
                    application.company ||
                    application.company_name ||
                    "Company";

                const status =
                    application.status ||
                    "Applied";

                const location =
                    job.location ||
                    application.location ||
                    "Not provided";

                const date =
                    application.applied_date ||
                    application.application_date ||
                    application.created_at ||
                    application.date ||
                    application.applied_on ||
                    "";

                const statusClass =
                    getStatusClass(status);

                return `
                    <div
                        class="status-job-card ${statusClass}">

                        <div
                            class="status-job-card-top">

                            <div>

                                <span class="small-label">
                                    ${
                                        escapeHTML(
                                            job.category ||
                                            application.category ||
                                            "JOB"
                                        )
                                    }
                                </span>

                                <h3>
                                    ${escapeHTML(
                                        title
                                    )}
                                </h3>

                                <p>
                                    ${escapeHTML(
                                        company
                                    )}
                                </p>

                            </div>

                            <span
                                class="
                                    professional-status-badge
                                    ${statusClass}
                                ">

                                ${statusIcon(status)}

                                ${escapeHTML(
                                    status
                                )}

                            </span>

                        </div>

                        <div
                            class="status-job-meta">

                            <span>
                                📍
                                ${escapeHTML(
                                    location
                                )}
                            </span>

                            <span>
                                📅
                                ${escapeHTML(
                                    formatApplicationDate(
                                        date
                                    )
                                )}
                            </span>

                        </div>

                        ${renderEmployerStatusDetails(
                            application
                        )}

                    </div>
                `;
            }
        ).join("");
}


/* =========================================================
   APPLICATION STATUS
========================================================= */

async function loadApplicationStatus() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/application-status",
                {
                    method: "GET",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    cache: "no-store"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            console.error(
                "Application status error:",
                data.message
            );

            return;
        }

        let applications =
            Array.isArray(
                data.applications
            )
                ? data.applications
                : [];

        applications =
            applications.filter(
                application =>
                    applicationBelongsToCurrentUser(
                        application
                    )
            );

        currentStatusApplications =
            applications;

        /*
           Prefer backend counts when present.
           If backend counts are not available,
           calculate them from the user's own records.
        */
        const counts =
            data.counts || {};

        const total =
            counts.total !== undefined
                ? counts.total
                : applications.length;

        const hired =
            counts.hired !== undefined
                ? counts.hired
                : applications.filter(
                    a =>
                        normalizeStatus(
                            a.status
                        ) === "hired"
                ).length;

        const shortlisted =
            counts.shortlisted !== undefined
                ? counts.shortlisted
                : applications.filter(
                    a =>
                        normalizeStatus(
                            a.status
                        ) === "shortlisted"
                ).length;

        const review =
            counts.under_review !== undefined
                ? counts.under_review
                : counts.underReview !== undefined
                    ? counts.underReview
                    : applications.filter(
                        a =>
                            normalizeStatus(
                                a.status
                            ) === "under review"
                    ).length;

        const rejected =
            counts.rejected !== undefined
                ? counts.rejected
                : applications.filter(
                    a =>
                        normalizeStatus(
                            a.status
                        ) === "rejected"
                ).length;

        if ($("statusTotal"))
            $("statusTotal").textContent =
                total;

        if ($("statusHired"))
            $("statusHired").textContent =
                hired;

        if ($("statusShortlisted"))
            $("statusShortlisted").textContent =
                shortlisted;

        if ($("statusReview"))
            $("statusReview").textContent =
                review;

        if ($("statusRejected"))
            $("statusRejected").textContent =
                rejected;

        const result =
            $("statusApplicationsResult");

        if (result) {

            result.classList.add(
                "hidden"
            );

            result.innerHTML = "";
        }

    } catch (error) {

        console.error(
            "Unable to load application status:",
            error
        );
    }
}

function showStatusApplications(
    status
) {

    if (
        !Array.isArray(
            currentStatusApplications
        )
    ) {
        currentStatusApplications = [];
    }

    let applications = [];

    if (
        status === "Total" ||
        status === "All" ||
        !status
    ) {

        applications =
            currentStatusApplications;

    } else {

        applications =
            currentStatusApplications.filter(
                application =>
                    normalizeStatus(
                        application.status
                    ) ===
                    normalizeStatus(status)
            );
    }

    renderStatusResults(
        applications,
        status === "Total"
            ? "All Applications"
            : `${status} Applications`
    );
}

function searchApplicationStatus() {

    const input =
        $("applicationStatusSearch");

    if (!input) return;

    const search =
        input.value
            .trim()
            .toLowerCase();

    if (
        !Array.isArray(
            currentStatusApplications
        )
    ) {
        currentStatusApplications = [];
    }

    const applications =
        currentStatusApplications.filter(
            application => {

                const job =
                    application.job || {};

                const text = [
                    job.title,
                    job.company,
                    application.job_title,
                    application.company,
                    application.status,
                    application.category,
                    application.location
                ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();

                return (
                    !search ||
                    text.includes(search)
                );
            }
        );

    renderStatusResults(
        applications,
        search
            ? `Search Results for "${search}"`
            : "All Applications"
    );
}

function renderStatusResults(
    applications,
    title
) {

    const container =
        $("statusApplicationsResult");

    if (!container) return;

    if (!applications.length) {

        container.innerHTML = `
            <div class="status-results-header">

                <div>

                    <span class="small-label">
                        APPLICATIONS
                    </span>

                    <h3>
                        ${escapeHTML(title)}
                    </h3>

                    <p>
                        0 applications
                    </p>

                </div>

                <button
                    class="small-btn"
                    onclick="closeStatusResults()">

                    × Close

                </button>

            </div>

            <div class="empty-state">

                <div>📭</div>

                <h3>
                    No applications found
                </h3>

                <p>
                    Try another job title,
                    company or status.
                </p>

            </div>
        `;

        container.classList.remove(
            "hidden"
        );

        return;
    }

    container.innerHTML = `
        <div class="status-results-header">

            <div>

                <span class="small-label">
                    APPLICATIONS
                </span>

                <h3>
                    ${escapeHTML(title)}
                </h3>

                <p>
                    ${applications.length}
                    application(s)
                </p>

            </div>

            <button
                class="small-btn"
                onclick="closeStatusResults()">

                × Close

            </button>

        </div>

        <div class="status-job-list">

            ${
                applications
                    .map(
                        application =>
                            renderStatusApplication(
                                application
                            )
                    )
                    .join("")
            }

        </div>
    `;

    container.classList.remove(
        "hidden"
    );

    setTimeout(() => {

        container.scrollIntoView({
            behavior: "smooth",
            block: "start"
        });

    }, 100);
}

function closeStatusResults() {

    const container =
        $("statusApplicationsResult");

    if (container) {
        container.classList.add(
            "hidden"
        );
    }
}

function renderStatusApplication(
    application
) {

    const job =
        application.job || {};

    const status =
        application.status ||
        "Applied";

    const statusClass =
        getStatusClass(status);

    const title =
        job.title ||
        application.job_title ||
        application.title ||
        "Job";

    const company =
        job.company ||
        application.company ||
        application.company_name ||
        "Company";

    const location =
        job.location ||
        application.location ||
        "";

    const applied =
        application.applied_date ||
        application.application_date ||
        application.created_at ||
        application.date ||
        application.applied_on ||
        application.createdAt ||
        "";

    return `
        <div
            class="status-job-card ${statusClass}">

            <div
                class="status-job-card-top">

                <div>

                    <span class="small-label">
                        ${escapeHTML(
                            job.category ||
                            application.category ||
                            "JOB"
                        )}
                    </span>

                    <h3>
                        ${escapeHTML(title)}
                    </h3>

                    <p>
                        ${escapeHTML(company)}
                    </p>

                </div>

                <span
                    class="
                        professional-status-badge
                        ${statusClass}
                    ">

                    ${statusIcon(status)}
                    ${escapeHTML(status)}

                </span>

            </div>

            <div class="status-job-meta">

                <span>
                    📍
                    ${escapeHTML(
                        location ||
                        "Location not provided"
                    )}
                </span>

                <span>
                    📅
                    ${escapeHTML(
                        formatApplicationDate(
                            applied
                        )
                    )}
                </span>

            </div>

            ${renderEmployerStatusDetails(
                application
            )}

        </div>
    `;
}


/* =========================================================
   STATUS HELPERS
========================================================= */

function normalizeStatus(status) {

    return String(status || "")
        .trim()
        .toLowerCase()
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ");
}

function getStatusClass(status) {

    const normalized =
        normalizeStatus(status);

    if (normalized === "hired")
        return "status-hired";

    if (normalized === "rejected")
        return "status-rejected";

    if (normalized === "shortlisted")
        return "status-shortlisted";

    if (normalized === "under review")
        return "status-under-review";

    return "status-applied";
}

function statusIcon(status) {

    const normalized =
        normalizeStatus(status);

    if (normalized === "hired")
        return "✓";

    if (normalized === "rejected")
        return "✕";

    if (normalized === "shortlisted")
        return "★";

    if (normalized === "under review")
        return "◷";

    return "•";
}


/* =========================================================
   DATE / TIME
========================================================= */

function formatDate(date) {

    if (!date)
        return "Not provided";

    let cleanDate =
        String(date);

    if (cleanDate.includes("T")) {

        cleanDate =
            cleanDate.split("T")[0];
    }

    const d =
        new Date(
            cleanDate +
            "T00:00:00"
        );

    if (isNaN(d.getTime()))
        return String(date);

    return d.toLocaleDateString(
        "en-US",
        {
            year: "numeric",
            month: "long",
            day: "numeric"
        }
    );
}

function formatApplicationDate(date) {

    if (!date)
        return "Date not provided";

    const d =
        new Date(date);

    if (isNaN(d.getTime()))
        return formatDate(date);

    return d.toLocaleDateString(
        "en-US",
        {
            year: "numeric",
            month: "long",
            day: "numeric"
        }
    );
}

function formatTime(time) {

    if (!time)
        return "Not provided";

    const parts =
        String(time).split(":");

    if (parts.length < 2)
        return time;

    let hour =
        parseInt(parts[0], 10);

    const minute =
        parts[1];

    const suffix =
        hour >= 12
            ? "PM"
            : "AM";

    hour =
        hour % 12 || 12;

    return `${hour}:${minute} ${suffix}`;
}


/* =========================================================
   RESUME UPLOAD
========================================================= */

async function uploadResume() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_seeker"
    ) {

        showToast(
            "Please login as a job seeker first."
        );

        return;
    }

    const fileInput =
        $("resumeFile");

    const skillsInput =
        $("resumeSkills");

    const introInput =
        $("resumeIntroduction");

    const file =
        fileInput &&
        fileInput.files
            ? fileInput.files[0]
            : null;

    const skills =
        skillsInput
            ? skillsInput.value.trim()
            : "";

    const introduction =
        introInput
            ? introInput.value.trim()
            : "";

    if (!file) {

        showToast(
            "Please select your resume file."
        );

        return;
    }

    if (!skills) {

        showToast(
            "Please enter your skills."
        );

        return;
    }

    if (!introduction) {

        showToast(
            "Please enter your professional introduction."
        );

        return;
    }

    const formData =
        new FormData();

    formData.append(
        "resume",
        file
    );

    formData.append(
        "skills",
        skills
    );

    formData.append(
        "introduction",
        introduction
    );

    try {

        const response =
            await fetch(
                "/api/resumes/upload",
                {
                    method: "POST",
                    body: formData
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to upload resume."
            );

            return;
        }

        showToast(
            "Resume uploaded successfully."
        );

        if (fileInput)
            fileInput.value = "";

        if (skillsInput)
            skillsInput.value = "";

        if (introInput)
            introInput.value = "";

    } catch (error) {

        console.error(
            "Resume upload error:",
            error
        );

        showToast(
            "Unable to connect to the server."
        );
    }
}


/* =========================================================
   SEEKER NOTIFICATIONS
========================================================= */

function loadSeekerNotifications() {
    return loadNotifications();
}


/* =========================================================
   POST JOB
========================================================= */

async function postJob() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {

        showToast(
            "Please login as a job poster."
        );

        return;
    }

    const title =
        $("jobTitle").value.trim();

    const company =
        $("jobCompany").value.trim();

    const category =
        $("jobCategory").value.trim();

    const location =
        $("jobLocation").value.trim();

    const salary =
        $("jobSalary").value.trim();

    const description =
        $("jobDescription").value.trim();

    if (
        !title ||
        !company ||
        !category ||
        !location ||
        !salary ||
        !description
    ) {

        showToast(
            "Please fill all required job fields."
        );

        return;
    }

    try {

        const response =
            await fetch(
                "/api/jobs",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        title,
                        company,
                        category,
                        location,
                        salary,
                        description
                    })
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to post job."
            );

            return;
        }

        showToast(
            "Job posted successfully."
        );

        $("jobTitle").value = "";
        $("jobCompany").value = "";
        $("jobCategory").value = "";
        $("jobLocation").value = "";
        $("jobSalary").value = "";
        $("jobDescription").value = "";

        await loadMyJobs();
        await loadNotifications();

    } catch (error) {

        console.error(
            "Post job error:",
            error
        );

        showToast(
            "Unable to connect to server."
        );
    }
}


/* =========================================================
   MY JOBS
========================================================= */

async function loadMyJobs() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/my-jobs",
                {
                    cache: "no-store"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to load your jobs."
            );

            return;
        }

        renderJobs(
            "myJobsContainer",
            data.jobs || [],
            false
        );

    } catch (error) {

        console.error(
            "My jobs error:",
            error
        );

        showToast(
            "Unable to load your jobs."
        );
    }
}


/* =========================================================
   DELETE JOB
========================================================= */

async function deleteJob(jobId) {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {
        return;
    }

    if (
        !confirm(
            "Delete this job? This will also remove its applications from this job."
        )
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                `/api/jobs/${jobId}`,
                {
                    method: "DELETE"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to delete job."
            );

            return;
        }

        showToast(
            "Job deleted successfully."
        );

        await loadMyJobs();
        await loadPosterApplications();
        await loadNotifications();

    } catch (error) {

        console.error(
            "Delete job error:",
            error
        );

        showToast(
            "Unable to connect to server."
        );
    }
}


/* =========================================================
   SEARCH CANDIDATE RESUMES
========================================================= */

async function searchResumes() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {
        return;
    }

    const search =
        $("resumeSearch")
            .value.trim();

    const params =
        new URLSearchParams();

    if (search)
        params.append(
            "search",
            search
        );

    try {

        const response =
            await fetch(
                "/api/resumes?" +
                params.toString()
            );

        const data =
            await response.json();

        const container =
            $("resumesContainer");

        if (!container) return;

        const candidates =
            data.resumes || [];

        if (!candidates.length) {

            container.innerHTML = `
                <div class="empty-state">
                    <div>👥</div>
                    <h3>No candidates found</h3>
                    <p>Try another search.</p>
                </div>
            `;

            return;
        }

        container.innerHTML =
            candidates.map(
                candidate => {

                    const user =
                        candidate.user ||
                        {};

                    const resume =
                        candidate.resume ||
                        {};

                    return `
                        <div class="resume-card">

                            <div
                                class="resume-card-icon">
                                👤
                            </div>

                            <h3>
                                ${escapeHTML(
                                    user.name ||
                                    "Candidate"
                                )}
                            </h3>

                            <p>
                                ${escapeHTML(
                                    user.email ||
                                    ""
                                )}
                            </p>

                            <div
                                class="candidate-resume-info">

                                <strong>
                                    Skills
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        resume.skills ||
                                        "Not provided"
                                    )}
                                </span>

                            </div>

                            <div
                                class="candidate-resume-info">

                                <strong>
                                    Introduction
                                </strong>

                                <span>
                                    ${escapeHTML(
                                        resume.introduction ||
                                        "Not provided"
                                    )}
                                </span>

                            </div>

                            <a
                                                           
                                class="small-btn"
                                href="/resumes/${encodeURIComponent(
                                    resume.filename || ""
                                )}"
                                target="_blank">

                                📄 View Resume

                            </a>

                        </div>
                    `;
                }
            ).join("");

    } catch (error) {

        console.error(
            "Resume search error:",
            error
        );

        showToast(
            "Unable to search candidates."
        );
    }
}


/* =========================================================
   POSTER APPLICATIONS
========================================================= */

async function loadPosterApplications() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {
        return;
    }

    try {

        const response =
            await fetch(
                "/api/my-applicants",
                {
                    cache: "no-store"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showToast(
                data.message ||
                "Unable to load applicants."
            );

            return;
        }

        const applicants =
            Array.isArray(
                data.applicants
            )
                ? data.applicants
                : [];

        /*
           /api/my-applicants should already return
           applications belonging only to this poster.

           Extra protection: if the API provides
           poster ownership fields, reject records
           belonging to another poster.
        */
        posterApplicationsCache =
            applicants.filter(
                item =>
                    posterApplicationBelongsToCurrentUser(
                        item
                    )
            );

        populateApplicantJobFilter(
            posterApplicationsCache
        );

        renderPosterApplications();

    } catch (error) {

        console.error(
            "Poster applications error:",
            error
        );

        showToast(
            "Unable to load applicants."
        );
    }
}

function posterApplicationBelongsToCurrentUser(
    item
) {

    if (!currentUser || !item)
        return false;

    const currentId =
        getCurrentUserId();

    const job =
        item.job || {};

    const poster =
        item.poster ||
        item.employer ||
        {};

    const posterId =
        item.poster_id ??
        item.poster_user_id ??
        item.employer_id ??
        job.poster_id ??
        job.user_id ??
        job.owner_id ??
        poster.id ??
        poster.user_id ??
        null;

    if (
        currentId !== null &&
        posterId !== null
    ) {

        return sameValue(
            currentId,
            posterId
        );
    }

    return true;
}


/* =========================================================
   JOB FILTER FOR APPLICANTS
========================================================= */

function populateApplicantJobFilter(
    applicants
) {

    const select =
        $("applicantJobFilter");

    if (!select) return;

    const current =
        select.value || "all";

    const jobs =
        new Map();

    applicants.forEach(item => {

        const job =
            item.job || {};

        if (
            job.id !== undefined &&
            job.id !== null
        ) {

            jobs.set(
                String(job.id),
                job
            );
        }
    });

    select.innerHTML =
        `<option value="all">
            All Jobs
        </option>` +

        Array.from(
            jobs.values()
        )
            .sort(
                (a, b) =>
                    String(
                        a.title || ""
                    ).localeCompare(
                        String(
                            b.title || ""
                        )
                    )
            )
            .map(
                job => `
                    <option
                        value="${escapeHTML(
                            String(job.id)
                        )}">

                        ${escapeHTML(
                            job.title ||
                            "Untitled Job"
                        )}

                    </option>
                `
            )
            .join("");

    if (
        Array.from(
            select.options
        ).some(
            option =>
                option.value ===
                current
        )
    ) {

        select.value =
            current;
    }
}

function filterPosterApplications() {
    renderPosterApplications();
}


/* =========================================================
   RENDER POSTER APPLICATIONS
========================================================= */

function renderPosterApplications() {

    const container =
        $("posterApplicationsContainer");

    if (!container) return;

    const filter =
        $("applicantJobFilter");

    const selected =
        filter
            ? filter.value
            : "all";

    const applicants =
        selected === "all"
            ? posterApplicationsCache
            : posterApplicationsCache.filter(
                item =>
                    String(
                        (item.job || {}).id
                    ) ===
                    String(selected)
            );

    const summary =
        $("applicationSummary");

    if (summary) {

        summary.textContent =
            `${applicants.length} candidate(s) shown.`;
    }

    const badge =
        $("applicationBadge");

    if (badge) {

        if (applicants.length) {

            badge.textContent =
                applicants.length;

            badge.classList.remove(
                "hidden"
            );

        } else {

            badge.classList.add(
                "hidden"
            );
        }
    }

    if (!applicants.length) {

        container.innerHTML = `
            <div class="empty-state">

                <div>📥</div>

                <h3>
                    No applicants found
                </h3>

                <p>
                    Try selecting another job.
                </p>

            </div>
        `;

        return;
    }

    container.innerHTML =
        applicants
            .map(
                item =>
                    renderApplicantCard(
                        item
                    )
            )
            .join("");
}


/* =========================================================
   APPLICANT CARD
========================================================= */

function renderApplicantCard(item) {

    const applicant =
        item.applicant || {};

    const job =
        item.job || {};

    const status =
        item.status ||
        "Applied";

    const statusClass =
        getStatusClass(status);

    const applicantName =
        applicant.name ||
        item.name ||
        "Applicant";

    const resume =
        item.resume || {};

    const resumeFilename =
        item.resume_filename ||
        resume.filename ||
        "";

    const resumeUrl =
        item.resume_url ||
        (
            resumeFilename
                ? `/resumes/${encodeURIComponent(
                    resumeFilename
                )}`
                : ""
        );

    const safeName =
        escapeHTML(
            applicantName
        )
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'");

    return `
        <div class="application-card">

            <div class="application-card-header">

                <div>

                    <span class="small-label">
                        APPLICANT
                    </span>

                    <h3>
                        ${escapeHTML(
                            applicantName
                        )}
                    </h3>

                    <p>
                        Applied for:

                        <strong>
                            ${escapeHTML(
                                job.title ||
                                item.job_title ||
                                "Job"
                            )}
                        </strong>
                    </p>

                </div>

                <div class="applicant-card-right">

                    <span
                        class="
                            professional-status-badge
                            ${statusClass}
                        ">

                        ${statusIcon(status)}
                        ${escapeHTML(status)}

                    </span>

                    <button
                        class="more-info-btn"
                        onclick="
                            toggleApplicantInfo(
                                ${item.application_id}
                            )
                        ">

                        More Info

                    </button>

                </div>

            </div>

            <div
                id="applicantInfo${item.application_id}"
                class="applicant-more-info">

                <div class="applicant-info-grid">

                    <div class="applicant-info-box">

                        <span>
                            Full Name
                        </span>

                        <strong>
                            ${escapeHTML(
                                applicant.name ||
                                item.name ||
                                "Not provided"
                            )}
                        </strong>

                    </div>

                    <div class="applicant-info-box">

                        <span>
                            Email
                        </span>

                        <strong>
                            ${escapeHTML(
                                applicant.email ||
                                item.email ||
                                "Not provided"
                            )}
                        </strong>

                    </div>

                    <div class="applicant-info-box">

                        <span>
                            Contact
                        </span>

                        <strong>
                            ${escapeHTML(
                                applicant.contact ||
                                item.contact ||
                                "Not provided"
                            )}
                        </strong>

                    </div>

                    <div class="applicant-info-box">

                        <span>
                            Applied Job
                        </span>

                        <strong>
                            ${escapeHTML(
                                job.title ||
                                item.job_title ||
                                "Job"
                            )}
                        </strong>

                    </div>

                </div>

                ${
                    item.introduction ||
                    applicant.introduction
                    ? `
                        <div class="applicant-long-info">

                            <span>
                                Introduction
                            </span>

                            <p>
                                ${escapeHTML(
                                    item.introduction ||
                                    applicant.introduction
                                )}
                            </p>

                        </div>
                    `
                    : ""
                }

                <div class="applicant-resume-box">

                    <div>

                        <strong>
                            Resume
                        </strong>

                        <p>
                            ${
                                resumeFilename
                                    ? escapeHTML(
                                        resumeFilename
                                    )
                                    : "No resume attached"
                            }
                        </p>

                    </div>

                    
                                        ${
                        resumeUrl
                            ? `
                                <a
                                    class="resume-view-btn"
                                    href="${escapeHTML(
                                        resumeUrl
                                    )}"
                                    target="_blank"
                                    rel="noopener">

                                    📄 View Resume

                                </a>
                            `
                            : `
                                <span class="small-label">
                                    Not available
                                </span>
                            `
                    }

                </div>

                <div class="application-actions">

                    <button
                        class="status-btn-review"
                        onclick="
                            openStatusUpdateModal(
                                ${item.application_id},
                                'Under Review',
                                '${safeName}'
                            )
                        ">

                        ◷ Review

                    </button>

                    <button
                        class="status-btn-shortlisted"
                        onclick="
                            openStatusUpdateModal(
                                ${item.application_id},
                                'Shortlisted',
                                '${safeName}'
                            )
                        ">

                        ★ Shortlist

                    </button>

                    <button
                        class="status-btn-hired"
                        onclick="
                            openStatusUpdateModal(
                                ${item.application_id},
                                'Hired',
                                '${safeName}'
                            )
                        ">

                        ✓ Hire

                    </button>

                    <button
                        class="status-btn-rejected"
                        onclick="
                            openStatusUpdateModal(
                                ${item.application_id},
                                'Rejected',
                                '${safeName}'
                            )
                        ">

                        ✕ Reject

                    </button>

                </div>

            </div>

        </div>
    `;
}


/* =========================================================
   EMPLOYER STATUS DETAILS
========================================================= */

function renderEmployerStatusDetails(
    item
) {

    const status =
        normalizeStatus(
            item.status || ""
        );

    if (status === "hired") {

        return `
            <div
                class="
                    employer-status-info
                    hired-info
                ">

                <strong>
                    ✓ Hired Information
                </strong>

                <p>
                    Salary:
                    <b>
                        Rs.
                        ${escapeHTML(
                            item.salary ||
                            "Not provided"
                        )}
                    </b>
                </p>

                ${
                    item.remarks
                        ? `
                            <p>
                                Remarks:
                                ${escapeHTML(
                                    item.remarks
                                )}
                            </p>
                        `
                        : ""
                }

            </div>
        `;
    }

    if (status === "shortlisted") {

        return `
            <div
                class="
                    employer-status-info
                    shortlisted-info
                ">

                <strong>
                    ★ Interview Information
                </strong>

                <p>
                    Date:
                    <b>
                        ${escapeHTML(
                            formatDate(
                                item.interview_date
                            )
                        )}
                    </b>
                </p>

                <p>
                    Time:
                    <b>
                        ${escapeHTML(
                            formatTime(
                                item.interview_time
                            )
                        )}
                    </b>
                </p>

                ${
                    item.remarks
                        ? `
                            <p>
                                Remarks:
                                ${escapeHTML(
                                    item.remarks
                                )}
                            </p>
                        `
                        : ""
                }

            </div>
        `;
    }

    if (
        status === "rejected" ||
        status === "under review"
    ) {

        return `
            <div
                class="employer-status-info">

                <strong>
                    ${
                        status === "rejected"
                            ? "✕ Rejection Remarks"
                            : "◷ Review Remarks"
                    }
                </strong>

                <p>
                    ${escapeHTML(
                        item.remarks ||
                        "No remarks."
                    )}
                </p>

            </div>
        `;
    }

    return "";
}


/* =========================================================
   APPLICANT MORE INFO
========================================================= */

function toggleApplicantInfo(
    applicationId
) {

    const element =
        $("applicantInfo" +
            applicationId);

    if (!element) return;

    element.classList.toggle(
        "show"
    );
}


/* =========================================================
   STATUS UPDATE MODAL
========================================================= */

function openStatusUpdateModal(
    applicationId,
    status,
    applicantName
) {

    if ($("statusApplicationId"))
        $("statusApplicationId").value =
            applicationId;

    if ($("selectedApplicationStatus"))
        $("selectedApplicationStatus").value =
            status;

    if ($("statusModalApplicant"))
        $("statusModalApplicant")
            .textContent =
                `${applicantName} — ${status}`;

    if ($("statusModalTitle"))
        $("statusModalTitle")
            .textContent =
                status === "Hired"
                    ? "Hire Candidate"
                    : status === "Shortlisted"
                        ? "Shortlist Candidate"
                        : status === "Rejected"
                            ? "Reject Candidate"
                            : "Put Application Under Review";

    if ($("statusModalIcon"))
        $("statusModalIcon")
            .textContent =
                statusIcon(status);

    [
        "hireFields",
        "shortlistFields",
        "reviewFields",
        "rejectFields"
    ].forEach(id => {

        if ($(id))
            $(id).classList.add(
                "hidden"
            );
    });

    if (
        normalizeStatus(status) ===
        "hired"
    ) {

        $("hireFields")
            .classList.remove(
                "hidden"
            );

        $("hireSalary").value = "";
        $("hireRemarks").value = "";

    } else if (
        normalizeStatus(status) ===
        "shortlisted"
    ) {

        $("shortlistFields")
            .classList.remove(
                "hidden"
            );

        $("interviewDate").value = "";
        $("interviewTime").value = "";
        $("shortlistRemarks").value = "";

    } else if (
        normalizeStatus(status) ===
        "under review"
    ) {

        $("reviewFields")
            .classList.remove(
                "hidden"
            );

        $("reviewRemarks").value = "";

    } else if (
        normalizeStatus(status) ===
        "rejected"
    ) {

        $("rejectFields")
            .classList.remove(
                "hidden"
            );

        $("rejectRemarks").value = "";
    }

    hideErrorBox(
        "statusUpdateError"
    );

    $("statusUpdateModal")
        .classList.remove(
            "hidden"
        );
}

function closeStatusUpdateModal() {

    if ($("statusUpdateModal")) {

        $("statusUpdateModal")
            .classList.add(
                "hidden"
            );
    }
}


/* =========================================================
   CONFIRM STATUS
========================================================= */

async function confirmApplicationStatus() {

    if (
        !currentUser ||
        currentUser.role !==
        "job_poster"
    ) {
        return;
    }

    const applicationId =
        $("statusApplicationId").value;

    const status =
        $("selectedApplicationStatus")
            .value;

    let salary = "";
    let interviewDate = "";
    let interviewTime = "";
    let remarks = "";

    if (
        normalizeStatus(status) ===
        "hired"
    ) {

        salary =
            $("hireSalary")
                .value
                .trim();

        remarks =
            $("hireRemarks")
                .value
                .trim();

        if (!salary) {

            markInput(
                "hireSalary",
                false
            );

            showValidation(
                "hireSalaryValidation",
                false,
                "Salary is required."
            );

            return;
        }

        markInput(
            "hireSalary",
            true
        );

        showValidation(
            "hireSalaryValidation",
            true,
            "Salary entered."
        );
    }

    if (
        normalizeStatus(status) ===
        "shortlisted"
    ) {

        interviewDate =
            $("interviewDate").value;

        interviewTime =
            $("interviewTime").value;

        remarks =
            $("shortlistRemarks")
                .value
                .trim();

        if (!interviewDate) {

            markInput(
                "interviewDate",
                false
            );

            showValidation(
                "interviewDateValidation",
                false,
                "Interview date is required."
            );

            return;
        }

        if (!interviewTime) {

            markInput(
                "interviewTime",
                false
            );

            showValidation(
                "interviewTimeValidation",
                false,
                "Interview time is required."
            );

            return;
        }

        markInput(
            "interviewDate",
            true
        );

        markInput(
            "interviewTime",
            true
        );
    }

    if (
        normalizeStatus(status) ===
        "under review"
    ) {

        remarks =
            $("reviewRemarks")
                .value
                .trim();

        if (!remarks) {

            markInput(
                "reviewRemarks",
                false
            );

            showValidation(
                "reviewRemarksValidation",
                false,
                "Remarks are required."
            );

            return;
        }

        markInput(
            "reviewRemarks",
            true
        );
    }

    if (
        normalizeStatus(status) ===
        "rejected"
    ) {

        remarks =
            $("rejectRemarks")
                .value
                .trim();

        if (!remarks) {

            markInput(
                "rejectRemarks",
                false
            );

            showValidation(
                "rejectRemarksValidation",
                false,
                "Remarks are required."
            );

            return;
        }

        markInput(
            "rejectRemarks",
            true
        );
    }

    try {

        const response =
            await fetch(
                `/api/applications/${applicationId}/status`,
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        status,
                        salary,
                        interview_date:
                            interviewDate,
                        interview_time:
                            interviewTime,
                        remarks
                    })
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            showErrorBox(
                "statusUpdateError",
                data.message ||
                "Unable to update application."
            );

            return;
        }

        closeStatusUpdateModal();

        showToast(
            `Application marked as ${status}.`
        );

        await loadPosterApplications();
        await loadNotifications();

    } catch (error) {

        console.error(
            "Status update error:",
            error
        );

        showErrorBox(
            "statusUpdateError",
            "Unable to connect to server."
        );
    }
}


/* =========================================================
   NOTIFICATIONS
========================================================= */

async function loadNotifications() {

    if (!currentUser) return;

    try {

        const response =
            await fetch(
                "/api/notifications",
                {
                    method: "GET",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    cache: "no-store"
                }
            );

        const data =
            await response.json();

        if (
            !response.ok ||
            !data.success
        ) {

            console.error(
                "Notification API error:",
                data.message
            );

            return;
        }

        let notifications =
            Array.isArray(
                data.notifications
            )
                ? data.notifications
                : [];

        /*
           IMPORTANT:
           Never render another user's notification
           when the notification explicitly contains
           recipient information.
        */
        notifications =
            notifications.filter(
                notification =>
                    notificationBelongsToCurrentUser(
                        notification
                    )
            );

        const unreadCount =
            notifications.filter(
                notification =>
                    !notification.read
            ).length;

        const badge =
            $("notificationBadge");

        if (badge) {

            if (unreadCount > 0) {

                badge.textContent =
                    unreadCount;

                badge.classList.remove(
                    "hidden"
                );

            } else {

                badge.textContent = "0";

                badge.classList.add(
                    "hidden"
                );
            }
        }

        if (
            currentUser.role ===
            "job_seeker"
        ) {

            renderSeekerNotifications(
                notifications
            );

        } else if (
            currentUser.role ===
            "job_poster"
        ) {

            renderNotifications(
                "posterNotifications",
                notifications
            );
        }

    } catch (error) {

        console.error(
            "Notification error:",
            error
        );
    }
}

function renderSeekerNotifications(
    notifications
) {

    const container =
        $("seekerNotifications");

    if (!container) return;

    if (!notifications.length) {

        container.innerHTML = `
            <div class="empty-state">

                <div>🔔</div>

                <h3>
                    No notifications
                </h3>

                <p>
                    You are all caught up.
                </p>

            </div>
        `;

        return;
    }

    container.innerHTML =
        notifications
            .slice()
            .reverse()
            .map(
                notification => {

                    const status =
                        notification.status ||
                        "";

                    const statusClass =
                        status
                            ? getStatusClass(
                                status
                            )
                            : "";

                    return `
                        <div
                            class="
                                notification-item
                                ${
                                    notification.read
                                        ? ""
                                        : "unread"
                                }
                                ${statusClass}
                            ">

                            <div
                                class="notification-icon">

                                ${
                                    status
                                        ? statusIcon(
                                            status
                                        )
                                        : "🔔"
                                }

                            </div>

                            <div
                                class="
                                    notification-content
                                ">

                                <div
                                    class="
                                        notification-message
                                    ">

                                    ${escapeHTML(
                                        notification.message ||
                                        ""
                                    )}

                                </div>

                                ${
                                    notification.read
                                        ? ""
                                        : `
                                            <span
                                                class="
                                                    notification-new
                                                ">

                                                NEW

                                            </span>
                                        `
                                }

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}

function renderNotifications(
    containerId,
    notifications
) {

    const container =
        $(containerId);

    if (!container) return;

    if (!notifications.length) {

        container.innerHTML = `
            <div class="empty-state">

                <div>🔔</div>

                <h3>
                    No notifications
                </h3>

                <p>
                    You are all caught up.
                </p>

            </div>
        `;

        return;
    }

    container.innerHTML =
        notifications
            .slice()
            .reverse()
            .map(
                notification => {

                    const status =
                        notification.status ||
                        "";

                    return `
                        <div
                            class="
                                notification-item
                                ${
                                    notification.read
                                        ? ""
                                        : "unread"
                                }
                            ">

                            <div
                                class="notification-icon">

                                ${
                                    status
                                        ? statusIcon(
                                            status
                                        )
                                        : "🔔"
                                }

                            </div>

                            <div
                                class="
                                    notification-content
                                ">

                                <strong>

                                    ${
                                        notification.type ===
                                        "application_status"
                                            ? "Application Update"
                                            : "New Application"
                                    }

                                </strong>

                                <p>
                                    ${escapeHTML(
                                        notification.message ||
                                        ""
                                    )}
                                </p>

                                ${
                                    notification.read
                                        ? ""
                                        : `
                                            <span
                                                class="
                                                    notification-new
                                                ">

                                                NEW

                                            </span>
                                        `
                                }

                            </div>

                        </div>
                    `;
                }
            )
            .join("");
}


/* =========================================================
   MARK NOTIFICATIONS READ
========================================================= */

async function markNotificationsRead() {

    if (!currentUser) return;

    try {

        await fetch(
            "/api/notifications/read",
            {
                method: "POST"
            }
        );

        await loadNotifications();

    } catch (error) {

        console.error(
            "Unable to mark notifications read:",
            error
        );
    }
}


/* =========================================================
   APPLICATION STATUS SEARCH SETUP
========================================================= */

function setupApplicationStatusSearch() {

    const input =
        $("applicationStatusSearch");

    if (!input) return;

    input.addEventListener(
        "input",
        searchApplicationStatus
    );
}


/* =========================================================
   MODAL CLICK OUTSIDE
========================================================= */

window.addEventListener(
    "click",
    function(event) {

        if (
            $("jobModal") &&
            event.target ===
            $("jobModal")
        ) {

            closeJobModal();
        }

        if (
            $("applyModal") &&
            event.target ===
            $("applyModal")
        ) {

            closeApplyModal();
        }

        if (
            $("statusUpdateModal") &&
            event.target ===
            $("statusUpdateModal")
        ) {

            closeStatusUpdateModal();
        }
    }
);


/* =========================================================
   PAGE LOAD / SESSION RESTORE
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    async function() {

        setupApplicationStatusSearch();

        try {

            const response =
                await fetch(
                    "/api/me",
                    {
                        method: "GET",
                        headers: {
                            "Content-Type":
                                "application/json"
                        },
                        cache: "no-store"
                    }
                );

            const data =
                await response.json();

            if (
                data.success &&
                data.logged_in &&
                data.user
            ) {

                currentUser =
                    data.user;

                $("startPage")
                    .classList
                    .add("hidden");

                $("authPage")
                    .classList
                    .add("hidden");

                $("welcomeUser")
                    .textContent =
                        "Welcome, " +
                        (
                            currentUser.name ||
                            ""
                        );

                $("logoutBtn")
                    .style
                    .display =
                        "inline-flex";

                /*
                   THIS IS THE IMPORTANT PART.
                   The currently logged-in account is loaded
                   first, then ONLY that account's dashboard
                   data is requested.
                */
                await loadUserPortal();
            }

        } catch (error) {

            console.error(
                "Startup error:",
                error
            );
        }
    }
);