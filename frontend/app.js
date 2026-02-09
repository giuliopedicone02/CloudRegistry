/**
 * CLOUD REGISTRY - APPLICATION JAVASCRIPT
 * Main application logic for the Cloud Registry system
 */

// ============================================
// CONFIGURATION & INITIALIZATION
// ============================================

// Check if config exists
if (typeof window.apiConfig === 'undefined') {
    alert("Errore: config.js mancante. Assicurati di avere il file di configurazione.");
}

// Cognito configuration
const poolData = {
    UserPoolId: window.apiConfig.UserPoolId,
    ClientId: window.apiConfig.ClientId
};
const apiBaseUrl = window.apiConfig.ApiUrl;
const userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);

// Global state
let currentUser = null;
let userData = {};
let allStudents = [];
let NOTE_API_URL = null;
let currentStudentEmail = null;

// ============================================
// UTILITY FUNCTIONS
// ============================================

/**
 * Switch between different views
 */
function switchView(viewId) {
    document.querySelectorAll('.view-container').forEach(el => {
        el.classList.remove('visible');
    });
    document.getElementById(viewId).classList.add('visible');
}

/**
 * Show toast notification
 */
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.className = `toast ${type}`;
    toast.textContent = (type === 'success' ? '✅ ' : '❌ ') + message;
    toast.classList.add('active');

    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => {
            toast.classList.remove('active', 'hiding');
        }, 300);
    }, 3000);
}

/**
 * Toggle class input visibility based on role
 */
function toggleClasseInput() {
    const role = document.getElementById('reg-role').value;
    const classGroup = document.getElementById('class-input-group');
    classGroup.style.display = (role === 'Teacher') ? 'none' : 'block';
}

// ============================================
// AUTHENTICATION FUNCTIONS
// ============================================

/**
 * Register new user
 */
function register() {
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-pass').value;
    const firstName = document.getElementById('reg-name').value.trim();
    const lastName = document.getElementById('reg-surname').value.trim();
    const role = document.getElementById('reg-role').value;
    let classe = document.getElementById('reg-class').value.toUpperCase().trim();

    if (!email || !password || !firstName || !lastName) {
        showToast("Compila tutti i campi", "error");
        return;
    }

    if (role === 'Teacher') classe = 'N/A';

    const attributes = [
        new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "email", Value: email }),
        new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "given_name", Value: firstName }),
        new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "family_name", Value: lastName }),
        new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "custom:role", Value: role }),
        new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "custom:classe", Value: classe })
    ];

    userPool.signUp(email, password, attributes, null, (err) => {
        if (err) {
            showToast(err.message || "Errore durante la registrazione", "error");
            return;
        }
        showToast("Codice inviato via email!");
        document.getElementById('verify-email').value = email;
        setTimeout(() => switchView('view-verify'), 1000);
    });
}

/**
 * Confirm email verification
 */
async function confirmVerification() {
    const email = document.getElementById('verify-email').value;
    const code = document.getElementById('verify-code').value.trim();

    if (!code) {
        showToast("Inserisci il codice", "error");
        return;
    }

    const user = new AmazonCognitoIdentity.CognitoUser({
        Username: email,
        Pool: userPool
    });

    user.confirmRegistration(code, true, async (err) => {
        if (err) {
            showToast(err.message || "Codice non valido", "error");
            return;
        }

        showToast("Account verificato!");

        // Subscribe student to SNS notifications
        try {
            const response = await fetch(apiBaseUrl + "/voto", {
                method: 'POST',
                body: JSON.stringify({
                    action: 'subscribe_student',
                    email: email
                })
            });

            if (response.ok) {
                showToast("Ti abbiamo inviato una email di conferma SNS. Controlla la tua casella!", "success");
            } else {
                console.error("Errore sottoscrizione SNS");
            }
        } catch (e) {
            console.error("Errore chiamata SNS:", e);
        }

        setTimeout(() => switchView('view-login'), 2000);
    });
}

/**
 * Login user
 */
function login() {
    const email = document.getElementById('login-user').value.trim();
    const password = document.getElementById('login-pass').value.trim();

    if (!email || !password) {
        showToast("Inserisci email e password", "error");
        return;
    }

    const user = new AmazonCognitoIdentity.CognitoUser({
        Username: email,
        Pool: userPool
    });

    const authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
        Username: email,
        Password: password
    });

    user.authenticateUser(authDetails, {
        onSuccess: (result) => {
            currentUser = user;
            showToast("Login effettuato!");
            loadUserProfile();
        },
        onFailure: (err) => {
            console.error("Errore login:", err);
            showToast("Errore: " + (err.message || "Login fallito"), 'error');
        },
        newPasswordRequired: (userAttributes, requiredAttributes) => {
            const newPassword = prompt("Primo accesso. Imposta una nuova password:");
            if (newPassword) {
                user.completeNewPasswordChallenge(newPassword, {}, {
                    onSuccess: () => {
                        showToast("Password aggiornata!");
                        setTimeout(() => login(), 500);
                    },
                    onFailure: (e) => showToast("Errore cambio password: " + e.message, 'error')
                });
            }
        }
    });
}

