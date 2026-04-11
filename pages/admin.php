<?php
/**
 * MAGA Z — Secret Admin Portal
 * Hidden dashboard for system updates and data import
 */

// Safety check: ensure integrity definitions are loaded
if (!defined('_SYS_INTEGRITY_CHECKSUM_')) {
    die("❌ Error: Core integrity check failed.");
}

// Handle Logout
if (isset($_GET['logout'])) {
    unset($_SESSION['maga_admin_auth']);
    header('Location: ?page=home');
    exit;
}

// Handle Authentication
$error = '';
if (isset($_POST['admin_key'])) {
    if (validateCoreIntegrity($_POST['admin_key'])) {
        $_SESSION['maga_admin_auth'] = true;
    } else {
        $error = 'คีย์รักษาระดับความปลอดภัยไม่ถูกต้อง';
    }
}

$isAuthenticated = $_SESSION['maga_admin_auth'] ?? false;

// --- AJAX Batch Import Handler ---
$isApiAuth = false;
if (isset($_SERVER['HTTP_X_ADMIN_KEY'])) {
    $isApiAuth = validateCoreIntegrity($_SERVER['HTTP_X_ADMIN_KEY']);
}

if (($isAuthenticated || $isApiAuth) && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['ajax_import'])) {
    header('Content-Type: application/json');
    $input = file_get_contents('php://input');
    $data = json_decode($input, true);

    if (!$data) {
        echo json_encode(['success' => false, 'message' => 'Invalid JSON data']);
        exit;
    }

    try {
        $pdo = getDB();
        
        // Auto-migration: Check if sort_order exists
        $cols = $pdo->query("SHOW COLUMNS FROM animes LIKE 'sort_order'")->fetch();
        if (!$cols) {
            $pdo->exec("ALTER TABLE animes ADD COLUMN sort_order INT NOT NULL DEFAULT 0");
            $pdo->exec("ALTER TABLE animes ADD INDEX (sort_order)");
        }

        // Get category map
        $catMap = [];
        foreach ($pdo->query("SELECT id, source_id FROM categories")->fetchAll() as $row) {
            $catMap[$row['source_id']] = (int)$row['id'];
        }

        $insertAnime = $pdo->prepare("
            INSERT INTO animes (category_id, title, link, cover, sort_order) 
            VALUES (:catId, :title, :link, :cover, :sortOrder)
            ON DUPLICATE KEY UPDATE 
                title = VALUES(title), 
                cover = VALUES(cover),
                category_id = VALUES(category_id),
                sort_order = VALUES(sort_order)
        ");
        
        $insertEpisode = $pdo->prepare("
            INSERT INTO episodes (anime_id, title, url, sort_order) 
            VALUES (:animeId, :title, :url, :sortOrder)
        ");

        $totalAnime = 0;
        $totalEpisodes = 0;

        // Reverse categories so Movie is handled first, then Sub, then Dub
        // This makes the 'first' categories in JSON (Dub) get the 'last' (highest) IDs
        $dataReversed = array_reverse($data, true);
        
        foreach ($dataReversed as $sourceId => $catData) {
            $categoryId = $catMap[$sourceId] ?? null;
            if (!$categoryId) continue;
            
            $animes = $catData['animes'] ?? [];
            $pdo->beginTransaction();
            // Reverse anime list so older items are inserted first
            // Meaning newest items in the JSON list get the highest IDs
            $animesReversed = array_reverse($animes);
            
            foreach ($animesReversed as $animeData) {
                $link = $animeData['link'] ?? '';
                if (empty($link)) continue;
                
                $insertAnime->execute([
                    ':catId' => $categoryId,
                    ':title' => $animeData['title'] ?? '',
                    ':link'  => $link,
                    ':cover' => $animeData['cover'] ?? '',
                    ':sortOrder' => $animeData['sort_order'] ?? 0,
                ]);
                
                $animeId = $pdo->lastInsertId();
                if (!$animeId) {
                    $stmt = $pdo->prepare("SELECT id FROM animes WHERE link = ?");
                    $stmt->execute([$link]);
                    $animeId = (int)$stmt->fetchColumn();
                }
                
                if ($animeId) {
                    $pdo->prepare("DELETE FROM episodes WHERE anime_id = ?")->execute([$animeId]);
                    foreach ($animeData['episodes'] ?? [] as $idx => $ep) {
                        $insertEpisode->execute([
                            ':animeId'   => $animeId,
                            ':title'     => $ep['title'] ?? '',
                            ':url'       => $ep['url'] ?? '',
                            ':sortOrder' => $idx,
                        ]);
                        $totalEpisodes++;
                    }
                }
                $totalAnime++;
            }
            $pdo->commit();
        }

        echo json_encode(['success' => true, 'total_anime' => $totalAnime, 'total_episodes' => $totalEpisodes]);
        exit;
    } catch (Exception $e) {
        echo json_encode(['success' => false, 'message' => $e->getMessage()]);
        exit;
    }
}

// --- AJAX Clear Data Handler ---
if ($isAuthenticated && $_SERVER['REQUEST_METHOD'] === 'POST' && isset($_GET['ajax_clear'])) {
    header('Content-Type: application/json');
    try {
        $pdo = getDB();
        $pdo->exec("SET FOREIGN_KEY_CHECKS = 0");
        $pdo->exec("TRUNCATE TABLE episodes");
        $pdo->exec("TRUNCATE TABLE animes");
        $pdo->exec("SET FOREIGN_KEY_CHECKS = 1");
        echo json_encode(['success' => true, 'message' => 'ล้างข้อมูลทั้งหมดเรียบร้อยแล้ว']);
    } catch (Exception $e) {
        echo json_encode(['success' => false, 'message' => $e->getMessage()]);
    }
    exit;
}

// Handle Traditional File Import (Keep for small files or legacy)
$importLog = [];
if ($isAuthenticated && isset($_FILES['anime_data'])) {
    $file = $_FILES['anime_data'];
    
    if ($file['error'] === UPLOAD_ERR_OK) {
        $content = file_get_contents($file['tmp_name']);
        
        // Clean JS wrapper
        $content = preg_replace('/^const\s+animeData\s*=\s*/', '', $content);
        $content = rtrim($content);
        if (substr($content, -1) === ';') {
            $content = substr($content, 0, -1);
        }
        
        $data = json_decode($content, true);
        
        if ($data === null) {
            $importLog[] = "❌ Parse JSON ไม่สำเร็จ: " . json_last_error_msg();
        } else {
            $importLog[] = "✅ อ่านข้อมูลสำเร็จ! พบ " . count($data) . " หมวดหมู่";
            
            $pdo = getDB();
            
            // Get category map
            $catMap = [];
            foreach ($pdo->query("SELECT id, source_id FROM categories")->fetchAll() as $row) {
                $catMap[$row['source_id']] = (int)$row['id'];
            }
            
            // Statements
            $insertAnime = $pdo->prepare("
                INSERT INTO animes (category_id, title, link, cover, sort_order) 
                VALUES (:catId, :title, :link, :cover, :sortOrder)
                ON DUPLICATE KEY UPDATE 
                    title = VALUES(title), 
                    cover = VALUES(cover),
                    category_id = VALUES(category_id),
                    sort_order = VALUES(sort_order)
            ");
            $insertEpisode = $pdo->prepare("
                INSERT INTO episodes (anime_id, title, url, sort_order) 
                VALUES (:animeId, :title, :url, :sortOrder)
            ");

            $totalAnime = 0;
            $totalEpisodes = 0;
            
            foreach ($data as $sourceId => $catData) {
                $categoryId = $catMap[$sourceId] ?? null;
                if (!$categoryId) continue;
                
                $animes = $catData['animes'] ?? [];
                $pdo->beginTransaction();
                try {
                    foreach ($animes as $animeData) {
                        $link = $animeData['link'] ?? '';
                        if (empty($link)) continue;
                        
                        $insertAnime->execute([
                            ':catId' => $categoryId,
                            ':title' => $animeData['title'] ?? '',
                            ':link'  => $link,
                            ':cover' => $animeData['cover'] ?? '',
                            ':sortOrder' => $animeData['sort_order'] ?? 0,
                        ]);
                        
                        $animeId = $pdo->lastInsertId();
                        if (!$animeId) {
                            $stmt = $pdo->prepare("SELECT id FROM animes WHERE link = ?");
                            $stmt->execute([$link]);
                            $animeId = (int)$stmt->fetchColumn();
                        }
                        
                        if ($animeId) {
                            $pdo->prepare("DELETE FROM episodes WHERE anime_id = ?")->execute([$animeId]);
                            foreach ($animeData['episodes'] ?? [] as $idx => $ep) {
                                $insertEpisode->execute([
                                    ':animeId'   => $animeId,
                                    ':title'     => $ep['title'] ?? '',
                                    ':url'       => $ep['url'] ?? '',
                                    ':sortOrder' => $idx,
                                ]);
                                $totalEpisodes++;
                            }
                        }
                        $totalAnime++;
                    }
                    $pdo->commit();
                    $importLog[] = "📁 หมวดหมู่ '{$catData['name']}': สำเร็จ";
                } catch (Exception $e) {
                    $pdo->rollBack();
                    $importLog[] = "❌ Error ในหมวด '{$catData['name']}': " . $e->getMessage();
                }
            }
            $importLog[] = "🎉 นำเข้าเสร็จสมบูรณ์! (อนิเมะ: $totalAnime เรื่อง, ตอน: $totalEpisodes ตอน)";
        }
    } else {
        $uploadErrorMessages = [
            UPLOAD_ERR_INI_SIZE   => "ไฟล์มีขนาดใหญ่เกินกว่าที่เซิร์ฟเวอร์กำหนด (upload_max_filesize ใน php.ini)",
            UPLOAD_ERR_FORM_SIZE  => "ไฟล์มีขนาดใหญ่เกินกว่าที่แบบฟอร์มกำหนด",
            UPLOAD_ERR_PARTIAL   => "ไฟล์ถูกอัปโหลดเพียงบางส่วนเท่านั้น",
            UPLOAD_ERR_NO_FILE    => "ไม่มีไฟล์ถูกอัปโหลด",
            UPLOAD_ERR_NO_TMP_DIR => "ไม่พบโฟลเดอร์ชั่วคราวสำหรับเก็บไฟล์",
            UPLOAD_ERR_CANT_WRITE => "ไม่สามารถเขียนไฟล์ลงดิสก์ได้",
            UPLOAD_ERR_EXTENSION  => "ปลั๊กอินของ PHP หยุดการอัปโหลดไฟล์",
        ];
        $errCode = $file['error'];
        $errMsg = $uploadErrorMessages[$errCode] ?? "ข้อผิดพลาดที่ไม่รู้จัก (Code: $errCode)";
        $importLog[] = "❌ เกิดข้อผิดพลาดในการอัปโหลดไฟล์: $errMsg";
    }
}

$pageTitle = 'Secret Admin Portal — MAGA Z';
include __DIR__ . '/../includes/header.php';
?>

<div class="admin-portal-container padding-shop" style="min-height: 80vh; display: flex; align-items: center; justify-content: center;">
    
    <?php if (!$isAuthenticated): ?>
        <!-- Login Screen -->
        <div class="admin-card auth-card">
            <div class="admin-header">
                <i class="ri-shield-keyhole-line"></i>
                <h2>Core Integrity Authentication</h2>
                <p>กรุณาระบุคีย์รักษาระดับความปลอดภัยเพื่อเข้าถึงระบบจัดการ</p>
            </div>
            
            <form action="?page=admin" method="POST" class="admin-form">
                <?php if ($error): ?>
                    <div class="admin-alert error"><?= $error ?></div>
                <?php endif; ?>
                
                <div class="admin-input-group">
                    <label for="admin_key">SECRET ACCESS KEY</label>
                    <input type="password" name="admin_key" id="admin_key" placeholder="9a8b7c6d..." required>
                </div>
                
                <button type="submit" class="admin-btn-primary">
                    <i class="ri-door-open-line"></i> เข้าสู่ระบบจัดการ
                </button>
            </form>
            
            <div class="admin-footer">
                <a href="?page=home"><i class="ri-arrow-left-line"></i> กลับสู่หน้าหลัก</a>
            </div>
        </div>

    <?php else: ?>
        <!-- Admin Dashboard -->
        <div class="admin-card dashboard-card">
            <div class="admin-header">
                <div class="admin-badge">ADMIN ACCESS GRANTED</div>
                <h2>System Update Dashboard</h2>
                <p>จัดการอัปเดตข้อมูลอนิเมะจากไฟล์สแกนล่าสุด</p>
            </div>
            
            <div class="admin-content">
                
                <div class="admin-section">
                    <h3><i class="ri-upload-cloud-2-line"></i> นำเข้าข้อมูลอนิเมะ</h3>
                    <p class="section-desc">อัปโหลดไฟล์ <code>anime_data.js</code> จากโปรแกรมสแกนเพื่ออัปเดตฐานข้อมูล</p>
                    
                    <form action="?page=admin" method="POST" enctype="multipart/form-data" class="upload-form" id="mainUploadForm">
                        <div class="file-drop-zone" id="dropZone">
                            <i class="ri-file-code-line"></i>
                            <div class="file-info">
                                <span>คลิกเพื่อเลือกไฟล์ หรือลากไฟล์มาวางที่นี่</span>
                                <small>ต้องเป็นไฟล์ anime_data.js หรือไฟล์ JSON เท่านั้น</small>
                            </div>
                            <input type="file" name="anime_data" id="fileInput" accept=".js,.json" required>
                        </div>
                        
                        <div class="selected-file-name" id="fileNameDisplay" style="display: none;"></div>
                        
                        <!-- Progress UI -->
                        <div id="importProgressContainer" style="display: none; margin-top: 20px;">
                            <div class="progress-info" style="display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 0.85rem;">
                                <span id="progressStatus">กำลังเตรียมความพร้อม...</span>
                                <span id="progressPercent">0%</span>
                            </div>
                            <div class="progress-bar-bg" style="height: 10px; background: var(--admin-bg); border-radius: 10px; overflow: hidden; border: 1px solid var(--admin-border);">
                                <div id="progressBarFill" style="height: 100%; width: 0%; background: var(--admin-accent); transition: width 0.3s ease;"></div>
                            </div>
                        </div>

                        <button type="submit" class="admin-btn-success" id="submitBtn" disabled>
                            <i class="ri-refresh-line"></i> เริ่มการนำเข้าข้อมูล
                        </button>
                    </form>
                </div>

                <div class="admin-section info-section">
                    <h3><i class="ri-information-line"></i> ข้อมูลระบบ (System Info)</h3>
                    <div class="system-stats">
                        <div class="stat-item">
                            <span>Upload Max Size:</span>
                            <strong><?= ini_get('upload_max_filesize') ?></strong>
                        </div>
                        <div class="stat-item">
                            <span>Post Max Size:</span>
                            <strong><?= ini_get('post_max_size') ?></strong>
                        </div>
                        <div class="stat-item">
                            <span>Memory Limit:</span>
                            <strong><?= ini_get('memory_limit') ?></strong>
                        </div>
                    </div>
                    <button type="button" onclick="clearAllData()" class="admin-btn-danger" style="margin-top: 15px; background: #ef4444; color: white; border: none; padding: 10px; width: 100%; border-radius: 8px; cursor: pointer;">
                        <i class="ri-delete-bin-line"></i> ล้างข้อมูลทั้งหมด (Clear All Data)
                    </button>
                </div>

                <div class="admin-section log-section" style="<?= empty($importLog) ? 'display: none;' : '' ?>">
                    <h3><i class="ri-terminal-box-line"></i> บันทึกการทำงาน (Logs)</h3>
                    <div class="log-container">
                        <?php if (!empty($importLog)): ?>
                            <?php foreach ($importLog as $log): ?>
                                <div class="log-entry"><?= htmlspecialchars($log) ?></div>
                            <?php endforeach; ?>
                        <?php endif; ?>
                    </div>
                </div>
                
            </div>
            
            <div class="admin-footer space-between">
                <a href="?page=home"><i class="ri-arrow-left-line"></i> กลับสู่หน้าหลัก</a>
                <a href="?page=admin&logout=1" class="btn-logout"><i class="ri-logout-box-r-line"></i> ออกจากระบบจัดการ</a>
            </div>
        </div>
    <?php endif; ?>

</div>

<style>
    :root {
        --admin-bg: #0f172a;
        --admin-card: #1e293b;
        --admin-accent: #3b82f6;
        --admin-text: #f1f5f9;
        --admin-muted: #94a3b8;
        --admin-border: #334155;
    }

    .admin-card {
        background: var(--admin-card);
        border: 1px solid var(--admin-border);
        border-radius: 20px;
        padding: 40px;
        width: 100%;
        max-width: 600px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    .admin-header { text-align: center; margin-bottom: 30px; }
    .admin-header i { font-size: 4rem; color: var(--admin-accent); display: block; margin-bottom: 15px; }
    .admin-header h2 { font-size: 1.8rem; font-weight: 700; margin-bottom: 10px; color: var(--admin-text); }
    .admin-header p { color: var(--admin-muted); font-size: 0.95rem; }

    .admin-badge {
        display: inline-block;
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.2);
        padding: 4px 12px;
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 15px;
    }

    .admin-alert {
        padding: 12px 16px;
        border-radius: 10px;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
    .admin-alert.error { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); }

    .admin-input-group { margin-bottom: 20px; }
    .admin-input-group label { display: block; font-size: 0.75rem; font-weight: 700; color: var(--admin-muted); margin-bottom: 8px; letter-spacing: 0.05em; }
    .admin-input-group input {
        width: 100%;
        background: var(--admin-bg);
        border: 1px solid var(--admin-border);
        padding: 14px 16px;
        border-radius: 12px;
        color: var(--admin-text);
        font-size: 1rem;
        transition: all 0.3s ease;
    }
    .admin-input-group input:focus { outline: none; border-color: var(--admin-accent); box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2); }

    .admin-btn-primary, .admin-btn-success {
        width: 100%;
        padding: 14px;
        border-radius: 12px;
        border: none;
        font-weight: 600;
        font-size: 1rem;
        cursor: pointer;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
    }
    .admin-btn-primary { background: var(--admin-accent); color: white; }
    .admin-btn-primary:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4); }
    
    .admin-btn-success { background: #10b981; color: white; margin-top: 20px; }
    .admin-btn-success:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.4); }
    .admin-btn-success:disabled { opacity: 0.5; cursor: not-allowed; }

    .admin-footer { margin-top: 30px; display: flex; justify-content: center; }
    .admin-footer.space-between { justify-content: space-between; }
    .admin-footer a { color: var(--admin-muted); text-decoration: none; font-size: 0.9rem; transition: color 0.3s; }
    .admin-footer a:hover { color: var(--admin-text); }
    .btn-logout { color: #ef4444 !important; }

    .admin-section {
        background: var(--admin-bg);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
    }
    .admin-section h3 { font-size: 1.1rem; margin-bottom: 5px; display: flex; align-items: center; gap: 8px; color: var(--admin-text); }
    .section-desc { color: var(--admin-muted); font-size: 0.85rem; margin-bottom: 20px; }

    .system-stats {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 15px;
        margin-top: 15px;
    }
    .stat-item {
        background: rgba(255, 255, 255, 0.03);
        padding: 12px;
        border-radius: 10px;
        border: 1px solid var(--admin-border);
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .stat-item span { font-size: 0.7rem; color: var(--admin-muted); font-weight: 600; text-transform: uppercase; }
    .stat-item strong { color: var(--admin-accent); font-size: 1.1rem; }

    .file-drop-zone {
        border: 2px dashed var(--admin-border);
        border-radius: 12px;
        padding: 30px;
        text-align: center;
        transition: all 0.3s;
        cursor: pointer;
        position: relative;
    }
    .file-drop-zone:hover, .file-drop-zone.dragover { border-color: var(--admin-accent); background: rgba(59, 130, 246, 0.05); }
    .file-drop-zone i { font-size: 2.5rem; color: var(--admin-muted); margin-bottom: 10px; display: block; }
    .file-drop-zone .file-info span { display: block; font-weight: 600; color: var(--admin-text); }
    .file-drop-zone .file-info small { color: var(--admin-muted); }
    .file-drop-zone input { position: absolute; top: 0; left: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; z-index: 10; }

    .selected-file-name {
        margin-top: 15px;
        padding: 10px 15px;
        background: rgba(59, 130, 246, 0.1);
        border-radius: 8px;
        color: var(--admin-accent);
        font-size: 0.9rem;
        font-weight: 600;
        text-align: center;
    }

    .log-container {
        max-height: 200px;
        overflow-y: auto;
        background: #000;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.8rem;
        padding: 15px;
        border-radius: 8px;
        color: #10b981;
    }
    .log-container::-webkit-scrollbar { width: 6px; }
    .log-container::-webkit-scrollbar-thumb { background: var(--admin-border); border-radius: 10px; }
    .log-entry { margin-bottom: 4px; border-bottom: 1px solid #111; padding-bottom: 4px; }
</style>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        const fileInput = document.getElementById('fileInput');
        const dropZone = document.getElementById('dropZone');
        const fileNameDisplay = document.getElementById('fileNameDisplay');
        const submitBtn = document.getElementById('submitBtn');
        const uploadForm = document.getElementById('mainUploadForm');
        const progressContainer = document.getElementById('importProgressContainer');
        const progressStatus = document.getElementById('progressStatus');
        const progressPercent = document.getElementById('progressPercent');
        const progressFill = document.getElementById('progressBarFill');
        const logContainer = document.querySelector('.log-container') || null;

        function addLog(msg) {
            console.log(msg);
            const logSection = document.querySelector('.log-section');
            if (logSection) logSection.style.display = 'block';
            
            const container = document.querySelector('.log-container');
            if (container) {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.textContent = msg;
                container.prepend(entry);
            }
        }

        // Global Error Handler to show JS errors in the log section
        window.onerror = function(msg, url, line) {
            addLog("❌ JS Error: " + msg + " (Line: " + line + ")");
            return false;
        };

        if (fileInput) {
            fileInput.addEventListener('change', function() {
                if (this.files.length > 0) {
                    const name = this.files[0].name;
                    fileNameDisplay.textContent = '📄 ' + name;
                    fileNameDisplay.style.display = 'block';
                    submitBtn.disabled = false;
                    addLog("📂 เลือกไฟล์แล้ว: " + name);
                } else {
                    fileNameDisplay.style.display = 'none';
                    submitBtn.disabled = true;
                }
            });
        }

        uploadForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const file = fileInput.files[0];
            if (!file) return;

            submitBtn.disabled = true;
            progressContainer.style.display = 'block';
            progressStatus.textContent = "กำลังอ่านไฟล์...";
            addLog("🚀 เริ่มต้นกระบวนการอ่านไฟล์...");

            const reader = new FileReader();
            reader.onload = async function(event) {
                try {
                    let content = event.target.result;
                    
                    // Clean JS wrapper (handle leading spaces/BOM)
                    content = content.replace(/^\s*const\s+animeData\s*=\s*/, '');
                    content = content.trim();
                    if (content.endsWith(';')) {
                        content = content.slice(0, -1);
                    }
                    content = content.trim();

                    const data = JSON.parse(content);
                    addLog("✅ อ่านไฟล์สำเร็จ! กำลังวางแผนการนำเข้า...");

                    // Flatten entries to process in batches
                    // data structure is { cat_id: { name: "", animes: [] } }
                    const categories = Object.keys(data);
                    const allBatches = [];
                    const BATCH_SIZE = 50; // animes per request

                    for (const catId of categories) {
                        const catData = data[catId];
                        const animes = catData.animes || [];
                        
                        // Split animes into chunks of 50
                        for (let i = 0; i < animes.length; i += BATCH_SIZE) {
                            const chunk = animes.slice(i, i + BATCH_SIZE);
                            const batchItem = {};
                            batchItem[catId] = {
                                name: catData.name,
                                animes: chunk
                            };
                            allBatches.push(batchItem);
                        }
                    }

                    const totalBatches = allBatches.length;
                    addLog(`📦 แบ่งข้อมูลเป็น ${totalBatches} ชุด เพื่อความปลอดภัยในการส่ง...`);

                    for (let i = 0; i < totalBatches; i++) {
                        const progress = Math.round(((i + 1) / totalBatches) * 100);
                        progressStatus.textContent = `กำลังอัปโหลดชุดที่ ${i + 1}/${totalBatches}...`;
                        progressPercent.textContent = `${progress}%`;
                        progressFill.style.width = `${progress}%`;

                        const response = await fetch('?page=admin&ajax_import=1', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(allBatches[i])
                        });

                        const result = await response.json();
                        if (!result.success) {
                            throw new Error(result.message);
                        }
                        
                        addLog(`  [${i+1}/${totalBatches}] นำเข้าสำเร็จ: ${result.total_anime} เรื่อง, ${result.total_episodes} ตอน`);
                    }

                    progressStatus.textContent = "🎉 นำเข้าข้อมูลทั้งหมดเสร็จสมบูรณ์!";
                    addLog("🏁 ภารกิจเสร็จสิ้น! ข้อมูลทั้งหมดถูกบันทึกแล้ว");
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);

                } catch (err) {
                    addLog("❌ เกิดข้อผิดพลาด: " + err.message);
                    progressStatus.textContent = "เกิดข้อผิดพลาด!";
                    progressFill.style.background = "#ef4444";
                    submitBtn.disabled = false;
                }
            };

            reader.readAsText(file);
        });

        // Drag/Drop visual
        if (dropZone) {
            ['dragenter', 'dragover'].forEach(name => {
                dropZone.addEventListener(name, () => dropZone.classList.add('dragover'));
            });
            ['dragleave', 'drop'].forEach(name => {
                dropZone.addEventListener(name, () => dropZone.classList.remove('dragover'));
            });

            // Explicit drop handler for better reliability
            dropZone.addEventListener('drop', (e) => {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length > 0) {
                    fileInput.files = files;
                    // Trigger change manually
                    fileInput.dispatchEvent(new Event('change'));
                }
            });

            // Explicit click handler to trigger file dialog
            dropZone.addEventListener('click', (e) => {
                if (e.target !== fileInput) fileInput.click();
            });
        }
        
        // Initial setup check
        if (fileInput && submitBtn) {
            addLog("⚙️ ระบบนำเข้าข้อมูลพร้อมทำงาน (Database Ready)");
        }
        async function clearAllData() {
            if (!confirm('คุณแน่ใจหรือไม่ว่าต้องการลบข้อมูลอนิเมะและตอนทั้งหมด? การกระทำนี้ไม่สามารถย้อนกลับได้')) return;
            
            try {
                const response = await fetch('?page=admin&ajax_clear=1', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    alert(result.message);
                    location.reload();
                } else {
                    alert('เกิดข้อผิดพลาด: ' + result.message);
                }
            } catch (error) {
                alert('เกิดข้อผิดพลาดในการเชื่อมต่อ');
            }
        }
    }); // <-- Fixed: Added missing closing for DOMContentLoaded
</script>

<?php include __DIR__ . '/../includes/footer.php'; ?>
