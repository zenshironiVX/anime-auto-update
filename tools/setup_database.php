<?php
/**
 * MAGA Z — Database Setup
 * รันครั้งเดียวเพื่อสร้างฐานข้อมูลและตาราง
 * Usage: php tools/setup_database.php  หรือเปิดผ่าน browser
 */

$host    = 'sql200.infinityfree.com';
$port    = 3306;
$user    = 'if0_41536229';
$pass    = 'vx9ts3Ol1dHmU76';
$dbName  = 'if0_41536229_anime';
$charset = 'utf8mb4';

try {
    // เชื่อมต่อ MySQL (ยังไม่เลือก DB)
    $pdo = new PDO("mysql:host={$host};port={$port};charset={$charset}", $user, $pass, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    ]);

    echo "✅ เชื่อมต่อ MySQL สำเร็จ\n";

    // สร้างฐานข้อมูล
    $pdo->exec("CREATE DATABASE IF NOT EXISTS `{$dbName}` 
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");
    echo "✅ สร้างฐานข้อมูล '{$dbName}' สำเร็จ\n";

    $pdo->exec("USE `{$dbName}`");

    // ตาราง categories
    $pdo->exec("
        CREATE TABLE IF NOT EXISTS `categories` (
            `id`         INT AUTO_INCREMENT PRIMARY KEY,
            `source_id`  VARCHAR(10) NOT NULL UNIQUE,
            `name`       VARCHAR(100) NOT NULL,
            `max_page`   INT DEFAULT 100,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ");
    echo "✅ สร้างตาราง 'categories' สำเร็จ\n";

    // ตาราง animes
    $pdo->exec("
        CREATE TABLE IF NOT EXISTS `animes` (
            `id`          INT AUTO_INCREMENT PRIMARY KEY,
            `category_id` INT NOT NULL,
            `title`       VARCHAR(500) NOT NULL,
            `link`        VARCHAR(500) NOT NULL,
            `cover`       VARCHAR(500) DEFAULT '',
            `created_at`  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY `uq_link` (`link`),
            KEY `idx_category` (`category_id`),
            CONSTRAINT `fk_anime_category` FOREIGN KEY (`category_id`) REFERENCES `categories`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ");
    echo "✅ สร้างตาราง 'animes' สำเร็จ\n";

    // ตาราง episodes
    $pdo->exec("
        CREATE TABLE IF NOT EXISTS `episodes` (
            `id`         INT AUTO_INCREMENT PRIMARY KEY,
            `anime_id`   INT NOT NULL,
            `title`      VARCHAR(500) NOT NULL,
            `url`        VARCHAR(500) NOT NULL,
            `sort_order` INT DEFAULT 0,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            KEY `idx_anime` (`anime_id`),
            CONSTRAINT `fk_episode_anime` FOREIGN KEY (`anime_id`) REFERENCES `animes`(`id`) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    ");
    echo "✅ สร้างตาราง 'episodes' สำเร็จ\n";

    // ใส่ข้อมูลหมวดเริ่มต้น
    $stmt = $pdo->prepare("INSERT IGNORE INTO `categories` (`source_id`, `name`, `max_page`) VALUES (?, ?, ?)");
    $stmt->execute(['1', 'ซับไทย', 247]);
    $stmt->execute(['2', 'พากย์ไทย', 193]);
    $stmt->execute(['3', 'เดอะมูฟวี่', 86]);
    echo "✅ ใส่ข้อมูลหมวดเริ่มต้นสำเร็จ\n";

    echo "\n🎉 ตั้งค่าฐานข้อมูลเสร็จสิ้น!\n";

} catch (PDOException $e) {
    die("❌ Error: " . $e->getMessage() . "\n");
}
