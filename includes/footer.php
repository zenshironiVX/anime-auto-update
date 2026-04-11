        </div><!-- /.content -->
    </div><!-- /.wrapper -->

    <nav class="bottom-nav" id="bottomNav">
        <a href="?page=home" class="bottom-nav-link <?= ($currentPage_nav ?? '') === 'home' ? 'active' : '' ?>" id="bn-home">
            <i class="ri-home-4-line"></i>
            <span>หน้าแรก</span>
        </a>
        <a href="#" class="bottom-nav-link" onclick="openSearchModal(); return false;" id="bn-search">
            <i class="ri-search-line"></i>
            <span>ค้นหา</span>
        </a>
        <a href="#" class="bottom-nav-link" onclick="toggleMobileMenu(); return false;" id="bn-category">
            <i class="ri-grid-fill"></i>
            <span>หมวดหมู่</span>
        </a>
        <a href="?page=favorites" class="bottom-nav-link <?= ($currentPage_nav ?? '') === 'favorites' ? 'active' : '' ?>" id="bn-bookshelf">
            <i class="ri-heart-3-fill"></i>
            <span>รายการโปรด</span>
        </a>
    </nav>

    <button id="scrollTop" onclick="window.scrollTo({top:0,behavior:'smooth'})">
        <i class="ri-arrow-up-line"></i>
    </button>

    <script src="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js"></script>
    <script src="assets/js/app.js"></script>
</body>
</html>
