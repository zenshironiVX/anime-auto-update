<?php
/**
 * MAGA Z — Search API (AJAX)
 * รับ ?q=keyword → ค้นหาอนิเมะ → return JSON
 * รับ ?ids=1,2,3 → ดึงอนิเมะตาม ID → return JSON
 */

header('Content-Type: application/json; charset=utf-8');

require_once __DIR__ . '/../includes/functions.php';

// Mode: Search by IDs (for favorites)
if (isset($_GET['ids']) && !empty($_GET['ids'])) {
    $rawIds = $_GET['ids'];
    $ids = array_filter(array_map('intval', explode(',', $rawIds)));
    
    if (empty($ids)) {
        echo json_encode([]);
        exit;
    }
    
    $results = getAnimesByIds($ids);
    echo json_encode($results, JSON_UNESCAPED_UNICODE);
    exit;
}

// Mode: Search by keyword
$query = trim($_GET['q'] ?? '');

if ($query === '') {
    echo json_encode([]);
    exit;
}

$results = searchAnime($query, 15);
echo json_encode($results, JSON_UNESCAPED_UNICODE);
