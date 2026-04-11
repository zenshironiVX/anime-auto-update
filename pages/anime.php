<?php
/**
 * MAGA Z — Anime Detail Page
 * รายละเอียดเรื่อง + ลิสต์ตอน + อนิเมะแนะนำ
 */

$animeId = (int)($_GET['id'] ?? 0);
$anime   = getAnimeById($animeId);

if (!$anime) {
    header('Location: ?page=home');
    exit;
}

$episodes    = getEpisodes($animeId);
$recommended = getRandomAnimeExclude($animeId, 18);

$pageTitle = htmlspecialchars($anime['title']) . ' - MAGA Z';
$pageDesc  = 'ดู ' . $anime['title'] . ' ออนไลน์ ทั้ง ' . count($episodes) . ' ตอน ที่ MAGA Z';

include __DIR__ . '/../includes/header.php';
?>

<!-- Section Header -->
<div class="products-section padding-shop" style="padding-top: 20px; padding-bottom: 10px;">
    <div class="categories-header">
        <div>
            <h2>
                <a onclick="location.href='?page=home'" style="cursor:pointer;color:var(--text-muted)">หน้าแรก</a> / 
                <a onclick="location.href='?page=category&id=<?= $anime['category_source_id'] ?>'" style="cursor:pointer;color:var(--text-muted)"><?= htmlspecialchars($anime['category_name']) ?></a> / 
                <?= htmlspecialchars($anime['title']) ?>
            </h2>
            <p><?= count($episodes) ?> ตอน</p>
        </div>
    </div>
</div>

<!-- Detail Header -->
<div class="padding-shop" style="padding-bottom: 24px;">
    <div class="detail-header">
        <div class="detail-cover">
            <img src="<?= htmlspecialchars($anime['cover']) ?>" class="cover-image" alt="<?= htmlspecialchars($anime['title']) ?>">
        </div>
        <div class="detail-info">
            <h1><?= htmlspecialchars($anime['title']) ?></h1>
            <div class="detail-meta">
                <span class="meta-tag"><i class="ri-folder-line"></i> <?= htmlspecialchars($anime['category_name']) ?></span>
                <span class="meta-tag"><i class="ri-movie-2-line"></i> <?= count($episodes) ?> ตอน</span>
            </div>
            <div style="margin-top:20px;">
                <button class="btn-primary fav-btn" id="favBtn" data-anime-id="<?= $animeId ?>" onclick="toggleFavorite(<?= $animeId ?>)">
                    <i class="ri-heart-3-line"></i> เพิ่มในรายการโปรด
                </button>
            </div>
        </div>
    </div>

    <!-- Episode List -->
    <div class="manga-ep-container">
        <div class="categories-header"><div><h2>รายการตอน</h2><p>Episodes List</p></div></div>
        <div class="manga-ep-grid">
            <?php 
            $totalEps = count($episodes);
            $reversedEps = array_reverse($episodes);
            foreach ($reversedEps as $ep):
                $epDisplay = getEpDisplay($ep['title'], (int)$ep['sort_order'], $totalEps);
            ?>
                <a href="?page=player&id=<?= $ep['id'] ?>" class="manga-ep-item">
                    <div class="manga-ep-flex">
                        <div class="ep-num-label"><?= htmlspecialchars($epDisplay) ?></div>
                        <i class="ri-play-circle-line"></i>
                    </div>
                </a>
            <?php endforeach; ?>
        </div>
    </div>

    <!-- Recommended -->
    <div style="margin-top:24px;">
        <div class="categories-header"><div><h2>อนิเมะแนะนำ</h2><p>Recommended For You</p></div></div>
        <div class="product-grid">
            <?php foreach ($recommended as $rec): ?>
                <?= buildCard($rec) ?>
            <?php endforeach; ?>
        </div>
    </div>
</div>

<?php include __DIR__ . '/../includes/footer.php'; ?>
