<?php
/**
 * MAGA Z — Helper Functions
 * ฟังก์ชันสำหรับดึงข้อมูลจากฐานข้อมูล
 */

require_once __DIR__ . '/../config/database.php';

// ============================================
// CATEGORY FUNCTIONS
// ============================================

function getCategories(): array {
    $pdo = getDB();
    return $pdo->query("SELECT * FROM categories ORDER BY source_id ASC")->fetchAll();
}

function getCategoryBySourceId(string $sourceId): ?array {
    $pdo = getDB();
    $stmt = $pdo->prepare("SELECT * FROM categories WHERE source_id = ?");
    $stmt->execute([$sourceId]);
    return $stmt->fetch() ?: null;
}

function getCategoryById(int $id): ?array {
    $pdo = getDB();
    $stmt = $pdo->prepare("SELECT * FROM categories WHERE id = ?");
    $stmt->execute([$id]);
    return $stmt->fetch() ?: null;
}

// ============================================
// ANIME FUNCTIONS
// ============================================

function getAllAnimeCount(): int {
    $pdo = getDB();
    return (int) $pdo->query("SELECT COUNT(*) FROM animes")->fetchColumn();
}

function getAllAnime(int $page = 1, int $limit = 30): array {
    $pdo = getDB();
    $offset = ($page - 1) * $limit;
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        ORDER BY a.sort_order DESC
        LIMIT :limit OFFSET :offset
    ");
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function getAnimeByCategory(int $categoryId, int $page = 1, int $limit = 30): array {
    $pdo = getDB();
    $offset = ($page - 1) * $limit;
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        WHERE a.category_id = :catId
        ORDER BY a.sort_order DESC
        LIMIT :limit OFFSET :offset
    ");
    $stmt->bindValue(':catId', $categoryId, PDO::PARAM_INT);
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function getAnimeByCategoryCount(int $categoryId): int {
    $pdo = getDB();
    $stmt = $pdo->prepare("SELECT COUNT(*) FROM animes WHERE category_id = ?");
    $stmt->execute([$categoryId]);
    return (int) $stmt->fetchColumn();
}

function getAnimeById(int $id): ?array {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        WHERE a.id = ?
    ");
    $stmt->execute([$id]);
    return $stmt->fetch() ?: null;
}

function getAnimesByIds(array $ids): array {
    if (empty($ids)) return [];
    $pdo = getDB();
    $placeholders = implode(',', array_fill(0, count($ids), '?'));
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        WHERE a.id IN ({$placeholders})
        ORDER BY a.sort_order DESC
    ");
    $stmt->execute($ids);
    return $stmt->fetchAll();
}

function getRandomAnime(int $count = 5): array {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        ORDER BY RAND()
        LIMIT :cnt
    ");
    $stmt->bindValue(':cnt', $count, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function getRandomAnimeExclude(int $excludeId, int $count = 18): array {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        WHERE a.id != :excludeId
        ORDER BY RAND()
        LIMIT :cnt
    ");
    $stmt->bindValue(':excludeId', $excludeId, PDO::PARAM_INT);
    $stmt->bindValue(':cnt', $count, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

function searchAnime(string $query, int $limit = 15): array {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT a.*, c.name AS category_name, c.source_id AS category_source_id,
               (SELECT COUNT(*) FROM episodes WHERE anime_id = a.id) AS episode_count
        FROM animes a
        JOIN categories c ON a.category_id = c.id
        WHERE a.title LIKE :q
        ORDER BY a.sort_order DESC
        LIMIT :limit
    ");
    $stmt->bindValue(':q', '%' . $query . '%', PDO::PARAM_STR);
    $stmt->bindValue(':limit', $limit, PDO::PARAM_INT);
    $stmt->execute();
    return $stmt->fetchAll();
}

// ============================================
// EPISODE FUNCTIONS
// ============================================

function getEpisodes(int $animeId): array {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT * FROM episodes 
        WHERE anime_id = ? 
        ORDER BY sort_order DESC
    ");
    $stmt->execute([$animeId]);
    return $stmt->fetchAll();
}

function getEpisodeById(int $id): ?array {
    $pdo = getDB();
    $stmt = $pdo->prepare("SELECT * FROM episodes WHERE id = ?");
    $stmt->execute([$id]);
    return $stmt->fetch() ?: null;
}

function getAdjacentEpisodes(int $animeId, int $currentSortOrder): array {
    $pdo = getDB();
    
    // Previous
    $stmt = $pdo->prepare("
        SELECT id, sort_order FROM episodes 
        WHERE anime_id = ? AND sort_order < ? 
        ORDER BY sort_order DESC LIMIT 1
    ");
    $stmt->execute([$animeId, $currentSortOrder]);
    $prev = $stmt->fetch();
    
    // Next
    $stmt = $pdo->prepare("
        SELECT id, sort_order FROM episodes 
        WHERE anime_id = ? AND sort_order > ? 
        ORDER BY sort_order ASC LIMIT 1
    ");
    $stmt->execute([$animeId, $currentSortOrder]);
    $next = $stmt->fetch();
    
    return ['prev' => $prev, 'next' => $next];
}

// ============================================
// STATS
// ============================================

function getStats(): array {
    $pdo = getDB();
    $totalAnime = (int) $pdo->query("SELECT COUNT(*) FROM animes")->fetchColumn();
    $totalEpisodes = (int) $pdo->query("SELECT COUNT(*) FROM episodes")->fetchColumn();
    $totalCategories = (int) $pdo->query("SELECT COUNT(*) FROM categories")->fetchColumn();
    return [
        'animes'     => $totalAnime,
        'episodes'   => $totalEpisodes,
        'categories' => $totalCategories,
    ];
}

// ============================================
// EPISODE DISPLAY NAME
// ============================================

function getEpDisplay(string $title, int $idx, int $totalEps): string {
    // เดอะมูฟวี่ — 1 ตอนเดียว และไม่มีคำว่า ตอนที่ หรือ EP
    if ($totalEps === 1 && strpos($title, 'ตอนที่') === false && !preg_match('/EP\.?\s*\d+/i', $title)) {
        return "ตอนที่ 1 (เดอะมูฟวี่) - {$title}";
    }
    // ตอนที่ X
    if (preg_match('/ตอนที่\s*(\d+(\.\d+)?)/i', $title, $m)) {
        return "ตอนที่ {$m[1]}";
    }
    // EP X / EP.X
    if (preg_match('/\bEP\.?\s*(\d+(\.\d+)?)\b/i', $title, $m)) {
        return "ตอนที่ {$m[1]}";
    }
    // Number at end
    if (preg_match('/(\d+(\.\d+)?)\s*$/', $title, $m)) {
        return "ตอนที่ {$m[1]}";
    }
    // Fallback
    return "ตอนที่ " . ($idx + 1);
}

// ============================================
// LATEST EPISODE INFO (for banner)
// ============================================

function getLatestEpInfo(int $animeId): string {
    $pdo = getDB();
    $stmt = $pdo->prepare("
        SELECT title FROM episodes 
        WHERE anime_id = ? 
        ORDER BY sort_order DESC LIMIT 1
    ");
    $stmt->execute([$animeId]);
    $row = $stmt->fetch();
    if (!$row) return 'N/A';
    
    $title = $row['title'];
    if (preg_match('/ตอนที่\s*(\d+(\.\d+)?)/i', $title, $m)) return 'EP.' . $m[1];
    if (preg_match('/\bEP\.?\s*(\d+(\.\d+)?)\b/i', $title, $m)) return 'EP.' . $m[1];
    if (preg_match('/(\d+(\.\d+)?)\s*$/', $title, $m)) return 'EP.' . $m[1];
    return $title;
}

// ============================================
// PAGINATION RENDERER
// ============================================

function renderPagination(int $currentPage, int $totalItems, int $perPage, string $baseUrl): string {
    $totalPages = (int) ceil($totalItems / $perPage);
    if ($totalPages <= 1) return '';
    
    // Parse existing query params
    $parts = parse_url($baseUrl);
    $query = [];
    if (isset($parts['query'])) parse_str($parts['query'], $query);
    $pathOnly = $parts['path'] ?? 'index.php';
    
    $html = '<div class="pagination padding-shop" style="padding-bottom: 60px;">';
    
    if ($currentPage > 1) {
        $query['p'] = $currentPage - 1;
        $url = $pathOnly . '?' . http_build_query($query);
        $html .= "<a href=\"{$url}\"><button>‹</button></a>";
    }
    
    for ($i = 1; $i <= $totalPages; $i++) {
        if (abs($i - $currentPage) < 3) {
            $query['p'] = $i;
            $url = $pathOnly . '?' . http_build_query($query);
            $active = $i === $currentPage ? ' class="active"' : '';
            $html .= "<a href=\"{$url}\"><button{$active}>{$i}</button></a>";
        }
    }
    
    if ($currentPage < $totalPages) {
        $query['p'] = $currentPage + 1;
        $url = $pathOnly . '?' . http_build_query($query);
        $html .= "<a href=\"{$url}\"><button>›</button></a>";
    }
    
    $html .= '</div>';
    return $html;
}

// ============================================
// ANIME CARD BUILDER
// ============================================

function buildCard(array $anime): string {
    $id    = (int)$anime['id'];
    $title = htmlspecialchars($anime['title'], ENT_QUOTES, 'UTF-8');
    $cover = htmlspecialchars($anime['cover'], ENT_QUOTES, 'UTF-8');
    $catName = htmlspecialchars($anime['category_name'], ENT_QUOTES, 'UTF-8');
    $epCount = $anime['episode_count'] ?? 0;
    
    return <<<HTML
    <div class="product-card" onclick="location.href='?page=anime&id={$id}'">
        <div class="product-image-box">
            <img src="{$cover}" loading="lazy" class="product-image" onerror="this.onerror=null;this.src='https://via.placeholder.com/200x300?text=No+Cover'">
            <div class="cat-label-tr">{$catName}</div>
            <div class="status-badge status-instock">Online</div>
        </div>
        <div class="product-info">
            <h3 class="product-title">{$title}</h3>
            <div class="price-badge-row">
                <div class="stock-badge">{$epCount} ตอน</div>
            </div>
        </div>
    </div>
HTML;
}

// ============================================
// SAFE BASE URL DETECTION
// ============================================

function getBaseUrl(): string {
    $script = $_SERVER['SCRIPT_NAME'] ?? '/index.php';
    return dirname($script) . '/';
}
