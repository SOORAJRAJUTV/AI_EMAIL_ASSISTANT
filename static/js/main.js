// Email Assistant Main JS
document.addEventListener('DOMContentLoaded', function () {
    // DOM Elements
    const emailList = document.getElementById('email-list');
    const refreshBtn = document.getElementById('refresh-btn');
    const replyModal = document.getElementById('reply-modal');
    const closeBtn = document.querySelector('.close-btn');
    const sendReplyBtn = document.getElementById('send-reply-btn');
    const editReplyBtn = document.getElementById('edit-reply-btn');
    const replyContent = document.getElementById('reply-content');
    const searchInput = document.getElementById('email-search');

    const autoReplyToggle = document.getElementById('auto-reply-toggle');
    const autoReplyStatus = document.getElementById('auto-reply-status');


    // State
    let isFetching = false;
    let currentEmail = null;
    let lastFetchTime = 0;
    const FETCH_COOLDOWN = 60000;

    safeLoadEmails();
    setupAutoReplyToggle();


    // Event Listeners
    refreshBtn.addEventListener('click', safeLoadEmails);
    closeBtn.addEventListener('click', closeModal);
    searchInput.addEventListener('input', debounce(searchEmails, 300));

    replyModal.addEventListener('click', function (e) {
        if (e.target === replyModal) {
            closeModal();
        }
    });

    sendReplyBtn.addEventListener('click', function () {
        if (!currentEmail) return;

        const emailId = replyModal.dataset.emailId;
        const to = document.getElementById('reply-to').textContent;
        const subject = document.getElementById('reply-subject').textContent;
        const body = replyContent.value;

        if (!body.trim()) {
            showToast("Reply content cannot be empty", "error");
            return;
        }

        sendReply(emailId, to, subject, body);
    });

    editReplyBtn.addEventListener('click', function () {
        replyContent.readOnly = !replyContent.readOnly;
        editReplyBtn.innerHTML = replyContent.readOnly
            ? '<i class="fas fa-edit"></i> Edit'
            : '<i class="fas fa-lock"></i> Lock';
    });

    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    async function safeLoadEmails() {
        try {
            await loadEmails();
        } catch (error) {
            console.error("Email loading failed:", error);
            showToast(error.message || "Failed to load emails", "error");
        }
    }

    function setupAutoReplyToggle() {
        if (!autoReplyToggle || !autoReplyStatus) return;
    
        // Get current status from backend
        fetch('/auto-reply/status')
            .then(res => res.json())
            .then(data => {
                autoReplyToggle.checked = data.auto_reply_enabled;
                autoReplyStatus.textContent = data.auto_reply_enabled ? "ON" : "OFF";
            })
            .catch(err => {
                console.error("Failed to fetch auto-reply status:", err);
                autoReplyStatus.textContent = "Unavailable";
            });
    
        // On toggle
        autoReplyToggle.addEventListener('change', () => {
            const enabled = autoReplyToggle.checked;
    
            fetch('/auto-reply/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            })
            .then(res => res.json())
            .then(data => {
                showToast(data.message || "Auto-reply mode updated");
                autoReplyStatus.textContent = enabled ? "ON" : "OFF";
            })
            .catch(err => {
                console.error("Failed to toggle auto-reply:", err);
                showToast("Failed to update auto-reply mode", "error");
                autoReplyToggle.checked = !enabled;
                autoReplyStatus.textContent = autoReplyToggle.checked ? "ON" : "OFF";
            });
        });
    }
    

    async function loadEmails() {
        const now = Date.now();
        if (isFetching || (now - lastFetchTime < FETCH_COOLDOWN)) return;

        isFetching = true;
        lastFetchTime = now;

        showLoading();

        try {
            const response = await fetch('/api/emails');

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to load emails');
            }

            renderEmails(data.emails);
        } catch (error) {
            console.error('Error:', error);
            showToast(error.message, "error");
        } finally {
            isFetching = false;
            hideLoading();
        }
    }
    
    function renderEmails(emails) {
        if (!emails || emails.length === 0) {
            emailList.innerHTML = '<div class="empty-state">No emails found</div>';
            return;
        }
    
        emailList.innerHTML = '';
    
        emails.forEach(email => {
            console.log("Email object:", email);  // Debugging
    
            const emailId = email.message_id || email.id || '';
            const emailBody = email.snippet || 'No content'; // ✅ Using snippet instead of body
    
            const emailItem = document.createElement('div');
            emailItem.className = 'email-item';
            emailItem.dataset.id = emailId;
    
            emailItem.innerHTML = `
                <div class="email-header">
                    <span class="email-sender">${escapeHtml(email.from)}</span>
                    <span class="email-date">${escapeHtml(email.date)}</span>
                </div>
                <div class="email-subject">${escapeHtml(email.subject)}</div>
                <div class="email-body">${escapeHtml(emailBody)}</div>
                <div class="email-actions">
                    <button class="reply-btn" data-id="${escapeHtml(emailId)}">
                        <i class="fas fa-reply"></i> Reply
                    </button>
                </div>
            `;
    
            emailItem.querySelector('.reply-btn').addEventListener('click', (e) => {
                const button = e.currentTarget;
                const id = button.dataset.id;
                if (!id) {
                    showToast("Failed to generate reply: Email ID missing", "error");
                    return;
                }
                generateReply(id);
            });
    
            emailList.appendChild(emailItem);
        });
    }
    
    
    
    

    function searchEmails() {
        const query = searchInput.value.trim().toLowerCase();
        if (!query) {
            loadEmails();
            return;
        }

        const emailItems = document.querySelectorAll('.email-item');
        emailItems.forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(query) ? 'block' : 'none';
        });
    }

    async function generateReply(emailId) {
        if (!emailId) {
            console.error("No email ID provided");
            showToast("Cannot generate reply: Missing email ID", "error");
            return;
        }

        if (isFetching) return;
        isFetching = true;

        showLoading();

        try {
            const response = await fetch('/api/reply/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ email_id: emailId })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to generate reply');
            }

            currentEmail = {
                id: emailId,
                from: data.sender,
                subject: data.subject
            };

            document.getElementById('reply-to').textContent = data.sender;
            document.getElementById('reply-subject').textContent = `Re: ${data.subject}`;
            replyContent.value = data.reply;
            replyContent.readOnly = true;
            replyModal.dataset.emailId = emailId;
            editReplyBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';

            openModal();

            if (data.analysis) {
                showToast(`Email priority: ${data.analysis.priority || 'normal'}`);
            }

        } catch (error) {
            console.error('Error:', error);
            showToast(error.message, "error");
        } finally {
            isFetching = false;
            hideLoading();
        }
    }

    async function sendReply(emailId, to, subject, body) {
        if (isFetching) return;
        isFetching = true;

        showLoading();

        try {
            const response = await fetch('/api/reply/send', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    email_id: emailId,
                    to: to,
                    subject: subject,
                    body: body
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to send reply');
            }

            showToast('Reply sent successfully!');
            closeModal();
            await safeLoadEmails();

        } catch (error) {
            console.error('Error:', error);
            showToast(error.message, "error");
        } finally {
            isFetching = false;
            hideLoading();
        }
    }

    // Utilities
    function escapeHtml(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function formatDate(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            return isNaN(date.getTime()) ? '' :
                date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } catch {
            return '';
        }
    }

    function openModal() {
        replyModal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        replyModal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }

    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(toast);
                }, 300);
            }, 3000);
        }, 10);
    }

    function showLoading() {
        const loader = document.createElement('div');
        loader.className = 'loader';
        loader.id = 'page-loader';
        document.body.appendChild(loader);
    }

    function hideLoading() {
        const loader = document.getElementById('page-loader');
        if (loader) loader.remove();
    }
      
});
