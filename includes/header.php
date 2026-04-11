<?php
/**
 * MAGA Z — Shared Header
 * Navbar, Search Modal, CSS/Font includes
 */
$categories = getCategories();
$currentPage_nav = $_GET['page'] ?? 'home';
$baseUrl = getBaseUrl();
?>
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <meta name="theme-color" content="#050508">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="referrer" content="no-referrer">
    <title><?= $pageTitle ?? 'MAGA Z - ดูอนิเมะออนไลน์' ?></title>
    <meta name="description" content="<?= $pageDesc ?? 'ดูอนิเมะออนไลน์ ซับไทย พากย์ไทย เดอะมูฟวี่ คมชัดระดับ HD ที่ MAGA Z' ?>">
    <link rel="icon" type="image/png" href="https://img1.pic.in.th/images/___202603251446-removebg-preview.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css" />
    <link rel="stylesheet" href="assets/css/style.css?v=1.2">
    <script>
        (function () {
            const savedTheme = localStorage.getItem('maga_theme');
            const theme = savedTheme || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
            document.documentElement.setAttribute('data-theme', theme);
        })();
    </script>
</head>
<body<?= ($currentPage_nav === 'player') ? ' class="reader-active"' : '' ?>>
    <div class="wrapper">
        <nav class="nav">
            <div class="nav-container">
                <div class="nav-left" style="display:flex;align-items:center;gap:12px;">
                    <div class="nameshop" onclick="location.href='?page=home'" style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                        <img src="https://img1.pic.in.th/images/___202603251446-removebg-preview.png" alt="MAGA Z Logo" style="height: 36px; width: auto; object-fit: contain;">
                        <h2>MAGA <span>Z</span></h2>
                    </div>
                </div>
                <div class="nav-center" id="navCenter">
                    <div class="nav-center-header">
                        <h3>หมวดหมู่อนิเมะ</h3>
                        <p>เลือกแนวที่ใช่สำหรับคุณ</p>
                    </div>
                    <a href="?page=home" class="nav-link <?= $currentPage_nav === 'home' ? 'active' : '' ?>" id="nav-all" onclick="closeMobile();">
                        ทั้งหมด
                    </a>
                    <div id="navCategoryLinks" style="display:flex;gap:4px;">
                        <?php
                        $targetCats = ["ซับไทย", "พากย์ไทย", "เดอะมูฟวี่"];
                        $sortedCats = [];
                        // เรียงตามลำดับ target ก่อน
                        foreach ($targetCats as $name) {
                            foreach ($categories as $cat) {
                                if ($cat['name'] === $name) {
                                    $sortedCats[] = $cat;
                                    break;
                                }
                            }
                        }
                        // เพิ่มหมวดที่เหลือ
                        foreach ($categories as $cat) {
                            if (!in_array($cat['name'], $targetCats)) {
                                $sortedCats[] = $cat;
                            }
                        }
                        $activeCatId = $_GET['id'] ?? '';
                        foreach ($sortedCats as $cat):
                            $isActive = ($currentPage_nav === 'category' && $activeCatId == $cat['source_id']) ? 'active' : '';
                        ?>
                            <a href="?page=category&id=<?= $cat['source_id'] ?>" class="nav-link <?= $isActive ?>" data-cat="<?= $cat['source_id'] ?>" onclick="closeMobile();">
                                <?= htmlspecialchars($cat['name']) ?>
                            </a>
                        <?php endforeach; ?>
                        <a href="?page=favorites" class="nav-link <?= $currentPage_nav === 'favorites' ? 'active' : '' ?>" id="nav-bookshelf" onclick="closeMobile();">
                            รายการโปรด
                        </a>
                    </div>
                </div>
                <div class="nav-right">
                    <button id="themeToggle" class="theme-toggle-btn" onclick="toggleTheme()" title="สลับโหมดสว่าง/มืด">
                        <i class="ri-moon-line"></i>
                    </button>
                    <div class="search-box" onclick="openSearchModal()" style="cursor:pointer;">
                        <input type="text" placeholder="ค้นหาอนิเมะ..." readonly style="pointer-events:none;cursor:pointer;">
                        <span class="search-icon"><i class="ri-search-line"></i></span>
                    </div>
                </div>
            </div>
        </nav>

        <!-- Search Modal -->
        <div id="searchModal" class="search-modal-overlay" style="display:none;">
            <div class="search-modal-content">
                <div class="search-header">
                    <i class="ri-search-line search-icon-large"></i>
                    <input type="text" id="searchInput" placeholder="พิมพ์ชื่อเรื่องที่ต้องการค้นหา..." autocomplete="off">
                    <button class="close-search" onclick="closeSearchModal()"><i class="ri-close-line"></i></button>
                </div>
                <div class="search-body">
                    <div id="searchResults" class="search-results">
                        <div class="search-placeholder" id="searchPlaceholder">
                            <i class="ri-search-eye-line"></i>
                            <p>พิมพ์เพื่อค้นหา</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="content" id="mainContent">