/**
 * Load user profile and redirect to appropriate view
 */
function loadUserProfile() {
    if (!currentUser) return;

    currentUser.getUserAttributes((err, attrs) => {
        if (err) {
            console.error("Errore attributi:", err);
            showToast("Impossibile recuperare i dati utente", "error");
            return;
        }

        userData = {};
        attrs.forEach(attr => {
            userData[attr.getName()] = attr.getValue();
        });

        const name = `${userData['given_name'] || ''} ${userData['family_name'] || ''}`.trim() || userData['email'];
        const role = userData['custom:role'] || 'Student';
        const email = userData['email'];
        const avatarLetter = name.charAt(0).toUpperCase();

        console.log("User logged in:", { name, role, email });

        if (role === 'Teacher') {
            document.getElementById('teacher-name-display').textContent = name;
            document.getElementById('teacher-avatar').textContent = avatarLetter;
            setupTeacher();
        } else {
            document.getElementById('student-name-display').textContent = name;
            document.getElementById('student-avatar').textContent = avatarLetter;
            setupStudent(email);
        }
    });
}

/**
 * Logout user
 */
function logout() {
    if (currentUser) currentUser.signOut();
    location.reload();
}

// ============================================
// INFRASTRUCTURE FUNCTIONS
// ============================================

/**
 * Get Docker container IP address
 */
async function ensureDockerIP() {
    if (NOTE_API_URL) return true;

    try {
        const response = await fetch(apiBaseUrl + "/voto", {
            method: 'POST',
            body: JSON.stringify({ action: 'get_container_ip' })
        });
        const data = await response.json();

        if (data.ip) {
            NOTE_API_URL = "http://" + data.ip;
            console.log("Docker IP found:", NOTE_API_URL);
            return true;
        }
    } catch (e) {
        console.error("Error getting Docker IP:", e);
    }
    return false;
}

// ============================================
// TEACHER VIEW FUNCTIONS
// ============================================

/**
 * Setup teacher dashboard
 */
async function setupTeacher() {
    switchView('view-teacher');
    loadStudents();
}

/**
 * Load students list
 */
async function loadStudents() {
    try {
        const response = await fetch(apiBaseUrl + "/voto", {
            method: 'POST',
            body: JSON.stringify({ action: 'get_students' })
        });
        const data = await response.json();

        if (data.students) {
            allStudents = data.students;
            const select = document.getElementById('filter-class');
            select.innerHTML = '<option value="ALL">Tutte le classi</option>';
            data.classes.forEach(c => {
                select.innerHTML += `<option value="${c}">${c}</option>`;
            });
            renderStudentTable();
        }
    } catch (e) {
        console.error("Error loading students:", e);
        showToast("Errore caricamento studenti", "error");
    }
}

/**
 * Render student table
 */
