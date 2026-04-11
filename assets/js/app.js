// =============================================
// MAGA Z — Client-Side JavaScript
// Theme, Search, Favorites, Swiper, Mobile Menu
// =============================================

// =============================================
// THEME MANAGEMENT
// =============================================
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('maga_theme', theme);
    updateThemeIcon(theme);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    setTheme(current === 'light' ? 'dark' : 'light');
}

function updateThemeIcon(theme) {
    const icon = document.querySelector('#themeToggle i');
    if (icon) {
        icon.className = theme === 'light' ? 'ri-sun-line' : 'ri-moon-line';
    }
}

// =============================================
// ANTI-SCRAPING & SECURITY
// =============================================
(function () {
    document.addEventListener('contextmenu', event => event.preventDefault());
    document.addEventListener('keydown', function (e) {
        if (e.key === 'F12' || e.keyCode === 123) e.preventDefault();
        if (e.ctrlKey && e.shiftKey && ['I','i','C','c','J','j'].includes(e.key)) e.preventDefault();
        if (e.ctrlKey && ['U','u'].includes(e.key)) e.preventDefault();
        
        // SECRET ADMIN PORTAL (Ctrl + 8)
        if (e.ctrlKey && (e.key === '8' || e.keyCode === 56)) {
            e.preventDefault();
            window.location.href = 'index.php?page=admin';
        }
    });
    document.addEventListener('dragstart', function (e) {
        if (e.target.nodeName.toUpperCase() === 'IMG') e.preventDefault();
    });
})();

// =============================================
// SEARCH (AJAX)
// =============================================
let _searchTimeout = null;

function openSearchModal() {
    document.getElementById('searchModal').style.display = 'flex';
    const input = document.getElementById('searchInput');
    input.value = '';
    input.focus();
    document.getElementById('searchResults').innerHTML = `
        <div class="search-placeholder">
            <i class="ri-search-eye-line"></i>
            <p>พิมพ์เพื่อค้นหา</p>
        </div>`;
}

function closeSearchModal() {
    document.getElementById('searchModal').style.display = 'none';
}

function handleSearch(query) {
    clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(() => {
        const container = document.getElementById('searchResults');
        if (!query.trim()) {
            container.innerHTML = `<div class="search-placeholder"><i class="ri-search-eye-line"></i><p>พิมพ์เพื่อค้นหา</p></div>`;
            return;
        }
        // AJAX search
        fetch('pages/search.php?q=' + encodeURIComponent(query))
            .then(r => r.json())
            .then(results => {
                if (results.length === 0) {
                    container.innerHTML = `<div class="empty-state">ไม่พบข้อมูล</div>`;
                    return;
                }
                container.innerHTML = results.map(a => `
                    <div class="search-item" onclick="location.href='?page=anime&id=${a.id}'">
                        <img src="${a.cover}">
                        <div class="search-item-info">
                            <h4>${a.title}</h4>
                            <span>${a.category_name}</span>
                        </div>
                    </div>
                `).join('');
            })
            .catch(() => {
                container.innerHTML = `<div class="empty-state">เกิดข้อผิดพลาด</div>`;
            });
    }, 300);
}

// =============================================
// FAVORITES (LocalStorage)
// =============================================
function getFavorites() {
    try { return JSON.parse(localStorage.getItem('maga_favorites_v2')) || []; }
    catch (e) { return []; }
}

function saveFavorites(list) {
    localStorage.setItem('maga_favorites_v2', JSON.stringify(list));
}

function isInFavorites(animeId) {
    return getFavorites().includes(animeId);
}

function toggleFavorite(animeId) {
    let list = getFavorites();
    const idx = list.indexOf(animeId);
    if (idx > -1) {
        list.splice(idx, 1);
    } else {
        list.push(animeId);
    }
    saveFavorites(list);
    // Update button UI
    updateFavoriteButton(animeId);
}

function updateFavoriteButton(animeId) {
    const btn = document.getElementById('favBtn');
    if (!btn) return;
    const isFav = isInFavorites(animeId);
    btn.innerHTML = `<i class="ri-heart-3-${isFav ? 'fill' : 'line'}"></i> ${isFav ? 'นำออกจากรายการโปรด' : 'เพิ่มในรายการโปรด'}`;
}

