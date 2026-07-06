// Convert backend date to human-readable "time ago"
function timeAgo(dateString) {
    const date = new Date(dateString);
    const seconds = Math.floor((new Date() - date) / 1000);

    let interval = seconds / 31536000;
    if (interval > 1) return Math.floor(interval) + " years ago";

    interval = seconds / 2592000;
    if (interval > 1) return Math.floor(interval) + " months ago";

    interval = seconds / 86400;
    if (interval > 1) return Math.floor(interval) + " days ago";

    interval = seconds / 3600;
    if (interval > 1) return Math.floor(interval) + " hours ago";

    interval = seconds / 60;
    if (interval > 1) return Math.floor(interval) + " minutes ago";

    return "Just now";
}

// Update badge count
function updateBadge(count) {
    const badge = document.getElementById("mailBadge");
    if (!badge) return;

    if (count > 0) {
        badge.textContent = count;
        badge.style.display = "inline-flex"; // use flex to center numbers
    } else {
        badge.style.display = "none";
    }
}

// Load mails from API
async function loadMails() {
    try {
        const res = await fetch("/api/mails");
        const mails = await res.json();

        const box = document.getElementById("mailItems");
        if (!box) return;

        box.innerHTML = "";
        let unread = 0;

        mails.forEach(mail => {
            if (!mail.is_read) unread++;

            const card = document.createElement("div");
            card.className = "navmail-card";
            card.innerHTML = `
                <div class="navmail-avatar">
                    <img src="${mail.avatar}" alt="avatar">
                </div>

                <div class="navmail-body">
                    <div class="navmail-subject">${mail.subject}</div>
                    <div class="navmail-preview">${mail.message.substring(0, 60)}...</div>
                    <div class="navmail-meta">
                        <span class="navmail-sender">${mail.sender}</span>
                        <span class="navmail-time">${timeAgo(mail.created)}</span>
                    </div>
                </div>

                <div class="navmail-priority navmail-priority-${mail.priority}">
                    <i class="bi bi-envelope-fill"></i>
                </div>
            `;

            card.onclick = () => {
                // Navigate to mail view
                window.location.href = "/mail/view/" + mail.id;
                // Optimistic update
                if (!mail.is_read) {
                    mail.is_read = true;
                    unread--;
                    updateBadge(unread);
                }
            };

            box.appendChild(card);
        });

        // Update badge after loading
        updateBadge(unread);

    } catch (err) {
        console.error("Mail load error:", err);
    }
}

// Initial load + periodic refresh
loadMails();
setInterval(loadMails, 15000);