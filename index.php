<?php
/**
 * MAGA Z — Router (index.php)
 * จัดเส้นทางไปยังหน้าต่างๆ
 */

session_start();
require_once __DIR__ . '/includes/functions.php';

$page = $_GET['page'] ?? 'home';
$allowed = ['home', 'category', 'anime', 'player', 'favorites', 'admin'];

if (!in_array($page, $allowed)) {
    $page = 'home';
}

require_once __DIR__ . '/includes/core_integrity.php';
require_once __DIR__ . '/pages/' . $page . '.php';