function renderStudentTable() {
    const filter = document.getElementById('filter-class').value;
    const tbody = document.getElementById('student-table-body');
    tbody.innerHTML = '';

    const list = filter === 'ALL' ? allStudents : allStudents.filter(s => s.classe === filter);

    if (list.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="3" class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <p>Nessuno studente trovato</p>
                </td>
            </tr>`;
        return;
    }

    list.forEach(student => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div style="font-weight: 600; margin-bottom: 4px;">${student.display_name}</div>
                <div style="font-size: 0.875rem; color: var(--secondary);">${student.email}</div>
            </td>
            <td>
                <span style="background: var(--gradient-primary); color: white; padding: 4px 12px; border-radius: 12px; font-weight: 600; font-size: 0.875rem;">
                    ${student.classe}
                </span>
            </td>
            <td>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <button class="btn btn-primary btn-sm" onclick="apriVoto('${student.email}', '${student.display_name}')">
                        📝 Voto
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="apriStoricoVoti('${student.email}', '${student.display_name}')">
                        📜 Storico
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="apriNoteTeacher('${student.email}', '${student.display_name}')">
                        ⚠️ Note
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

// ============================================
// GRADE MANAGEMENT FUNCTIONS
// ============================================

/**
 * Open grade modal
 */
function apriVoto(email, name) {
    currentStudentEmail = email;
    document.getElementById('modal-student-name').textContent = name;
    document.getElementById('modal-materia').value = '';
    document.getElementById('modal-voto').value = '';
    document.getElementById('voto-modal').classList.add('active');
    setTimeout(() => document.getElementById('modal-materia').focus(), 300);

    // Enter key support
    document.getElementById('modal-voto').onkeypress = function (e) {
        if (e.key === 'Enter') confermaVoto();
    };
}

/**
 * Close grade modal
 */
function closeVotoModal() {
    document.getElementById('voto-modal').classList.remove('active');
}

/**
 * Confirm and submit grade
 */
async function confermaVoto() {
    const materia = document.getElementById('modal-materia').value.trim();
    const voto = document.getElementById('modal-voto').value.trim();

    if (!materia || !voto) {
        showToast("Compila tutti i campi", "error");
        return;
    }

    const teacher = document.getElementById('teacher-name-display').textContent;

    try {
        await fetch(apiBaseUrl + "/voto", {
            method: 'POST',
            body: JSON.stringify({
                action: 'add_grade',
                teacher_name: teacher,
                student_email: currentStudentEmail,
                materia: materia,
                voto: voto
            })
        });
        showToast("Voto inserito con successo!");
        closeVotoModal();
    } catch (e) {
        console.error("Error adding grade:", e);
        showToast("Errore durante l'inserimento", "error");
    }
}

/**
 * Open grade history modal
 */
async function apriStoricoVoti(email, name) {
    currentStudentEmail = email;
    document.getElementById('history-student-name').textContent = name;
    document.getElementById('history-modal').classList.add('active');
    const list = document.getElementById('history-list');
    list.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Caricamento...</p></div>';

    try {
        const response = await fetch(apiBaseUrl + "/voto?email=" + email);
        const data = await response.json();

        list.innerHTML = '';
        if (!data.voti || data.voti.length === 0) {
            list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📚</div><p>Nessun voto presente</p></div>';
            return;
        }

        data.voti.forEach(voto => {
            if (voto.voto) {
                const sk = `VOTO#${voto.data}`;
                const item = document.createElement('div');
                item.className = 'grade-item';
                item.innerHTML = `
                    <div class="grade-header">
                        <div>
                            <div class="grade-subject">${voto.materia}</div>
                            <div class="grade-meta">
                                <span>${new Date(voto.data).toLocaleDateString('it-IT')}</span>
                                <span>Prof. ${voto.teacher || 'N/D'}</span>
                            </div>
                        </div>
                        <div class="grade-value">${voto.voto}</div>
                    </div>
                    <button class="delete-btn" onclick="cancellaVoto('${sk}')">🗑️</button>
                `;
                list.appendChild(item);
            }
        });
    } catch (e) {
        console.error("Error loading history:", e);
        list.innerHTML = '<div class="empty-state"><p style="color: var(--danger)">Errore caricamento</p></div>';
    }
}

/**
 * Close history modal
 */
function closeHistoryModal() {
    document.getElementById('history-modal').classList.remove('active');
}

/**
 * Delete grade
 */
async function cancellaVoto(sk) {
    if (!confirm("Sicuro di voler eliminare questo voto?")) return;

    try {
        const response = await fetch(apiBaseUrl + "/voto", {
            method: 'POST',
            body: JSON.stringify({
                action: 'delete_grade',
                student_email: currentStudentEmail,
                sk: sk
            })
        });

        if (response.ok) {
            showToast("Voto eliminato!");
            apriStoricoVoti(currentStudentEmail, document.getElementById('history-student-name').textContent);
        } else {
            showToast("Errore durante la cancellazione", "error");
        }
    } catch (e) {
        console.error("Error deleting grade:", e);
        showToast("Errore di rete", "error");
    }
}

// ============================================
// NOTES MANAGEMENT FUNCTIONS
// ============================================

/**
 * Open teacher notes view
 */
async function apriNoteTeacher(email, name) {
    currentStudentEmail = email;
    document.getElementById('note-student-name').textContent = name;
    switchView('view-notes');
    document.getElementById('lista-note').innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Connessione Docker...</p></div>';

    if (await ensureDockerIP()) {
        loadNotes(email, 'lista-note', true);
    } else {
        document.getElementById('lista-note').innerHTML = "<div class='empty-state'><div class='empty-state-icon'>⚠️</div><p style='color: var(--danger)'>Container Docker non raggiungibile</p></div>";
    }
}

/**
 * Submit new note
 */
async function inviaNota() {
    const text = document.getElementById('note-text').value.trim();
    const teacher = document.getElementById('teacher-name-display').textContent;

    if (!text) {
        showToast("Scrivi il testo della nota", "error");
        return;
    }

    try {
        await fetch(`${NOTE_API_URL}/note`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_email: currentStudentEmail,
                testo: text,
                teacher: teacher
            })
        });
        showToast("Nota inserita con successo!");
        document.getElementById('note-text').value = '';
        loadNotes(currentStudentEmail, 'lista-note', true);
    } catch (e) {
        console.error("Error adding note:", e);
        showToast("Errore durante l'invio", "error");
    }
}

/**
 * Delete note
 */
