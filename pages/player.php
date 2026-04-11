<?php
/**
 * MAGA Z — Video Player Page
 * หน้าดูอนิเมะ (iframe player + navigation)
 */

$episodeId = (int)($_GET['id'] ?? 0);
$episode   = getEpisodeById($episodeId);

if (!$episode) {
    header('Location: ?page=home');
    exit;
}

$animeId = (int)$episode['anime_id'];
$anime   = getAnimeById($animeId);

if (!$anime) {
    header('Location: ?page=home');
    exit;
}

// Get prev/next episodes
$adjacent = getAdjacentEpisodes($animeId, (int)$episode['sort_order']);
$prevId = $adjacent['prev'] ? $adjacent['prev']['id'] : null;
$nextId = $adjacent['next'] ? $adjacent['next']['id'] : null;

$pageTitle = htmlspecialchars($anime['title'] . ' - ' . $episode['title']) . ' - MAGA Z';
$pageDesc  = 'ดู ' . $anime['title'] . ' ' . $episode['title'] . ' ออนไลน์ ที่ MAGA Z';

include __DIR__ . '/../includes/header.php';
?>

<div class="padding-shop" style="padding-bottom: 24px;">
    <div class="reader-toolbar">
        <button class="btn-ghost" onclick="location.href='?page=anime&id=<?= $animeId ?>'">
            <i class="ri-arrow-left-line"></i> กลับ
        </button>
        <div class="reader-title"><?= htmlspecialchars($anime['title']) ?> - <?= htmlspecialchars($episode['title']) ?></div>
    </div>
    <div style="padding-top: 60px; max-width: 1000px; margin: 0 auto; width: 100%;">
        <div style="position:relative; padding-bottom:56.25%; height:0; background:#000; border-radius:12px; overflow:hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.5);">
            <iframe src="<?= htmlspecialchars($episode['url']) ?>" style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;" allowfullscreen></iframe>
        </div>
        <div class="reader-nav" style="margin-top:24px;">
            <button class="btn-ghost" <?= $prevId === null ? 'disabled' : "onclick=\"location.href='?page=player&id={$prevId}'\"" ?>>
                <i class="ri-arrow-left-line"></i> ตอนก่อนหน้า
            </button>
            <button class="btn-primary" <?= $nextId === null ? 'disabled' : "onclick=\"location.href='?page=player&id={$nextId}'\"" ?>>
                ตอนถัดไป <i class="ri-arrow-right-line"></i>
            </button>
        </div>
    </div>
</div>

<?php include __DIR__ . '/../includes/footer.php'; ?>
