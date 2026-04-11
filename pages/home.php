<?php
/**
 * MAGA Z — Home Page
 * หน้าแรก: Banner + Stats + รายการอนิเมะทั้งหมด
 */

$pageTitle = 'MAGA Z - ดูอนิเมะออนไลน์';
$pageDesc  = 'ดูอนิเมะออนไลน์ ซับไทย พากย์ไทย เดอะมูฟวี่ คมชัดระดับ HD ที่ MAGA Z';

// Data
$stats       = getStats();
$currentP    = max(1, (int)($_GET['p'] ?? 1));
$perPage     = 30;
$totalAnime  = getAllAnimeCount();
$animes      = getAllAnime($currentP, $perPage);

// Banner — always randomize on every page load as requested
$bannerAnime = getRandomAnime(5);

include __DIR__ . '/../includes/header.php';
?>

<!-- Banner Slider -->
<div class="slider-wrapper wrapernum3" id="bannerSection">
    <div class="big-slider swiper-container slidernom3" id="mainSliderContainer">
        <div class="swiper-wrapper" id="bannerWrapper">
            <?php foreach ($bannerAnime as $item):
                $totalEps = (int)($item['episode_count'] ?? 0);
                $epNum = getLatestEpInfo((int)$item['id']);
                $catName = htmlspecialchars($item['category_name'], ENT_QUOTES, 'UTF-8');
                $desc = "เรื่องราวสุดเข้มข้นที่น่าติดตาม มาร่วมลุ้นและเอาใจช่วยตัวละครใน " . htmlspecialchars($item['title']) . " ไปพร้อมๆ กัน รับชมแบบคมชัดได้ที่นี่";
            ?>
            <div class="swiper-slide">
                <div class="mainslider">
                    <div class="bigbanner img-blur" style="background-image: url('<?= htmlspecialchars($item['cover']) ?>');"></div>
                    <div class="limit">
                        <div class="sliderinfo">
                            <div class="sliderinfolimit">
                                <div class="slidlc"><i class="ri-play-fill"></i> <?= $epNum ?> · <?= $catName ?></div>
                                <a href="?page=anime&id=<?= $item['id'] ?>">
                                    <span class="name"><?= htmlspecialchars($item['title']) ?></span>
                                    <div class="desc"><p><?= $desc ?></p></div>
                                </a>
                                <div class="banner-ep-info"><i class="ri-film-line"></i> <?= $totalEps ?> ตอน</div>
                                <div class="start-reading">
                                    <a href="?page=anime&id=<?= $item['id'] ?>">
                                        <i class="ri-play-fill"></i> <span>รับชมเลย</span>
                                    </a>
                                </div>
                            </div>
                        </div>
                        <div class="slidtrithumb">
                            <img src="<?= htmlspecialchars($item['cover']) ?>" alt="cover">
                        </div>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
        <div class="paging">
            <div class="centerpaging">
                <div class="swiper-pagination" id="bannerPagination"></div>
            </div>
        </div>
    </div>
</div>

<!-- Stats Grid -->
<div class="stats-grid padding-shop" id="statsGrid">
    <div class="stat-card">
        <div class="stat-content">
            <span class="stat-label">เรื่องทั้งหมด</span>
            <div class="stat-value"><?= number_format($stats['animes']) ?> <span class="stat-unit">เรื่อง</span></div>
        </div>
        <div class="stat-icon-large"><i class="ri-movie-2-line"></i></div>
    </div>
    <div class="stat-card">
        <div class="stat-content">
            <span class="stat-label">ตอนทั้งหมด</span>
            <div class="stat-value"><?= number_format($stats['episodes']) ?> <span class="stat-unit">ตอน</span></div>
        </div>
        <div class="stat-icon-large"><i class="ri-play-list-2-line"></i></div>
    </div>
    <div class="stat-card">
        <div class="stat-content">
            <span class="stat-label">หมวดหมู่</span>
            <div class="stat-value"><?= $stats['categories'] ?> <span class="stat-unit">หมวด</span></div>
        </div>
        <div class="stat-icon-large"><i class="ri-folder-line"></i></div>
    </div>
</div>

<!-- Section Header -->
<div class="products-section padding-shop" style="padding-bottom: 20px;" id="mainSection">
    <div class="categories-header">
        <div>
            <h2>รายการอนิเมะ</h2>
            <p>อ้างอิงลำดับตามแอปต้นทาง (Page 1 Sync)</p>
        </div>
        <span class="item-count"><?= number_format($totalAnime) ?> เรื่อง</span>
    </div>
</div>

<!-- Anime Grid -->
<div class="padding-shop" style="padding-bottom: 24px;">
    <div class="product-grid">
        <?php foreach ($animes as $anime): ?>
            <?= buildCard($anime) ?>
        <?php endforeach; ?>
    </div>
</div>

<!-- Pagination -->
<?= renderPagination($currentP, $totalAnime, $perPage, 'index.php?page=home') ?>

<?php include __DIR__ . '/../includes/footer.php'; ?>