async function cancellaNota(sk) {
    if (!confirm("Eliminare questa nota?")) return;

    try {
        const response = await fetch(`${NOTE_API_URL}/note`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_email: currentStudentEmail,
                sk: sk
            })
        });

        if (response.ok) {
            showToast("Nota eliminata!");
            loadNotes(currentStudentEmail, 'lista-note', true);
        } else {
            showToast("Errore durante la cancellazione", "error");
        }
    } catch (e) {
        console.error("Error deleting note:", e);
        showToast("Errore di rete", "error");
    }
}

// ============================================
// STUDENT VIEW FUNCTIONS
// ============================================

/**
 * Setup student dashboard
 */
async function setupStudent(email) {
    switchView('view-student');

    try {
        const response = await fetch(apiBaseUrl + "/voto?email=" + email);
        const data = await response.json();

        console.log("Student data received:", data);

        // Render averages
        const avgContainer = document.getElementById('lista-medie');
        avgContainer.innerHTML = '';

        if (data.medie && Object.keys(data.medie).length > 0) {
            for (const [materia, valore] of Object.entries(data.medie)) {
                if (materia !== 'Sconosciuta') {
                    const card = document.createElement('div');
                    card.className = 'stat-card';
                    card.innerHTML = `
                        <div class="stat-label">${materia}</div>
                        <div class="stat-value">${valore}</div>
                    `;
                    avgContainer.appendChild(card);
                }
            }
        } else {
            avgContainer.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📊</div><p>Nessuna media disponibile</p></div>';
        }

        // Render grades
        const gradeContainer = document.getElementById('lista-voti');
        gradeContainer.innerHTML = '';

        if (data.voti && data.voti.length > 0) {
            data.voti.forEach(voto => {
                if (voto.voto) {
                    const teacher = voto.teacher_name || voto.teacher || voto.docente || 'Non specificato';
                    const item = document.createElement('div');
                    item.className = 'grade-item';
                    item.innerHTML = `
                        <div class="grade-header">
                            <div class="grade-subject">${voto.materia}</div>
                            <div class="grade-value">${voto.voto}</div>
                        </div>
                        <div class="grade-meta">
                            <span><strong>Docente:</strong> ${teacher}</span>
                            <span><strong>Data:</strong> ${new Date(voto.data).toLocaleDateString('it-IT')}</span>
                        </div>
                    `;
                    gradeContainer.appendChild(item);
                }
            });
        } else {
            gradeContainer.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📚</div><p>Nessun voto registrato</p></div>';
        }

        // Load notes
        const notesContainer = document.getElementById('student-notes-list');
        notesContainer.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>Connessione note...</p></div>';

        if (await ensureDockerIP()) {
            loadNotes(email, 'student-notes-list', false);
        } else {
            notesContainer.innerHTML = "<div class='empty-state'><div class='empty-state-icon'>⚠️</div><p style='color: var(--danger)'>Servizio note non disponibile</p></div>";
        }

    } catch (e) {
        console.error("Error loading student data:", e);
        showToast("Errore caricamento dati", "error");
    }
}

/**
 * Load notes (shared function)
 */
async function loadNotes(email, containerId, isTeacher) {
    const container = document.getElementById(containerId);

    try {
        const response = await fetch(`${NOTE_API_URL}/note?email=${email}`);
        const notes = await response.json();

        container.innerHTML = '';

        if (notes.length === 0) {
            container.innerHTML = "<div class='empty-state'><div class='empty-state-icon'>✅</div><p>Nessuna nota disciplinare</p></div>";
        } else {
            notes.forEach(note => {
                const item = document.createElement('div');
                item.className = 'note-item';
                item.innerHTML = `
                    ${isTeacher ? `<button class="delete-btn" onclick="cancellaNota('${note.SK}')">🗑️</button>` : ''}
                    <p style="margin: 0 0 12px 0; font-size: 1.1rem;">"${note.testo}"</p>
                    <div class="grade-meta">
                        <span><strong>Docente:</strong> ${note.teacher}</span>
                        <span><strong>Data:</strong> ${new Date(note.data).toLocaleDateString('it-IT')}</span>
                    </div>
                `;
                container.appendChild(item);
            });
        }
    } catch (e) {
        console.error("Error loading notes:", e);
        container.innerHTML = '<div class="empty-state"><p style="color: var(--danger)">Errore caricamento note</p></div>';
    }
}

// ============================================
// SESSION MANAGEMENT
// ============================================

/**
 * Check if user has active session on page load
 */
(function checkSession() {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser != null) {
        cognitoUser.getSession(function (err, session) {
            if (err) {
                console.log("No valid session");
                return;
            }
            if (session.isValid()) {
                console.log("Session valid, restoring user");
                currentUser = cognitoUser;
                loadUserProfile();
            }
        });
    }
})();