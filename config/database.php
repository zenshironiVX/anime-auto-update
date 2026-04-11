<?php
/**
 * MAGA Z — Database Configuration (PDO MySQL)
 * ใช้กับ XAMPP MySQL default
 */

define('DB_HOST', 'sql200.infinityfree.com');
define('DB_PORT', 3306);
define('DB_NAME', 'if0_41536229_anime'); // เปลี่ยนชื่อฐานข้อมูลด้านหลังตาที่สร้างไว้ในโฮสต์
define('DB_USER', 'if0_41536229');
define('DB_PASS', 'vx9ts3Ol1dHmU76');
define('DB_CHARSET', 'utf8mb4');

/**
 * Get PDO connection (singleton)
 */
function getDB(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $dsn = "mysql:host=" . DB_HOST . ";port=" . DB_PORT . ";dbname=" . DB_NAME . ";charset=" . DB_CHARSET;
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ];
        try {
            $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
            
            // EMERGENCY AUTO-MIGRATION: Ensure 'updated_at' and 'sort_order' exist
            $cols = $pdo->query("SHOW COLUMNS FROM animes")->fetchAll(PDO::FETCH_COLUMN);
            
            if (!in_array('updated_at', $cols)) {
                $pdo->exec("ALTER TABLE animes ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP");
            }
            if (!in_array('sort_order', $cols)) {
                $pdo->exec("ALTER TABLE animes ADD COLUMN sort_order INT NOT NULL DEFAULT 0");
                $pdo->exec("ALTER TABLE animes ADD INDEX (sort_order)");
            }
        } catch (PDOException $e) {
            die("❌ เชื่อมต่อฐานข้อมูลไม่ได้: " . $e->getMessage());
        }
    }
    return $pdo;
}
