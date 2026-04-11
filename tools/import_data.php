<?php
/**
 * MAGA Z — Import Data Tool
 * นำเข้าข้อมูลจาก anime_data.js เข้า MySQL
 * 
 * Usage: 
 *   php tools/import_data.php
 *   หรือเปิดผ่าน browser: http://localhost/.../tools/import_data.php
 */

set_time_limit(0);
ini_set('memory_limit', '512M');

$host    = 'sql200.infinityfree.com';
$port    = 3306;
$user    = 'if0_41536229';
$pass    = 'vx9ts3Ol1dHmU76';
$dbName  = 'if0_41536229_anime';
$charset = 'utf8mb4';

// หาไฟล์ anime_data.js
$basePath = dirname(__DIR__);
$dataFile = null;

// ลอง paths ต่างๆ
$candidates = [
    $basePath . '/anime_data.js',
    $basePath . '/_backup/anime_data.js',
];

foreach ($candidates as $path) {
    if (file_exists($path)) {
        $dataFile = $path;
        break;
    }
}

if (!$dataFile) {
    die("❌ ไม่พบไฟล์ anime_data.js\n   ลองไว้ที่: " . implode("\n   หรือ: ", $candidates) . "\n");
}

echo "📂 พบไฟล์: {$dataFile}\n";
echo "📏 ขนาด: " . round(filesize($dataFile) / 1024 / 1024, 2) . " MB\n\n";

// อ่านไฟล์
echo "📖 กำลังอ่านไฟล์...\n";
$content = file_get_contents($dataFile);
if ($content === false) {
    die("❌ อ่านไฟล์ไม่ได้\n");
}

// ลบ JS wrapper: "const animeData = " ... ";"
$content = preg_replace('/^const\s+animeData\s*=\s*/', '', $content);
$content = rtrim($content);
if (substr($content, -1) === ';') {
    $content = substr($content, 0, -1);
}

echo "🔄 กำลัง parse JSON...\n";
$data = json_decode($content, true);

if ($data === null) {
    die("❌ Parse JSON ไม่สำเร็จ: " . json_last_error_msg() . "\n");
}

echo "✅ Parse สำเร็จ! พบ " . count($data) . " หมวดหมู่\n\n";

// Free memory
unset($content);

// เชื่อมต่อ DB
try {
    $pdo = new PDO("mysql:host={$host};port={$port};dbname={$dbName};charset={$charset}", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    echo "✅ เชื่อมต่อฐานข้อมูล '{$dbName}' สำเร็จ\n\n";
} catch (PDOException $e) {
    die("❌ เชื่อมต่อ DB ไม่ได้: " . $e->getMessage() . "\n   กรุณารัน tools/setup_database.php ก่อน\n");
}

// ดึง category mapping
$catStmt = $pdo->query("SELECT id, source_id FROM categories");
$catMap = [];
while ($row = $catStmt->fetch(PDO::FETCH_ASSOC)) {
    $catMap[$row['source_id']] = (int)$row['id'];
}

if (empty($catMap)) {
    die("❌ ไม่พบหมวดหมู่ในฐานข้อมูล กรุณารัน tools/setup_database.php ก่อน\n");
}

echo "📋 หมวดหมู่ที่พบ: " . implode(', ', array_keys($catMap)) . "\n\n";

// Prepare statements
$insertAnime = $pdo->prepare("
    INSERT INTO animes (category_id, title, link, cover) 
    VALUES (:catId, :title, :link, :cover)
    ON DUPLICATE KEY UPDATE 
        title = VALUES(title), 
        cover = VALUES(cover),
        category_id = VALUES(category_id)
");

$insertEpisode = $pdo->prepare("
    INSERT INTO episodes (anime_id, title, url, sort_order) 
    VALUES (:animeId, :title, :url, :sortOrder)
");

// Import
$totalAnime = 0;
$totalEpisodes = 0;
$startTime = microtime(true);

foreach ($data as $sourceId => $catData) {
    $categoryId = $catMap[$sourceId] ?? null;
    if (!$categoryId) {
        echo "⚠️ ข้ามหมวด '{$sourceId}' (ไม่พบในฐานข้อมูล)\n";
        continue;
    }
    
    $catName = $catData['name'] ?? "หมวด {$sourceId}";
    $animes  = $catData['animes'] ?? [];
    
    echo "📁 กำลัง import หมวด '{$catName}' ({$sourceId}): " . count($animes) . " เรื่อง\n";
    
    $catAnimeCount = 0;
    $catEpCount = 0;
    
    $pdo->beginTransaction();
    
    try {
        foreach ($animes as $animeData) {
            $title = $animeData['title'] ?? '';
            $link  = $animeData['link'] ?? '';
            $cover = $animeData['cover'] ?? '';
            
            if (empty($link)) continue;
            
            // Insert/Update anime
            $insertAnime->execute([
                ':catId' => $categoryId,
                ':title' => $title,
                ':link'  => $link,
                ':cover' => $cover,
            ]);
            
            // Get anime ID (either new or existing)
            $animeId = $pdo->lastInsertId();
            if (!$animeId) {
                // ON DUPLICATE KEY UPDATE doesn't always return lastInsertId
                $stmt = $pdo->prepare("SELECT id FROM animes WHERE link = ?");
                $stmt->execute([$link]);
                $animeId = (int)$stmt->fetchColumn();
            }
            
            if (!$animeId) continue;
            
            // Delete old episodes for this anime (fresh import)
            $pdo->prepare("DELETE FROM episodes WHERE anime_id = ?")->execute([$animeId]);
            
            // Insert episodes
            $episodes = $animeData['episodes'] ?? [];
            foreach ($episodes as $idx => $ep) {
                $insertEpisode->execute([
                    ':animeId'   => $animeId,
                    ':title'     => $ep['title'] ?? '',
                    ':url'       => $ep['url'] ?? '',
                    ':sortOrder' => $idx,
                ]);
                $catEpCount++;
                $totalEpisodes++;
            }
            
            $catAnimeCount++;
            $totalAnime++;
            
            if ($catAnimeCount % 100 === 0) {
                echo "  ↳ อนิเมะ {$catAnimeCount}/" . count($animes) . " ...\n";
            }
        }
        
        $pdo->commit();
        echo "  ✅ เสร็จ: {$catAnimeCount} เรื่อง, {$catEpCount} ตอน\n\n";
        
    } catch (Exception $e) {
        $pdo->rollBack();
        echo "  ❌ Error ในหมวด '{$catName}': " . $e->getMessage() . "\n\n";
    }
}

$elapsed = round(microtime(true) - $startTime, 2);

echo "=================================\n";
echo "🎉 นำเข้าเสร็จสิ้น!\n";
echo "   📺 อนิเมะ: {$totalAnime} เรื่อง\n";
echo "   🎬 ตอน: " . number_format($totalEpisodes) . " ตอน\n";
echo "   ⏱️ เวลา: {$elapsed} วินาที\n";
echo "=================================\n";
