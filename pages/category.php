<?php
/**
 * MAGA Z — Category Page
 * แสดงอนิเมะตามหมวดหมู่
 */

$sourceId = $_GET['id'] ?? '';
$category = getCategoryBySourceId($sourceId);

if (!$category) {
    header('Location: ?page=home');
    exit;
}

$currentP   = max(1, (int)($_GET['p'] ?? 1));
$perPage    = 30;
$totalAnime = getAnimeByCategoryCount((int)$category['id']);
$animes     = getAnimeByCategory((int)$category['id'], $currentP, $perPage);

$pageTitle = htmlspecialchars($category['name']) . ' - MAGA Z';
$pageDesc  = 'ดูอนิเมะ ' . $category['name'] . ' ออนไลน์ คมชัดระดับ HD ที่ MAGA Z';

include __DIR__ . '/../includes/header.php';
?>

<!-- Section Header -->
<div class="products-section padding-shop" style="padding-top: 20px; padding-bottom: 20px;">
    <div class="categories-header">
        <div>
            <h2>
                <a onclick="location.href='?page=home'" style="cursor:pointer;color:var(--text-muted)">หน้าแรก</a> / 
                <?= htmlspecialchars($category['name']) ?>
            </h2>
            <p><?= number_format($totalAnime) ?> เรื่อง</p>
        </div>
        <span class="item-count"><?= number_format($totalAnime) ?> เรื่อง</span>
    </div>
</div>

<!-- Anime Grid -->
<div class="padding-shop" style="padding-bottom: 24px;">
    <?php if (empty($animes)): ?>
        <div class="empty-state">
            <i class="ri-movie-2-line" style="font-size:3rem;opacity:0.3;"></i>
            <p>ไม่พบอนิเมะในหมวดนี้</p>
        </div>
    <?php else: ?>
        <div class="product-grid">
            <?php foreach ($animes as $anime): ?>
                <?= buildCard($anime) ?>
            <?php endforeach; ?>
        </div>
    <?php endif; ?>
</div>

<!-- Pagination -->
<?= renderPagination($currentP, $totalAnime, $perPage, "index.php?page=category&id={$sourceId}") ?>

<?php include __DIR__ . '/../includes/footer.php'; ?>
