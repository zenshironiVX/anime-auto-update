<?php
/**
 * MAGA Z — Favorites Page
 * รายการโปรด (ข้อมูลดึงผ่าน AJAX จาก LocalStorage IDs)
 */

$pageTitle = 'รายการโปรด - MAGA Z';
$pageDesc  = 'รายการอนิเมะที่คุณชื่นชอบ';

include __DIR__ . '/../includes/header.php';
?>

<!-- Section Header -->
<div class="products-section padding-shop" style="padding-top: 20px; padding-bottom: 20px;">
    <div class="categories-header">
        <div>
            <h2>
                <a onclick="location.href='?page=home'" style="cursor:pointer;color:var(--text-muted)">หน้าแรก</a> / 
                รายการโปรด
            </h2>
            <p>เรื่องที่บันทึกไว้</p>
        </div>
        <span class="item-count" id="favCount">กำลังโหลด...</span>
    </div>
</div>

<!-- Favorites Grid (loaded via AJAX from app.js) -->
<div class="padding-shop" style="padding-bottom: 60px;">
    <div id="favoritesGrid">
        <div class="spinner"></div>
    </div>
</div>

<?php include __DIR__ . '/../includes/footer.php'; ?>