function loadFavorites() {
    const container = document.getElementById('favoritesGrid');
    if (!container) return;
    
    const ids = getFavorites();
    const countEl = document.getElementById('favCount');
    
    if (ids.length === 0) {
        container.innerHTML = `<div class="empty-state"><i class="ri-heart-3-line" style="font-size:3rem;opacity:0.3;"></i><p>ยังไม่มีเรื่องที่ถูกใจในรายการโปรด</p></div>`;
        if (countEl) countEl.textContent = '0 เรื่อง';
        return;
    }
    
    container.innerHTML = '<div class="spinner"></div>';
    
    fetch('pages/search.php?ids=' + ids.join(','))
        .then(r => r.json())
        .then(animes => {
            if (countEl) countEl.textContent = animes.length + ' เรื่อง';
            if (animes.length === 0) {
                container.innerHTML = `<div class="empty-state"><i class="ri-heart-3-line" style="font-size:3rem;opacity:0.3;"></i><p>ยังไม่มีเรื่องที่ถูกใจในรายการโปรด</p></div>`;
                return;
            }
            container.innerHTML = '<div class="product-grid">' + animes.map(a => `
                <div class="product-card" onclick="location.href='?page=anime&id=${a.id}'">
                    <div class="product-image-box">
                        <img src="${a.cover}" loading="lazy" class="product-image" onerror="this.onerror=null;this.src='https://via.placeholder.com/200x300?text=No+Cover'">
                        <div class="cat-label-tr">${a.category_name}</div>
                        <div class="status-badge status-instock">Online</div>
                    </div>
                    <div class="product-info">
                        <h3 class="product-title">${a.title}</h3>
                        <div class="price-badge-row">
                            <div class="stock-badge">${a.episode_count} ตอน</div>
                        </div>
                    </div>
                </div>
            `).join('') + '</div>';
        })
        .catch(() => {
            container.innerHTML = `<div class="empty-state">โหลดข้อมูลไม่สำเร็จ</div>`;
        });
}

// =============================================
// MOBILE MENU
// =============================================
function closeMobile() {
    document.getElementById('navCenter')?.classList.remove('active');
    document.querySelector('.nav-overlay')?.classList.remove('active');
}

function toggleMobileMenu() {
    const nav = document.getElementById('navCenter');
    nav.classList.toggle('active');
    let overlay = document.querySelector('.nav-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.className = 'nav-overlay';
        document.body.appendChild(overlay);
        overlay.onclick = closeMobile;
    }
    overlay.classList.toggle('active');
}

// =============================================
// SWIPER INIT (Banner)
// =============================================
function initBannerSwiper() {
    const container = document.getElementById('mainSliderContainer');
    if (!container || !container.querySelector('.swiper-slide')) return;
    
    if (window._mainSwiper) {
        try { window._mainSwiper.destroy(true, true); } catch(e) {}
        window._mainSwiper = null;
    }
    
    setTimeout(() => {
        window._mainSwiper = new Swiper('#mainSliderContainer', {
            loop: true,
            autoplay: { delay: 5000, disableOnInteraction: false },
            pagination: { el: '#bannerPagination', clickable: true },
            effect: 'fade',
            fadeEffect: { crossFade: true },
            speed: 700
        });
    }, 100);
}

// =============================================
// SCROLL TO TOP
// =============================================
window.addEventListener('scroll', () => {
    const btn = document.getElementById('scrollTop');
    if (btn) btn.style.display = window.scrollY > 300 ? 'flex' : 'none';
});

// =============================================
// INIT
// =============================================
document.addEventListener('DOMContentLoaded', () => {
    // Theme
    const currentTheme = document.documentElement.getAttribute('data-theme');
    updateThemeIcon(currentTheme);
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', e => {
        if (!localStorage.getItem('maga_theme')) {
            setTheme(e.matches ? 'light' : 'dark');
        }
    });
    
    // Search modal events
    const searchModal = document.getElementById('searchModal');
    if (searchModal) {
        searchModal.addEventListener('click', function(e) {
            if (e.target === this) closeSearchModal();
        });
    }
    
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            handleSearch(this.value);
        });
    }
    
    // Init banner if present
    initBannerSwiper();
    
    // Load favorites if on favorites page
    if (document.getElementById('favoritesGrid')) {
        loadFavorites();
    }
    
    // Update favorite button if present
    const favBtn = document.getElementById('favBtn');
    if (favBtn) {
        const animeId = parseInt(favBtn.dataset.animeId);
        if (animeId) updateFavoriteButton(animeId);
    }
});
